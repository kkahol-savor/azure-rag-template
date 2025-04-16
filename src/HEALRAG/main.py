"""
HEALRAG Main Module

This module provides a high-level interface for the HEALRAG library,
tying together the blob_manager, search_manager, rag_manager, and db_manager modules.
"""

import os
import json
import sys
from typing import List, Dict, Any, Optional, Union, Generator
from datetime import datetime
from azure.search.documents.indexes.models import SearchField, ScoringProfile, TextWeights, SemanticConfiguration
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the src directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.HEALRAG.blob_manager import BlobManager
from src.HEALRAG.search_manager import SearchManager
from src.HEALRAG.rag_manager import RAGManager
from src.HEALRAG.db_manager import DBManager

# Get FILE_OVERWRITE from environment variables, default to False
FILE_OVERWRITE = os.getenv("FILE_OVERWRITE", "False").lower() == "true"

class HEALRAG:
    """
    A class to manage the HEALRAG workflow.
    
    This class provides methods for uploading documents to blob storage,
    creating and populating search indices, and generating responses using RAG.
    """
    
    def __init__(
        self,
        blob_connection_string: Optional[str] = None,
        blob_container: Optional[str] = None,
        search_endpoint: Optional[str] = None,
        search_key: Optional[str] = None,
        search_index: Optional[str] = None,
        openai_endpoint: Optional[str] = None,
        openai_key: Optional[str] = None,
        openai_deployment: Optional[str] = None,
        cosmos_endpoint: Optional[str] = None,
        cosmos_key: Optional[str] = None,
        cosmos_database: Optional[str] = None,
        cosmos_container: Optional[str] = None
    ):
        """
        Initialize the HEALRAG workflow.
        
        Args:
            blob_connection_string: Azure Storage connection string
            blob_container: Azure Storage container name
            search_endpoint: Azure Cognitive Search endpoint
            search_key: Azure Cognitive Search key
            search_index: Azure Cognitive Search index name
            openai_endpoint: Azure OpenAI endpoint
            openai_key: Azure OpenAI key
            openai_deployment: Azure OpenAI deployment name
            cosmos_endpoint: Cosmos DB endpoint
            cosmos_key: Cosmos DB key
            cosmos_database: Cosmos DB database name
            cosmos_container: Cosmos DB container name
        """
        # Initialize blob manager
        self.blob_manager = BlobManager(
            connection_string=blob_connection_string,
            container_name=blob_container
        )
        
        # Initialize search manager
        self.search_manager = SearchManager(
            endpoint=search_endpoint,
            key=search_key,
            index_name=search_index
        )
        
        # Initialize RAG manager
        self.rag_manager = RAGManager(
            endpoint=openai_endpoint,
            key=openai_key,
            deployment=openai_deployment
        )
        
        # Initialize DB manager
        self.db_manager = DBManager(
            endpoint=cosmos_endpoint,
            key=cosmos_key,
            database=cosmos_database,
            container=cosmos_container
        )
    
    def upload_documents(self, directory_path: str, recursive: bool = True) -> Dict[str, Any]:
        """
        Upload documents to blob storage, skipping existing files unless FILE_OVERWRITE is True.
        
        Args:
            directory_path: Path to the directory containing documents
            recursive: Whether to upload subdirectories recursively
            
        Returns:
            Dictionary with upload results including:
            - total_files: Total number of files found
            - uploaded_files: Number of files uploaded
            - skipped_files: Number of files skipped (already exist)
            - failed_files: Number of files that failed to upload
            - details: List of upload details for each file
        """
        # First, list all existing blobs in the container
        existing_blobs = set(self.blob_manager.list_blobs())  # list_blobs() already returns blob names
        
        # Get list of files to upload
        files_to_upload = []
        for root, _, files in os.walk(directory_path):
            if not recursive and root != directory_path:
                continue
            for file in files:
                file_path = os.path.join(root, file)
                # Create blob name by removing the directory_path prefix
                blob_name = os.path.relpath(file_path, directory_path)
                
                if blob_name in existing_blobs and not FILE_OVERWRITE:
                    print(f"Skipping {blob_name} - already exists in blob storage")
                    continue
                    
                files_to_upload.append((file_path, blob_name))
        
        if not files_to_upload:
            print("No new documents to upload - all files already exist in blob storage")
            return {
                "total_files": len(existing_blobs),
                "uploaded_files": 0,
                "skipped_files": len(existing_blobs),
                "failed_files": 0,
                "details": []
            }
            
        # Upload new files
        results = self.blob_manager.upload_directory(directory_path, recursive)
        
        # Add information about skipped files
        results["skipped_files"] = len(existing_blobs) if not FILE_OVERWRITE else 0
        results["total_files"] = len(existing_blobs) + len(files_to_upload)
        
        return results
    
    def create_search_index(
        self,
        fields: List[Dict[str, Any]],
        scoring_profile: Optional[Dict[str, Any]] = None,
        semantic_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a search index with the specified fields and configurations.
        
        Args:
            fields: List of field definitions
            scoring_profile: Optional scoring profile configuration
            semantic_config: Optional semantic configuration
            
        Returns:
            Dict containing the created index information
        """
        # Convert dictionary fields to SearchField objects
        search_fields = []
        for field in fields:
            search_field = SearchField(
                name=field["name"],
                type=field["type"],
                key=field.get("key", False),
                searchable=field.get("searchable", True),
                filterable=field.get("filterable", True),
                sortable=field.get("sortable", True),
                facetable=field.get("facetable", False)
            )
            search_fields.append(search_field)
        
        # Convert scoring profile if provided
        scoring_profile_obj = None
        if scoring_profile:
            scoring_profile_obj = ScoringProfile(
                name=scoring_profile["name"],
                text_weights=TextWeights(weights=scoring_profile["text"]["weights"])
            )
        
        # Convert semantic config if provided
        semantic_config_obj = None
        if semantic_config:
            semantic_config_obj = SemanticConfiguration(
                name=semantic_config["name"],
                prioritized_fields=semantic_config["prioritizedFields"]
            )
            
        return self.search_manager.create_index(search_fields, scoring_profile_obj, semantic_config_obj)
    
    def populate_search_index(self, documents: List[Dict[str, Any]], batch_size: int = 1000) -> Dict[str, Any]:
        """
        Populate the search index with documents.
        
        Args:
            documents: List of documents to index
            batch_size: Size of batches for uploading
            
        Returns:
            Dictionary with indexing results
        """
        return self.search_manager.populate_index(documents, batch_size)
    
    def search(self, query: str, top: Optional[int] = None, 
              filter: Optional[str] = None, select: Optional[List[str]] = None,
              semantic_search: bool = True) -> List[Dict[str, Any]]:
        """
        Search the index with the given query.
        
        Args:
            query: Search query
            top: Number of results to return
            filter: OData filter expression
            select: List of fields to return
            semantic_search: Whether to use semantic search
            
        Returns:
            List of search results ordered by semantic score
        """
        # Get search results with semantic configuration and scoring profile
        results = self.search_manager.search(
            query=query,
            top=top,
            filter=filter,
            select=select,
            semantic_search=semantic_search,
            semantic_configuration_name="basic",
            scoring_profile_name="insurancePlansScoring"
        )
        
        # Sort results by semantic score in descending order
        if semantic_search and results:
            results.sort(key=lambda x: x.get('@search.score', 0), reverse=True)
        
        return results
    
    def generate_response(self, query: str, context: List[Dict[str, Any]], 
                         stream: bool = True) -> Union[str, Generator[str, None, None]]:
        """
        Generate a response to a query using the provided context.
        
        Args:
            query: User query
            context: List of retrieved documents to use as context
            stream: Whether to stream the response
            
        Returns:
            Generated response (string or generator for streaming)
        """
        return self.rag_manager.generate_response(query, context, stream)
    
    def save_conversation(self, conversation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save a conversation to the database.
        
        Args:
            conversation: Conversation to save
            
        Returns:
            Saved conversation
        """
        return self.db_manager.save_conversation(conversation)
    
    def get_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """
        Get a conversation from the database.
        
        Args:
            conversation_id: ID of the conversation to retrieve
            
        Returns:
            Retrieved conversation
        """
        return self.db_manager.get_conversation(conversation_id)
    
    def process_query(self, query: str, top: Optional[int] = None, 
                     save_conversation: bool = True) -> Dict[str, Any]:
        """
        Process a query using the RAG workflow.
        
        This method:
        1. Searches for relevant documents
        2. Generates a response using the retrieved documents
        3. Saves the conversation to the database
        
        Args:
            query: User query
            top: Number of documents to retrieve
            save_conversation: Whether to save the conversation to the database
            
        Returns:
            Dictionary with query results
        """
        # Search for relevant documents
        search_results = self.search(query, top=top)
        
        # Generate a response
        response = self.rag_manager.generate_response(query, search_results, stream=False)
        
        # Create conversation record
        conversation = {
            "query": query,
            "search_results": search_results,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
        
        # Save conversation if requested
        if save_conversation:
            saved_conversation = self.save_conversation(conversation)
            conversation["id"] = saved_conversation["id"]
        
        return conversation 