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
    
    def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Search the index.
        
        Args:
            query: Search query
            **kwargs: Additional search parameters
            
        Returns:
            List of search results
        """
        print(f"Executing search with query: '{query}' and parameters: {kwargs}")
        try:
            results = self.search_client.search(query, **kwargs)
            results_list = [dict(result) for result in results]
            print(f"Search results: {json.dumps(results_list, indent=4)}")
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

    def setup_rag_pipeline(self, data_dir: str) -> List[Dict[str, Any]]:
        """
        Set up the RAG pipeline by aggregating fields from JSON files in a directory.
        
        Args:
            data_dir: Directory containing JSON files
        
        Returns:
            Aggregated fields as a list of dictionaries
        """
        print(f"Setting up RAG pipeline for data directory: {data_dir}")
        aggregated_fields = []
        json_files = glob.glob(os.path.join(data_dir, "*.json"))
        print(f"Found {len(json_files)} JSON files in directory.")
        
        for json_file in json_files:
            print(f"Processing file: {json_file}")
            with open(json_file, "r") as f:
                json_data = json.load(f)
            
            # Generate fields for the current JSON file
            fields = self.generate_fields_from_json(json_data)
            
            # Add fields to the aggregated list, avoiding duplicates
            for field in fields:
                if field not in aggregated_fields:
                    aggregated_fields.append(field)
        
        # Write the aggregated fields to a JSON file
        with open("aggregated_fields.json", "w") as f:
            json.dump(aggregated_fields, f, indent=4)
        
        print(f"Aggregated fields: {json.dumps(aggregated_fields, indent=4)}")
        return aggregated_fields

