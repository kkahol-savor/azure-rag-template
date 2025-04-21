"""
Setup RAG Pipeline

This script uploads all files in the 'data' folder to Azure Blob Storage
using the BlobManager class.
"""

import os
import json
import re
import time
import pdfplumber
import logging
import warnings  # Add this import to suppress warnings
import sys
import contextlib  # Add this import for suppressing stderr
import base64  # Add this import for Base64 encoding
from datetime import datetime  # Add this import for datetime conversion
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import SearchIndex, SimpleField, SearchableField
from azure.core.credentials import AzureKeyCredential
from HEALRAG.search_manager import SearchManager

# Suppress pdfplumber warnings
logging.getLogger("pdfplumber").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning, module="pdfplumber")

@contextlib.contextmanager
def suppress_stderr():
    """
    Context manager to suppress standard error output.
    """
    with open(os.devnull, "w") as devnull:
        old_stderr = sys.stderr
        try:
            sys.stderr = devnull
            yield
        finally:
            sys.stderr = old_stderr

class RAGPipeline:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        self.file_overwrite = os.getenv("FILE_OVERWRITE", "False").lower() == "true"
        self.azure_storage_connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        self.blob_container_name = os.getenv("BLOB_CONTAINER_NAME")
        self.data_dir = os.getenv("DATA_DIR", "data")

        # Track a single sample JSON when INDEXING_SAMPLE is enabled
        self.sample_json_file: Optional[str] = None

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

    def generate_file_mapping(self) -> None:
        """
        Generate the file_mapping based on JSON and PDF files in the local data folder.

        The JSON files matching the regex ^SBC_\d{4,6}\.json$ will be used as "field_key_file",
        and PDF files with the same number in their name will be added to "files_to_be_indexed".

        Writes the file_mapping to a JSON file.
        """
        field_input_pattern = re.compile(r"^SBC_\d{4,6}\.json$")
        file_mapping: List[Dict[str, Any]] = []

        # Iterate through files in the data directory
        for root, _, files in os.walk(self.data_dir):
            json_files = [f for f in files if field_input_pattern.match(f)]
            for json_file in json_files:
                match = re.search(r"_(\d{4,6})\.json$", json_file)
                if not match:
                    continue
                number = match.group(1)
                pdf_files = [f for f in files if f.endswith(".pdf") and f"_{number}" in f]
                file_mapping.append({
                    "field_key_file": json_file,
                    "files_to_be_indexed": pdf_files
                })

        output_file = os.path.join(self.data_dir, "file_mapping.json")
        with open(output_file, "w") as f:
            json.dump(file_mapping, f, indent=4)
        print(f"File mapping written to {output_file}")

    def generate_fields_from_json(self, json_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        fields: List[Dict[str, Any]] = []
        field_names = set()

        # Key field
        fields.append({
            "name": "chunk_id",
            "type": "Edm.String",
            "searchable": False,
            "filterable": True,
            "sortable": True,
            "facetable": False,
            "key": True
        })
        field_names.add("chunk_id")

        # Parent ID
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
                continue
            field_names.add(key)

            entry: Dict[str, Any] = {"name": key, "searchable": True, "filterable": False, "sortable": False, "facetable": False, "key": False}
            if key in ["creation_date", "last_modified_date"]:
                entry.update({"type": "Edm.DateTimeOffset", "searchable": False, "filterable": True, "sortable": True})
            elif isinstance(value, (int, float)):
                entry.update({"type": "Edm.Double", "searchable": False, "filterable": True, "sortable": True, "facetable": True})
            else:
                entry["type"] = "Edm.String"
                entry.update({"searchable": True, "filterable": True})

            fields.append(entry)

        return fields

    def index_creator(self, fields: List[Dict[str, Any]]) -> None:
        print("Creating semantic index...")
        try:
            # Debug fields
            print(json.dumps(fields, indent=4))
            manager = SearchManager()
            manager.create_semantic_index(fields)
            print("Semantic index created successfully.")
        except Exception as e:
            print(f"Failed to create semantic index: {e}")

    def populate_insurance_index(self) -> None:
        """
        Populate the insurance index by calling the semantic_index_populator function
        from the SearchManager class, optionally filtering to one sample JSON.
        """
        # Generate the file mapping
        self.generate_file_mapping()

        # Read the file_mapping from the generated JSON file
        file_mapping_path = os.path.join(self.data_dir, "file_mapping.json")
        try:
            with open(file_mapping_path, "r") as f:
                file_mapping = json.load(f)
            print(f"File mapping loaded: {json.dumps(file_mapping, indent=4)}")
        except Exception as e:
            print(f"Failed to read file_mapping: {e}")
            return

        # If sampling, keep only the chosen JSON mapping
        if self.sample_json_file:
            file_mapping = [m for m in file_mapping if m["field_key_file"] == self.sample_json_file]
            if not file_mapping:
                print(f"No mapping for sample JSON '{self.sample_json_file}'")
                return

        # Call semantic_index_populator
        manager = SearchManager()
        try:
            manager.semantic_index_populator(
                field_input=r"^SBC_\d{4,6}\.json$",
                container_name=self.blob_container_name,
                file_mapping=file_mapping
            )
            print("Insurance index populated successfully.")
        except Exception as e:
            print(f"Failed to populate insurance index: {e}")

    def chunk_text(self, text: str, chunk_size: int = 1000) -> List[str]:
        return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

    def run(self):
        # Upload files before indexing
        self.upload_files_to_blob()

        print(f"Uploading files from '{self.data_dir}' to Azure Blob Storage...")
        indexing_sample = os.getenv("INDEXING_SAMPLE", "False").lower() == "true"

        if indexing_sample:
            print("INDEXING_SAMPLE is enabled. Processing only one JSON and its PDFs.")
            processed = False
            for root, _, files in os.walk(self.data_dir):
                if processed:
                    break
                for fname in files:
                    if fname.endswith(".json"):
                        print(f"Processing file: {fname}")
                        self.sample_json_file = fname
                        self.process_json_and_pdfs(root, fname, files)
                        processed = True
                        break
        else:
            print("INDEXING_SAMPLE is disabled. Processing all files one by one.")
            for root, _, files in os.walk(self.data_dir):
                for fname in files:
                    if fname.endswith(".json"):
                        print(f"Processing file: {fname}")
                        self.process_json_and_pdfs(root, fname, files)

    def process_json_and_pdfs(self, root: str, json_file: str, files: List[str]) -> None:
        """
        Process a single JSON file and its corresponding PDFs.

        Args:
            root: The root directory of the files.
            json_file: The JSON file to process.
            files: The list of files in the directory.
        """
        aggregated_keys = {}
        json_path = os.path.join(root, json_file)

        try:
            # Load JSON data
            with open(json_path, "r") as jf:
                data = json.load(jf)
                aggregated_keys.update(data)
                aggregated_keys.update({
                    "filename": json_file,
                    "parent_id": json_file,
                    "creation_date": datetime.utcfromtimestamp(os.path.getctime(json_path)).isoformat() + "Z",
                    "last_modified_date": datetime.utcfromtimestamp(os.path.getmtime(json_path)).isoformat() + "Z",
                    "file_size": os.path.getsize(json_path),
                    "file_path": json_path
                })
            print(f"JSON file '{json_file}' processed successfully.")

            # Find corresponding PDFs
            match = re.search(r"_(\d{4,6})\.json$", json_file)
            if not match:
                print(f"Could not extract number from JSON file '{json_file}'. Skipping.")
                return
            number = match.group(1)
            pdf_files = [f for f in files if f.endswith(".pdf") and f"_{number}" in f]

            # Process each PDF
            ndjson_data = []
            for pdf_file in pdf_files:
                pdf_path = os.path.join(root, pdf_file)
                print(f"Starting text extraction for PDF: {pdf_file}")
                with suppress_stderr():
                    with pdfplumber.open(pdf_path) as pdf:
                        text = "\n".join(p.extract_text() for p in pdf.pages if p.extract_text())
                print(f"Text extraction completed for PDF: {pdf_file}")

                # Add PDF metadata
                aggregated_keys.update({
                    "content": text,
                    "filename": pdf_file,
                    "parent_id": pdf_file,
                    "creation_date": datetime.utcfromtimestamp(os.path.getctime(pdf_path)).isoformat() + "Z",
                    "last_modified_date": datetime.utcfromtimestamp(os.path.getmtime(pdf_path)).isoformat() + "Z",
                    "file_size": os.path.getsize(pdf_path),
                    "file_path": pdf_path
                })

                # Chunk the extracted text
                if "content" in aggregated_keys:
                    chunks = self.chunk_text(aggregated_keys["content"])
                    print(f"Text chunked into {len(chunks)} parts for PDF: {pdf_file}")

                    # Log each chunk as a separate document in NDJSON
                    for idx, chunk in enumerate(chunks):
                        # Encode chunk_id using URL-safe Base64
                        chunk_id = base64.urlsafe_b64encode(f"{pdf_file}_chunk_{idx + 1}".encode()).decode()
                        ndjson_data.append({
                            "chunk_id": chunk_id,
                            "content": chunk,
                            "parent_id": pdf_file,
                            "sob_file": json.dumps(data.get("sob_file")) if isinstance(data.get("sob_file"), (list, dict)) else data.get("sob_file"),
                            "sbc_file": json.dumps(data.get("sbc_file")) if isinstance(data.get("sbc_file"), (list, dict)) else data.get("sbc_file"),
                            "plan_name": json.dumps(data.get("plan_name")) if isinstance(data.get("plan_name"), (list, dict)) else data.get("plan_name"),
                            "state": json.dumps(data.get("state")) if isinstance(data.get("state"), (list, dict)) else data.get("state"),
                            "qa_data": json.dumps(data.get("qa_data")) if isinstance(data.get("qa_data"), (list, dict)) else data.get("qa_data"),
                            "medical_events_data": json.dumps(data.get("medical_events_data")) if isinstance(data.get("medical_events_data"), (list, dict)) else data.get("medical_events_data"),
                            "excluded_services": json.dumps(data.get("excluded_services")) if isinstance(data.get("excluded_services"), (list, dict)) else data.get("excluded_services"),
                            "other_covered_services": json.dumps(data.get("other_covered_services")) if isinstance(data.get("other_covered_services"), (list, dict)) else data.get("other_covered_services"),
                            "filename": pdf_file,
                            "creation_date": datetime.utcfromtimestamp(os.path.getctime(pdf_path)).isoformat() + "Z",
                            "last_modified_date": datetime.utcfromtimestamp(os.path.getmtime(pdf_path)).isoformat() + "Z",
                            "file_size": os.path.getsize(pdf_path),
                            "file_path": pdf_path
                        })

            # Append NDJSON data to the single tracker file
            ndjson_tracker_path = os.path.join(os.getcwd(), "ndjson_indexing_tracker.ndjson")
            with open(ndjson_tracker_path, "a") as ndjson_file:
                for entry in ndjson_data:
                    ndjson_file.write(json.dumps(entry) + "\n")
            print(f"NDJSON tracker updated: {ndjson_tracker_path}")

            # Generate fields and index the data
            print(f"Generated fields for JSON '{json_file}' and PDFs: {pdf_files}")
            fields = self.generate_fields_from_json(aggregated_keys)
            self.index_creator(fields)

            # Index documents in Azure Cognitive Search
            manager = SearchManager()
            manager.upload_documents(ndjson_data)
            print(f"Documents indexed successfully for JSON '{json_file}' and PDFs: {pdf_files}")
            time.sleep(10)

        except Exception as ex:
            print(f"Error processing JSON '{json_file}' and its PDFs: {ex}")

if __name__ == "__main__":
    pipeline = RAGPipeline()
    pipeline.run()
