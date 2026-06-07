# /// script
# dependencies = [
#   "google-cloud-storage",
#   "langchain-ollama",
#   "langchain-openai",
#   "pydantic"
# ]
# ///

import os
import json
from google.cloud import storage
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

# Set to True to use local Ollama, False to use Cloud GPT-4o
USE_LOCAL_LLM = True

if USE_LOCAL_LLM:
    llm = ChatOllama(model="hermes3", temperature=0)
else:
    llm = ChatOpenAI(model="gpt-4o", temperature=0)

BUCKET_NAME = "marooncleanup"

def organize_ai_studio_data():
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    
    # Path where unzipped files will be located in the bucket (assuming user uploads them)
    # We will simulate processing any text files found in the bucket under ai_studio/
    blobs = list(bucket.list_blobs(prefix="ai_studio/"))
    
    if not blobs:
        print("No AI Studio files found in gs://marooncleanup/ai_studio/")
        return
        
    for blob in blobs:
        if not blob.name.endswith(".txt") and not blob.name.endswith(".json"):
            continue
            
        print(f"Analyzing file: {blob.name}")
        content = blob.download_as_text()
        
        if not content.strip() or content.strip() == "{}":
            print(f"  Skipping {blob.name} (File is empty).")
            continue
            
        # Prompt LLM to categorize the file based on contents
        prompt = f"""
        Read the following conversation or prompts from Google AI Studio:
        ---
        {content[:4000]} # Limit to 4k chars for categorization
        ---
        What is the primary topic of this conversation?
        Respond with ONLY ONE word or short phrase suitable for a folder name (e.g., 'Coding', 'Marketing_Strategy', 'Personal').
        """
        
        try:
            category = llm.invoke(prompt).content.strip().replace(" ", "_").replace("/", "-")
            if not category:
                category = "Uncategorized"
        except Exception as e:
            print(f"  LLM classification failed: {e}")
            category = "Uncategorized"
            
        # Move the file to the new organized folder
        new_name = f"ai_studio_organized/{category}/{os.path.basename(blob.name)}"
        bucket.copy_blob(blob, bucket, new_name)
        
        print(f"  -> Organized into category: {category}")

if __name__ == "__main__":
    organize_ai_studio_data()
