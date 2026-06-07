import os
import sys
import io
import json
import argparse
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.cloud import storage

# Default path for Hermes token
HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
TOKEN_PATH = Path("C:/Users/maroon/AppData/Local/hermes/google_token.json")
if not TOKEN_PATH.exists():
    TOKEN_PATH = HERMES_HOME / "google_token.json"

DEFAULT_FOLDER_ID = "1uv1UuMOdsNVqZk0BdjUsoeK-UY_UizJe"
GCS_BUCKET_NAME = "marooncleanup"

# Map Google-native MIME types to export formats
EXPORT_MAP = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": ("text/csv", ".csv"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.drawing": ("image/png", ".png"),
}

def get_drive_service():
    # Attempt to load Hermes token if it exists
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH))
            if creds.expired and creds.refresh_token:
                print("Refreshing credentials...")
                creds.refresh(Request())
                TOKEN_PATH.write_text(creds.to_json())
            if creds.valid:
                return build("drive", "v3", credentials=creds)
        except Exception as e:
            print(f"Warning: Failed to load Hermes token: {e}. Falling back to default credentials.")

    # Fallback to Application Default Credentials (ADC)
    import google.auth
    try:
        print("Loading Application Default Credentials (ADC)...")
        creds, project = google.auth.default(scopes=[
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/cloud-platform"
        ])
        # Refresh if necessary (gcloud tokens are typically self-refreshing or refreshed automatically)
        if creds.expired:
            print("Refreshing default credentials...")
            creds.refresh(Request())
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        print(f"ERROR: Failed to load Google Application Default Credentials: {e}")
        print("Please authenticate using 'gcloud auth application-default login --scopes=https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/cloud-platform'")
        sys.exit(1)

def download_file(service, file_id, file_name, mime_type, out_path):
    print(f"Downloading: {file_name} ({mime_type}) ...")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        if mime_type in EXPORT_MAP:
            export_mime, ext = EXPORT_MAP[mime_type]
            # Ensure file extension is appended if not present
            if not out_path.suffix:
                out_path = out_path.with_suffix(ext)
            request = service.files().export_media(fileId=file_id, mimeType=export_mime)
        else:
            request = service.files().get_media(fileId=file_id)

        fh = io.FileIO(str(out_path), "wb")
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"  Export/Download progress: {int(status.progress() * 100)}%", end="\r")
        fh.close()
        print(f"  Saved to {out_path}")
        return out_path
    except Exception as e:
        print(f"  ERROR downloading {file_name}: {e}")
        return None

def download_folder_recursive(service, folder_id, local_dir):
    print(f"\nProcessing folder ID: {folder_id} into {local_dir}")
    local_dir.mkdir(parents=True, exist_ok=True)
    
    query = f"'{folder_id}' in parents and trashed = false"
    page_token = None
    downloaded_files = []

    while True:
        results = service.files().list(
            q=query,
            pageSize=100,
            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=page_token
        ).execute()

        files = results.get("files", [])
        for f in files:
            f_id = f["id"]
            f_name = f["name"]
            f_mime = f["mimeType"]

            # Sanitize file name for local filesystem
            clean_name = "".join(c for c in f_name if c.isalnum() or c in "._- ")
            
            if f_mime == "application/vnd.google-apps.folder":
                subfolder_dir = local_dir / clean_name
                sub_files = download_folder_recursive(service, f_id, subfolder_dir)
                downloaded_files.extend(sub_files)
            else:
                out_path = local_dir / clean_name
                saved_path = download_file(service, f_id, f_name, f_mime, out_path)
                if saved_path:
                    downloaded_files.append((f_id, saved_path))

        page_token = results.get("nextPageToken", None)
        if not page_token:
            break

    return downloaded_files

def upload_to_gcs(local_dir, bucket_name, gcs_prefix="wffoodgroup_drive"):
    print(f"\nUploading local files from {local_dir} to GCS bucket gs://{bucket_name}...")
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
    except Exception as e:
        print(f"ERROR connecting to GCS: {e}")
        sys.exit(1)

    for root, dirs, files in os.walk(local_dir):
        for file in files:
            local_file_path = Path(root) / file
            # Compute relative path for GCS blob name
            rel_path = local_file_path.relative_to(local_dir)
            
            # ROUTING LOGIC: Route user custom sketches/coloring images to ai_studio/sketch_books/
            # and other regular documents to wffoodgroup_drive/
            if file.lower().endswith(('.png', '.jpg', '.jpeg')) or "sketch" in file.lower() or "coloring" in file.lower():
                blob_name = f"ai_studio/sketch_books/{rel_path.as_posix()}"
            else:
                blob_name = f"{gcs_prefix}/{rel_path.as_posix()}"
            
            print(f"Uploading {local_file_path} -> gs://{bucket_name}/{blob_name}")
            blob = bucket.blob(blob_name)
            try:
                blob.upload_from_filename(str(local_file_path))
            except Exception as e:
                print(f"  ERROR uploading {file}: {e}")

def delete_remote_files(service, file_list, root_folder_id):
    print("\nWARNING: Deleting all files in the target Google Drive folder...")
    
    # Delete files
    for f_id, local_path in file_list:
        print(f"Deleting file: {local_path.name} (ID: {f_id})")
        try:
            service.files().delete(fileId=f_id).execute()
        except Exception as e:
            print(f"  ERROR deleting file {f_id}: {e}")
            
    # Also recursively clean/delete subfolders and the root folder
    def delete_folders_rec(folder_id, is_root=False):
        query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        for f in results.get("files", []):
            delete_folders_rec(f["id"])
        
        if not is_root:
            print(f"Deleting folder ID: {folder_id}")
            try:
                service.files().delete(fileId=folder_id).execute()
            except Exception as e:
                print(f"  ERROR deleting folder {folder_id}: {e}")

    delete_folders_rec(root_folder_id, is_root=True)
    print("Remote Drive folder emptied.")

def main():
    parser = argparse.ArgumentParser(description="wffoodgroup Google Drive Migrator & Cleaner")
    parser.add_argument("--folder-id", default=DEFAULT_FOLDER_ID, help="Google Drive folder ID to download")
    parser.add_argument("--local-dir", default="./wffoodgroup_drive", help="Local directory to download files into")
    parser.add_argument("--gcs-bucket", default=GCS_BUCKET_NAME, help="GCS bucket name to upload to")
    parser.add_argument("--dry-run", action="store_true", help="List files in the folder without downloading")
    parser.add_argument("--download-only", action="store_true", help="Download and upload to GCS, but do not delete")
    parser.add_argument("--delete-only", action="store_true", help="Delete the files in Google Drive (must have been downloaded/uploaded first)")
    args = parser.parse_args()

    service = get_drive_service()
    folder_id = args.folder_id
    local_dir = Path(args.local_dir).resolve()

    if args.dry_run:
        print(f"Dry run: Querying folder ID {folder_id}...")
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, fields="files(id, name, mimeType)").execute()
        files = results.get("files", [])
        if not files:
            print("No files found or folder is empty.")
        for f in files:
            print(f"- {f['name']} (ID: {f['id']}, Type: {f['mimeType']})")
        return

    if args.delete_only:
        confirm = input(f"Are you sure you want to permanently delete everything in Google Drive folder {folder_id}? (yes/no): ")
        if confirm.lower() == "yes":
            # List files recursively to delete them
            print("Listing files to delete...")
            # We can download metadata recursively to delete
            file_list = []
            def collect_files(fid):
                q = f"'{fid}' in parents and trashed = false"
                res = service.files().list(q=q, fields="files(id, name, mimeType)").execute()
                for file in res.get("files", []):
                    if file["mimeType"] == "application/vnd.google-apps.folder":
                        collect_files(file["id"])
                    else:
                        file_list.append((file["id"], Path(file["name"])))
            collect_files(folder_id)
            delete_remote_files(service, file_list, folder_id)
        else:
            print("Deletion cancelled.")
        return

    # Standard run: download and upload to GCS
    print(f"Beginning download of folder {folder_id} into {local_dir}...")
    file_list = download_folder_recursive(service, folder_id, local_dir)
    print(f"Downloaded {len(file_list)} files.")

    # Upload to GCS
    upload_to_gcs(local_dir, args.gcs_bucket)

    if not args.download_only:
        confirm = input("\nDownload and upload complete. Do you want to DELETE the files on Google Drive now to empty the workspace? (yes/no): ")
        if confirm.lower() == "yes":
            delete_remote_files(service, file_list, folder_id)
        else:
            print("Deletion skipped. Files remain in Google Drive.")

if __name__ == "__main__":
    main()
