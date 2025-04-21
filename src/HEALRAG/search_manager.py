"""
Search Manager Module

This module provides functionality for managing Azure Cognitive Search operations.
"""

import os
import json
import glob  # Add this import for iterating through files
from typing import List, Dict, Any, Optional
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchFieldDataType,
    SemanticConfiguration,
    SemanticField
)
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
import re
import uuid
import time
import pdfplumber  # Add this import for PDF text extraction
import io

# Load environment variables
load_dotenv()

class SearchManager:
    """
    A class to manage Azure Cognitive Search operations.
    """
    
    def __init__(
        self,
        endpoint: Optional[str] = None,
        key: Optional[str] = None,
        index_name: Optional[str] = None
    ):
        """
        Initialize the SearchManager.
        
        Args:
            endpoint: Azure Search endpoint
            key: Azure Search key
            index_name: Name of the search index
        """
        self.endpoint = endpoint or os.getenv("AZURE_SEARCH_ENDPOINT")
        self.key = key or os.getenv("AZURE_SEARCH_KEY")
        self.index_name = index_name or os.getenv("AZURE_SEARCH_INDEX_NAME", "insurance-plans")
        
        if not self.endpoint or not self.key:
            raise ValueError("Azure Search endpoint and key are required")
        
        self.credential = AzureKeyCredential(self.key)
        
        # Create clients
        self.search_client = SearchClient(
            endpoint=self.endpoint,
            index_name=self.index_name,
            credential=self.credential
        )
        
        self.index_client = SearchIndexClient(
            endpoint=self.endpoint,
            credential=self.credential
        )
        
        print(f"SearchManager initialized with endpoint: {self.endpoint}, index_name: {self.index_name}")
    
    def create_bm25_index(self, fields: List[Dict[str, Any]]) -> None:
        """
        Create a search index with BM25 plain filter search.
        
        Args:
            fields: List of field definitions as JSON
        """
        print("Creating BM25 index...")
        print(f"Fields received for BM25 index: {json.dumps(fields, indent=4)}")

        # Check if the index already exists
        try:
            existing_index = self.index_client.get_index(self.index_name)
            print(f"Index '{self.index_name}' already exists. Using existing index.")
            return
        except Exception:
            print(f"Index '{self.index_name}' does not exist. Creating a new one.")

        # Parse fields into Azure Search field objects
        azure_fields = []
        for field in fields:
            if field.get("searchable", False):
                azure_fields.append(SearchableField(
                    name=field["name"],
                    type=SearchFieldDataType[field["type"]],
                    filterable=field.get("filterable", False),
                    sortable=field.get("sortable", False),
                    facetable=field.get("facetable", False)
                ))
            else:
                azure_fields.append(SimpleField(
                    name=field["name"],
                    type=SearchFieldDataType[field["type"]],
                    filterable=field.get("filterable", False),
                    sortable=field.get("sortable", False),
                    facetable=field.get("facetable", False)
                ))
        
        # Create the index
        index = SearchIndex(
            name=self.index_name,
            fields=azure_fields
        )
        
        # Create or update the index
        try:
            self.index_client.create_or_update_index(index)
            print(f"BM25 index created successfully for index: {self.index_name}")
        except Exception as e:
            print(f"Error creating BM25 index: {str(e)}")
            raise
    
    def create_semantic_index(self, fields: List[Dict[str, Any]]) -> None:
        """
        Create a search index with semantic search enabled.
        
        Args:
            fields: List of field definitions as JSON
        """
        print("Creating semantic index...")
        print(f"Fields received for semantic index: {json.dumps(fields, indent=4)}")

        # Check if the index already exists
        try:
            existing_index = self.index_client.get_index(self.index_name)
            print(f"Index '{self.index_name}' already exists. Using existing index.")
            return
        except Exception:
            print(f"Index '{self.index_name}' does not exist. Creating a new one.")

        # Map Edm types to SearchFieldDataType
        edm_to_search_field_type = {
            "Edm.String": SearchFieldDataType.String,
            "Edm.Double": SearchFieldDataType.Double,
            "Edm.DateTimeOffset": SearchFieldDataType.DateTimeOffset
        }

        # Parse fields into Azure Search field objects
        azure_fields = []
        key_field_set = False
        for field in fields:
            field_type = edm_to_search_field_type.get(field["type"])
            if not field_type:
                raise ValueError(f"Unsupported field type: {field['type']}")

            if field.get("key", False):
                if key_field_set:
                    raise ValueError("Multiple key fields found. Only one key field is allowed.")
                key_field_set = True

            if field.get("searchable", False):
                azure_fields.append(SearchableField(
                    name=field["name"],
                    type=field_type,
                    filterable=field.get("filterable", False),
                    sortable=field.get("sortable", False),
                    facetable=field.get("facetable", False),
                    key=field.get("key", False)
                ))
            else:
                azure_fields.append(SimpleField(
                    name=field["name"],
                    type=field_type,
                    filterable=field.get("filterable", False),
                    sortable=field.get("sortable", False),
                    facetable=field.get("facetable", False),
                    key=field.get("key", False)
                ))

        if not key_field_set:
            raise ValueError("No key field found. Each index must have exactly one key field.")

        # Define semantic configuration (without SemanticSettings)
        semantic_config = SemanticConfiguration(
            name="semantic-config",
            prioritized_fields={
                "titleField": None,
                "contentFields": [SemanticField(field_name="content")],
                "keywordsField": None
            }
        )

        # Create the index with semantic configuration
        index = SearchIndex(
            name=self.index_name,
            fields=azure_fields,
        )

        # Create or update the index
        try:
            self.index_client.create_or_update_index(index)
            print(f"Semantic index created successfully for index: {self.index_name}")
        except Exception as e:
            print(f"Error creating semantic index: {str(e)}")
            raise
    
    def search(
        self,
        query: str,
        index_name: Optional[str] = None,
        search_type: str = "hybrid",  # Default to hybrid search
        top: int = 10,
        select_fields: Optional[List[str]] = None,
        scoring_profile: Optional[str] = "basic",  # Default scoring profile
        semantic_configuration_name: Optional[str] = "basic",  # Default semantic configuration
        plan_name_filter: Optional[str] = None,  # New parameter for filtering by plan_name
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Search the index.

        Args:
            query: Search query.
            index_name: Name of the search index to query. Defaults to the initialized index.
            search_type: Type of search to perform ("bm25", "semantic", or "hybrid"). Defaults to "hybrid".
            top: Number of documents to retrieve. Defaults to 10.
            select_fields: List of fields to retrieve in the results. Defaults to None (all fields).
            scoring_profile: Scoring profile to use for ranking results. Defaults to "basic-profile".
            semantic_configuration_name: Semantic configuration to use for semantic or hybrid search. Defaults to "basic-profile".
            plan_name_filter: Optional filter value for the plan_name field.
            **kwargs: Additional search parameters.

        Returns:
            List of search results as dictionaries.
        """
        index_name = index_name or self.index_name  # Use the provided index name or default to the initialized one
        print(f"Executing {search_type} search on index: '{index_name}' with query: '{query}'")

        # Initialize a new SearchClient for the specified index
        search_client = SearchClient(
            endpoint=self.endpoint,
            index_name=index_name,
            credential=self.credential
        )

        # Determine query type based on search_type
        if search_type.lower() == "semantic":
            query_type = "semantic"
        elif search_type.lower() == "bm25":
            query_type = "simple"
        elif search_type.lower() == "hybrid":
            query_type = "semantic"  # Hybrid uses semantic query type with additional configurations
            kwargs["semantic_configuration_name"] = semantic_configuration_name
        else:
            raise ValueError(f"Unsupported search_type: {search_type}")

        # Build search parameters
        if select_fields:
            if "content" not in select_fields:
                select_fields.append("content")  # Ensure 'content' is included
        else:
            select_fields = ["content"]  # Default to include 'content'

        search_parameters = {
            "query_type": query_type,
            "top": top,
            "select": select_fields,
            "scoring_profile": scoring_profile,
            **kwargs
        }
        # Add plan_name filter if provided
        if plan_name_filter:
            # If a filter already exists, append with 'and'. Otherwise, simply add one.
            existing_filter = search_parameters.get("filter", "")
            plan_filter = f"plan_name eq '{plan_name_filter}'"
            if existing_filter:
                search_parameters["filter"] = f"{existing_filter} and {plan_filter}"
            else:
                search_parameters["filter"] = plan_filter

        try:
            # Perform the search
            results = search_client.search(query, **search_parameters)
            results_list = [dict(result) for result in results]
           # print(f"Search results: {json.dumps(results_list, indent=4)}")
            return results_list
        except Exception as e:
            print(f"Error during search: {str(e)}")
            return []
    
    def upload_documents(self, documents: List[Dict[str, Any]]) -> None:
        """
        Upload documents to the index.
        
        Args:
            documents: List of documents to upload
        """
        print(f"Uploading {len(documents)} documents to index: {self.index_name}")
        try:
            self.search_client.upload_documents(documents=documents)
            print("Documents uploaded successfully.")
        except Exception as e:
            print(f"Error uploading documents: {str(e)}")
            raise

    def semantic_index_populator(self, field_input: str, container_name: str, file_mapping: List[Dict[str, Any]]) -> None:
        """
        Populate a semantic index from a given blob storage container.

        Args:
            field_input: Regular expression for identifying field-relevant files.
            container_name: Name of the blob storage container.
            file_mapping: List of dictionaries mapping field-populator files to files to be indexed.
        """
        print(f"Populating semantic index from container: {container_name} with field input pattern: {field_input}")

        # Initialize BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(os.getenv("AZURE_STORAGE_CONNECTION_STRING"))
        container_client = blob_service_client.get_container_client(container_name)

        # Get chunk size from environment
        chunk_size = int(os.getenv("FILE_CHUNKING_SIZE", 4096))  # Default to 4096 bytes if not set

        # Validate file_mapping structure
        if not isinstance(file_mapping, list) or not all(
            isinstance(mapping, dict) and "field_key_file" in mapping and "files_to_be_indexed" in mapping
            for mapping in file_mapping
        ):
            raise ValueError("file_mapping must be a list of dictionaries with 'field_key_file' and 'files_to_be_indexed' keys.")

        # Process each mapping
        for mapping in file_mapping:
            field_key_file = mapping["field_key_file"]
            files_to_index = mapping["files_to_be_indexed"]

            # Ensure the field_key_file exists in the container
            try:
                field_blob_client = container_client.get_blob_client(field_key_file)
                field_data = json.loads(field_blob_client.download_blob().readall())
                print(f"Field data for '{field_key_file}': {json.dumps(field_data, indent=4)}")
            except Exception as e:
                print(f"Failed to process field key file '{field_key_file}': {e}")
                continue

            # Prepare documents for indexing
            documents = []
            for file_name in files_to_index:
                try:
                    file_blob_client = container_client.get_blob_client(file_name)
                    file_content = file_blob_client.download_blob().readall()

                    # Extract text from PDF
                    with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                        extracted_text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

                    # Chunk the extracted text
                    for i in range(0, len(extracted_text), chunk_size):
                        chunk = extracted_text[i:i + chunk_size]
                        chunk_id = f"{uuid.uuid4()}_{os.path.splitext(file_name)[0]}"
                        document = {
                            "chunk_id": chunk_id,
                            "parent_id": file_name,
                            "content": chunk
                        }

                        # Populate fields from field_key_file
                        for key, value in field_data.items():
                            if isinstance(value, (list, dict)):
                                document[key] = str(value)  # Convert lists/dicts to strings
                            else:
                                document[key] = value  # Use the value directly

                        documents.append(document)
                except Exception as e:
                    print(f"Failed to process file '{file_name}': {e}")

            # Log total documents for the field_key_file
            print(f"Total documents prepared for '{field_key_file}': {len(documents)}")

            # Upload documents to the index in batches to handle rate limits
            batch_size = int(os.getenv("BATCH_SIZE", 100))  # Default to 100 if not set
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                retry_attempts = 0
                max_retries = 5  # Maximum number of retries
                backoff_time = 5  # Initial backoff time in seconds

                while retry_attempts <= max_retries:
                    try:
                        self.upload_documents(batch)
                        print(f"Indexed batch {i // batch_size + 1} for field key file '{field_key_file}' successfully.")
                        break  # Exit retry loop on success
                    except Exception as e:
                        retry_attempts += 1
                        if retry_attempts > max_retries:
                            print(f"Failed to index batch {i // batch_size + 1} after {max_retries} retries: {e}")
                            break
                        print(f"Rate limit or other error occurred while indexing batch {i // batch_size + 1}: {e}")
                        print(f"Retrying in {backoff_time} seconds (attempt {retry_attempts}/{max_retries})...")
                        time.sleep(backoff_time)
                        backoff_time *= 2  # Exponential backoff



