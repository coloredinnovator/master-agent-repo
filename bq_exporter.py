import os
import subprocess
import json

def get_tables(dataset_id):
    cmd = f'bq ls --format=json {dataset_id}'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error listing tables in {dataset_id}: {result.stderr}")
        return []
    try:
        tables = json.loads(result.stdout)
        return [t["tableReference"]["tableId"] for t in tables]
    except json.JSONDecodeError:
        return []

def backup_all_tables():
    bucket_name = "marooncleanup"
    
    # Get datasets
    cmd = 'bq ls --format=json'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error listing datasets: {result.stderr}")
        return

    try:
        datasets = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("Could not parse datasets JSON.")
        return

    if not datasets:
        print("No datasets found in the project.")
        return

    for dataset in datasets:
        dataset_id = dataset["datasetReference"]["datasetId"]
        print(f"\nScanning dataset: {dataset_id}")
        
        tables = get_tables(dataset_id)
        if not tables:
            print(f"  No tables found in {dataset_id}.")
            continue
            
        for table_id in tables:
            local_file = f"{table_id}.json"
            gcs_uri = f"gs://{bucket_name}/bigquery_backup/{dataset_id}/{local_file}"
            
            print(f"  Extracting {dataset_id}.{table_id}...")
            
            # Export view/table data to local file
            query = f"SELECT * FROM `{dataset_id}.{table_id}`"
            export_cmd = f'bq query --use_legacy_sql=false --format=json --max_rows=1000000 "{query}" > {local_file}'
            
            subprocess.run(export_cmd, shell=True)
            
            # Upload to GCS
            upload_cmd = f'gcloud storage cp {local_file} "{gcs_uri}"'
            subprocess.run(upload_cmd, shell=True)
            
            # Cleanup
            if os.path.exists(local_file):
                os.remove(local_file)
                
            print(f"    [SUCCESS] Uploaded {table_id} to GCS.")

if __name__ == "__main__":
    backup_all_tables()
