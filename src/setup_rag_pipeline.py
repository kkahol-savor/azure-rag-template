"""
Setup RAG Pipeline

This script uploads all files in the 'data' folder to Azure Blob Storage
using the BlobManager class.
"""

import os
import json
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError
from dotenv import load_dotenv
from typing import Dict, Any, List
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import SearchIndex, SimpleField, SearchableField
from azure.core.credentials import AzureKeyCredential
from HEALRAG.search_manager import SearchManager

class RAGPipeline:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        self.file_overwrite = os.getenv("FILE_OVERWRITE", "False").lower() == "true"
        self.azure_storage_connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        self.blob_container_name = os.getenv("BLOB_CONTAINER_NAME")
        self.data_dir = os.getenv("DATA_DIR", "data")

        # Initialize Blob Service Client
        self.blob_service_client = BlobServiceClient.from_connection_string(self.azure_storage_connection_string)
        self.container_client = self.blob_service_client.get_container_client(self.blob_container_name)

    def ensure_container_exists(self):
        try:
            self.container_client.get_container_properties()
            print(f"Container '{self.blob_container_name}' exists.")
        except ResourceNotFoundError:
            print(f"Container '{self.blob_container_name}' does not exist. Creating it...")
            self.container_client.create_container()
            print(f"Container '{self.blob_container_name}' created successfully.")

    def upload_files_to_blob(self):
        self.ensure_container_exists()  # Ensure container exists before uploading
        for root, _, files in os.walk(self.data_dir):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                blob_name = os.path.relpath(file_path, self.data_dir)

                # Check if the blob already exists
                blob_client = self.container_client.get_blob_client(blob_name)
                if not self.file_overwrite and blob_client.exists():
                    print(f"Skipping existing file: {blob_name}")
                    continue

                # Upload the file
                try:
                    print(f"Uploading file: {blob_name}")
                    with open(file_path, "rb") as data:
                        blob_client.upload_blob(data, overwrite=self.file_overwrite)
                    print(f"Uploaded file: {blob_name}")
                except Exception as e:
                    print(f"Failed to upload file '{blob_name}': {e}")

    def generate_fields_from_json(self, json_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate fields for an index based on the structure of the JSON data.
        
        Args:
            json_data: The JSON data to process.
        
        Returns:
            A list of field definitions for the index.
        """
        fields = []
        field_names = set()  # Track field names to avoid duplicates

        # Ensure 'chunk_id' is always included as the key field
        fields.append({
            "name": "chunk_id",
            "type": "Edm.String",
            "searchable": False,
            "filterable": True,
            "sortable": True,
            "facetable": False,
            "key": True  # Set 'chunk_id' as the key field
        })
        field_names.add("chunk_id")

        # Ensure 'parent_id' is included and set to the filename
        fields.append({
            "name": "parent_id",
            "type": "Edm.String",
            "searchable": True,
            "filterable": True,
            "sortable": True,
            "facetable": False,
            "key": False
        })
        field_names.add("parent_id")

        for key, value in json_data.items():
            if key in field_names:
                continue  # Skip duplicate fields
            field_names.add(key)

            if key in ["creation_date", "last_modified_date"]:
                # Ensure these fields are always Edm.DateTimeOffset
                fields.append({
                    "name": key,
                    "type": "Edm.DateTimeOffset",
                    "searchable": False,
                    "filterable": True,
                    "sortable": True,
                    "facetable": False,
                    "key": False
                })
            elif isinstance(value, list):
                fields.append({
                    "name": key,
                    "type": "Edm.String",
                    "searchable": True,
                    "filterable": True,
                    "sortable": False,
                    "facetable": False,
                    "key": False
                })
            elif isinstance(value, str):
                fields.append({
                    "name": key,
                    "type": "Edm.String",
                    "searchable": True,
                    "filterable": True,
                    "sortable": True,
                    "facetable": False,
                    "key": False
                })
            elif isinstance(value, (int, float)):
                fields.append({
                    "name": key,
                    "type": "Edm.Double",
                    "searchable": False,
                    "filterable": True,
                    "sortable": True,
                    "facetable": True,
                    "key": False
                })
            elif isinstance(value, dict):
                fields.append({
                    "name": key,
                    "type": "Edm.String",
                    "searchable": True,
                    "filterable": True,
                    "sortable": False,
                    "facetable": False,
                    "key": False
                })
            else:
                fields.append({
                    "name": key,
                    "type": "Edm.String",
                    "searchable": True,
                    "filterable": True,
                    "sortable": False,
                    "facetable": False,
                    "key": False
                })

        return fields

    def index_creator(self, fields: List[Dict[str, Any]]) -> None:
        """
        Create a semantic index using the SearchManager.

        Args:
            fields: A list of field definitions for the index.
        """
        print("Creating semantic index...")
        try:
            # Debugging: Validate and print the fields structure
            if not isinstance(fields, list) or not all(isinstance(field, dict) for field in fields):
                raise ValueError("Fields must be a list of dictionaries.")
            
            print("Fields being passed to create_semantic_index:")
            for field in fields:
                print(json.dumps(field, indent=4))  # Pretty-print each field for clarity

            # Verify SearchManager instance and method
            search_manager = SearchManager()
            if not hasattr(search_manager, "create_semantic_index"):
                raise AttributeError("SearchManager does not have a 'create_semantic_index' method.")
            if not callable(search_manager.create_semantic_index):
                raise TypeError("'create_semantic_index' is not callable.")

            # Pass fields to create_semantic_index
            search_manager.create_semantic_index(fields)
            print("Semantic index created successfully.")
        except Exception as e:
            print(f"Failed to create semantic index: {e}")

    def run(self):
        print(f"Uploading files from '{self.data_dir}' to Azure Blob Storage...")
        # try:
        #     self.upload_files_to_blob()
        #     print("File upload process completed.")
        # except Exception as e:
        #     print(f"An error occurred during the upload process: {e}")

        # Aggregate outer keys from all JSON files in the data directory
        aggregated_keys = {}
        for root, _, files in os.walk(self.data_dir):
            for file_name in files:
                if file_name.endswith(".json"):
                    file_path = os.path.join(root, file_name)
                    try:
                        with open(file_path, "r") as json_file:
                            json_data = json.load(json_file)
                            if isinstance(json_data, dict):
                                aggregated_keys.update(json_data)
                                # Add metadata fields
                                aggregated_keys["filename"] = file_name
                                aggregated_keys["parent_id"] = file_name  # Set parent_id to the filename
                                aggregated_keys["content"] = json.dumps(json_data)
                                aggregated_keys["creation_date"] = os.path.getctime(file_path)
                                aggregated_keys["last_modified_date"] = os.path.getmtime(file_path)
                                aggregated_keys["file_size"] = os.path.getsize(file_path)
                                aggregated_keys["file_path"] = file_path
                    except Exception as e:
                        print(f"Failed to process JSON file '{file_name}': {e}")

        # Generate fields from the aggregated keys
        fields = self.generate_fields_from_json(aggregated_keys)
        print("Generated fields for index:")
        # Write the fields to a JSON file
        with open("fields.json", "w") as f:
            json.dump(fields, f, indent=4)

        # Create the semantic index
        self.index_creator(fields)

if __name__ == "__main__":
    pipeline = RAGPipeline()
    pipeline.run()
