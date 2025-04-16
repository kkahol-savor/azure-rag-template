"""
Search Manager Module

This module provides functions for managing Azure Cognitive Search operations.
It includes index creation, population, and search functionality with semantic search capabilities.
"""

import os
import json
from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import datetime
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    ComplexField,
    SearchFieldDataType,
    ScoringProfile,
    TextWeights,
    SemanticConfiguration
)
from azure.search.documents import SearchClient
from azure.search.documents.models import QueryType
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Azure Cognitive Search configuration
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
AZURE_SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME", "insurance-plans")
TOP_N_DOCUMENTS = int(os.getenv("TOP_N_DOCUMENTS", "5"))
PROGRESS_FILE = os.getenv("SEARCH_PROGRESS_FILE", "search_progress.ndjson")

class SearchManager:
    """
    A class to manage Azure Cognitive Search operations.
    
    This class provides methods for creating and populating search indices,
    as well as performing searches with semantic capabilities.
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
            endpoint: Azure Cognitive Search endpoint
            key: Azure Cognitive Search key
            index_name: Name of the index to use
        """
        self.endpoint = endpoint or AZURE_SEARCH_ENDPOINT
        self.key = key or AZURE_SEARCH_KEY
        self.index_name = index_name or AZURE_SEARCH_INDEX_NAME
        
        if not self.endpoint or not self.key:
            raise ValueError("Azure Cognitive Search endpoint and key are required")
        
        self.credential = AzureKeyCredential(self.key)
        self.index_client = SearchIndexClient(endpoint=self.endpoint, credential=self.credential)
        self.search_client = None
    
    def create_index(self, fields: List[Union[SimpleField, SearchableField, ComplexField]], 
                    scoring_profile: Optional[ScoringProfile] = None,
                    semantic_config: Optional[SemanticConfiguration] = None) -> SearchIndex:
        """
        Create a search index with the specified schema.
        
        Args:
            fields: List of fields to include in the index
            scoring_profile: Optional scoring profile for custom ranking
            semantic_config: Optional semantic configuration for semantic search
            
        Returns:
            Created SearchIndex
        """
        # Create the index with basic configuration
        index = SearchIndex(
            name=self.index_name,
            fields=fields
        )
        
        # Add scoring profile if provided
        if scoring_profile:
            index.scoring_profiles = [scoring_profile]
        
        # Add semantic configuration if provided
        if semantic_config:
            # In newer versions of the SDK, semantic settings are handled through the semantic_config
            index.semantic_settings = semantic_config
        
        try:
            result = self.index_client.create_or_update_index(index)
            print(f"Index '{result.name}' created successfully")
            
            # Record progress
            self._record_progress({
                "operation": "create_index",
                "index_name": self.index_name,
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            })
            
            return result
        except Exception as e:
            # Record failure
            self._record_progress({
                "operation": "create_index",
                "index_name": self.index_name,
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e)
            })
            
            raise
    
    def create_default_semantic_config(self, content_fields: List[str], 
                                     keywords_fields: Optional[List[str]] = None) -> SemanticConfiguration:
        """
        Create a default semantic configuration for semantic search.
        
        Args:
            content_fields: List of fields to use for semantic search
            keywords_fields: Optional list of fields to use for keyword extraction
            
        Returns:
            SemanticConfiguration
        """
        # In newer versions of the SDK, the structure is different
        return SemanticConfiguration(
            name="default",
            prioritized_fields={
                "contentFields": [{"fieldName": field} for field in content_fields],
                "keywordsFields": [{"fieldName": field} for field in (keywords_fields or [])]
            }
        )
    
    def create_default_scoring_profile(self, field_weights: Dict[str, float]) -> ScoringProfile:
        """
        Create a default scoring profile for custom ranking.
        
        Args:
            field_weights: Dictionary of field names and their weights
            
        Returns:
            ScoringProfile
        """
        return ScoringProfile(
            name="default",
            text_weights=TextWeights(weights=field_weights)
        )
    
    def populate_index(self, documents: List[Dict[str, Any]], batch_size: int = 1000) -> Dict[str, Any]:
        """
        Populate the search index with documents.
        
        Args:
            documents: List of documents to index
            batch_size: Size of batches for uploading
            
        Returns:
            Dictionary with indexing results
        """
        if not documents:
            return {"success": False, "message": "No documents provided"}
        
        # Initialize search client if not already done
        if not self.search_client:
            self.search_client = SearchClient(
                endpoint=self.endpoint,
                index_name=self.index_name,
                credential=self.credential
            )
        
        results = {
            "success": True,
            "total": len(documents),
            "indexed": 0,
            "failed": 0,
            "errors": []
        }
        
        # Upload documents in batches
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            try:
                result = self.search_client.upload_documents(documents=batch)
                success_count = sum(1 for r in result if r.succeeded)
                results["indexed"] += success_count
                results["failed"] += len(batch) - success_count
                
                # Record progress
                self._record_progress({
                    "operation": "populate_index",
                    "index_name": self.index_name,
                    "batch_start": i,
                    "batch_size": len(batch),
                    "success_count": success_count,
                    "timestamp": datetime.now().isoformat(),
                    "status": "success"
                })
                
                print(f"Uploaded batch of {len(batch)} documents")
                print(f"Successfully indexed {success_count} documents")
                print(f"Failed to index {len(batch) - success_count} documents")
            except Exception as e:
                results["failed"] += len(batch)
                results["errors"].append({"batch_start": i, "error": str(e)})
                
                # Record failure
                self._record_progress({
                    "operation": "populate_index",
                    "index_name": self.index_name,
                    "batch_start": i,
                    "batch_size": len(batch),
                    "timestamp": datetime.now().isoformat(),
                    "status": "failed",
                    "error": str(e)
                })
                
                print(f"Failed to upload batch: {str(e)}")
        
        return results
    
    def search(
        self,
        query: str,
        top: Optional[int] = None,
        filter: Optional[str] = None,
        select: Optional[List[str]] = None,
        semantic_search: bool = True,
        semantic_configuration_name: str = "basic",
        scoring_profile_name: str = "insurancePlansScoring"
    ) -> List[Dict[str, Any]]:
        """
        Search the index with the given query.
        
        Args:
            query: Search query
            top: Number of results to return
            filter: OData filter expression
            select: List of fields to return
            semantic_search: Whether to use semantic search
            semantic_configuration_name: Name of the semantic configuration to use
            scoring_profile_name: Name of the scoring profile to use
            
        Returns:
            List of search results ordered by semantic score
        """
        # Initialize search client if not already done
        if not self.search_client:
            self.search_client = SearchClient(
                endpoint=self.endpoint,
                index_name=self.index_name,
                credential=self.credential
            )
        
        # Set up search options
        search_options = {
            "scoring_profile": scoring_profile_name  # Use the insurance plans scoring profile
        }
        
        if semantic_search:
            search_options["query_type"] = QueryType.SEMANTIC
            search_options["query_language"] = "en-us"
            search_options["semantic_configuration_name"] = semantic_configuration_name
        
        # Perform the search
        top = top or TOP_N_DOCUMENTS
        results = list(self.search_client.search(
            search_text=query,
            top=top,
            filter=filter,
            select=select,
            **search_options
        ))
        
        # Record search
        self._record_progress({
            "operation": "search",
            "index_name": self.index_name,
            "query": query,
            "top": top,
            "results_count": len(results),
            "timestamp": datetime.now().isoformat(),
            "status": "success"
        })
        
        return results
    
    def semantic_search(
        self,
        query: str,
        top: Optional[int] = None,
        filter: Optional[str] = None,
        select: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform a semantic search with the given query.
        
        Args:
            query: Search query
            top: Number of results to return
            filter: OData filter expression
            select: List of fields to return
            
        Returns:
            List of search results
        """
        return self.search(
            query=query,
            top=top,
            filter=filter,
            select=select,
            semantic_search=True,
            query_type=QueryType.SEMANTIC
        )
    
    def _record_progress(self, record: Dict[str, Any]) -> None:
        """
        Record operation progress in NDJSON format.
        
        Args:
            record: Dictionary with operation details
        """
        os.makedirs(os.path.dirname(PROGRESS_FILE) or ".", exist_ok=True)
        
        with open(PROGRESS_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")
    
    def get_progress(self) -> List[Dict[str, Any]]:
        """
        Get all recorded progress.
        
        Returns:
            List of progress records
        """
        if not os.path.exists(PROGRESS_FILE):
            return []
        
        records = []
        with open(PROGRESS_FILE, "r") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        
        return records
    
    def get_last_operation(self, operation_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get the last recorded operation.
        
        Args:
            operation_type: Filter by operation type (create_index, populate_index, search)
            
        Returns:
            Last operation record or None
        """
        records = self.get_progress()
        
        if operation_type:
            records = [r for r in records if r.get("operation") == operation_type]
        
        return records[-1] if records else None 