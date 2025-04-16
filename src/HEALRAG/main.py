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

# Add the src directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.HEALRAG.blob_manager import BlobManager
from src.HEALRAG.search_manager import SearchManager
from src.HEALRAG.rag_manager import RAGManager
from src.HEALRAG.db_manager import DBManager

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
        Upload documents to blob storage.
        
        Args:
            directory_path: Path to the directory containing documents
            recursive: Whether to upload subdirectories recursively
            
        Returns:
            Dictionary with upload results
        """
        return self.blob_manager.upload_directory(directory_path, recursive)
    
    def create_search_index(self, fields: List[Any], 
                          scoring_profile: Optional[Any] = None,
                          semantic_config: Optional[Any] = None) -> Any:
        """
        Create a search index with the specified schema.
        
        Args:
            fields: List of fields to include in the index
            scoring_profile: Optional scoring profile for custom ranking
            semantic_config: Optional semantic configuration for semantic search
            
        Returns:
            Created SearchIndex
        """
        return self.search_manager.create_index(fields, scoring_profile, semantic_config)
    
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
            List of search results
        """
        return self.search_manager.search(
            query=query,
            top=top,
            filter=filter,
            select=select,
            semantic_search=semantic_search
        )
    
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