"""
RAG_CREATION Module

This module provides a high-level interface for creating and using a RAG system
for insurance plan documents. It handles the complete workflow from document
upload to response generation with citations.
"""

import os
import json
import re
import sys
from typing import List, Dict, Any, Optional, Union, Generator, Tuple
from datetime import datetime
from dotenv import load_dotenv

# Add the src directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.HEALRAG.main import HEALRAG

# Load environment variables
load_dotenv()

class RAGCreation:
    """
    A class to manage the complete RAG workflow for insurance plan documents.
    
    This class provides methods for:
    1. Uploading documents to blob storage
    2. Creating and populating a search index with extracted metadata
    3. Searching for relevant documents
    4. Generating responses with citations
    5. Storing conversations in Cosmos DB
    """
    
    def __init__(self):
        """
        Initialize the RAG creation workflow.
        """
        self.healrag = HEALRAG()
        self.index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "insurance-plans")
        self.top_n_documents = int(os.getenv("TOP_N_DOCUMENTS", "5"))
    
    def upload_documents(self, data_dir: str = "data") -> Dict[str, Any]:
        """
        Upload documents from the data directory to blob storage.
        
        Args:
            data_dir: Path to the directory containing documents
            
        Returns:
            Dictionary with upload results
        """
        print(f"Uploading documents from {data_dir} to blob storage...")
        return self.healrag.upload_documents(data_dir)
    
    def _parse_list_items(self, text: str) -> List[str]:
        """
        Parse a string containing list items with bullet points.
        
        Args:
            text: String containing list items with bullet points
            
        Returns:
            List of parsed items
        """
        # Replace the bullet point character with a standard bullet
        text = text.replace("\u00b7", "•")
        
        # Split by bullet points and clean up
        items = [item.strip() for item in text.split("•") if item.strip()]
        
        return items
    
    def _extract_json_files(self, data_dir: str = "data") -> List[Dict[str, Any]]:
        """
        Extract JSON files from the data directory.
        
        Args:
            data_dir: Path to the directory containing JSON files
            
        Returns:
            List of extracted JSON data
        """
        json_files = []
        
        for file in os.listdir(data_dir):
            if file.endswith(".json"):
                with open(os.path.join(data_dir, file), "r") as f:
                    json_data = json.load(f)
                    json_files.append(json_data)
        
        return json_files
    
    def _create_index_fields(self) -> List[Dict[str, Any]]:
        """
        Create fields for the search index based on the JSON structure.
        
        Returns:
            List of field definitions
        """
        fields = [
            {"name": "chunk_id", "type": "Edm.String", "key": True},  # Only this field should be key
            {"name": "content", "type": "Edm.String", "searchable": True},
            {"name": "parent_id", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "plan_name", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "state", "type": "Edm.String", "searchable": True, "filterable": True},
            # Collection fields cannot be sortable
            {"name": "excluded_services", "type": "Collection(Edm.String)", "searchable": True, "sortable": False},
            {"name": "other_covered_services", "type": "Collection(Edm.String)", "searchable": True, "sortable": False},
            {"name": "qa_questions", "type": "Collection(Edm.String)", "searchable": True, "sortable": False},
            {"name": "qa_answers", "type": "Collection(Edm.String)", "searchable": True, "sortable": False},
            {"name": "qa_why_this_matters", "type": "Collection(Edm.String)", "searchable": True, "sortable": False},
            {"name": "medical_events", "type": "Collection(Edm.String)", "searchable": True, "sortable": False},
            {"name": "medical_services", "type": "Collection(Edm.String)", "searchable": True, "sortable": False},
            {"name": "medical_costs", "type": "Collection(Edm.String)", "searchable": True, "sortable": False},
            {"name": "medical_limitations", "type": "Collection(Edm.String)", "searchable": True, "sortable": False}
        ]
        
        return fields
    
    def _create_scoring_profile(self) -> Dict[str, Any]:
        """
        Create a scoring profile for the search index.
        
        Returns:
            Scoring profile definition
        """
        return {
            "name": "insurancePlansScoring",
            "text": {
                "weights": {
                    "content": 3.0,
                    "plan_name": 2.0,
                    "state": 1.5,
                    "qa_questions": 1.0,
                    "qa_answers": 1.0,
                    "qa_why_this_matters": 1.0,
                    "medical_events": 1.0,
                    "medical_services": 1.0,
                    "medical_costs": 1.0,
                    "excluded_services": 1.0,
                    "other_covered_services": 1.0
                }
            }
        }
    
    def _create_semantic_config(self) -> Dict[str, Any]:
        """
        Create a semantic configuration for the search index.
        
        Returns:
            Semantic configuration definition
        """
        return {
            "name": "insurancePlansSemantic",
            "prioritizedFields": {
                "contentFields": [
                    {"fieldName": "content"},
                    {"fieldName": "qa_questions"},
                    {"fieldName": "qa_answers"},
                    {"fieldName": "qa_why_this_matters"},
                    {"fieldName": "medical_events"},
                    {"fieldName": "medical_services"},
                    {"fieldName": "medical_costs"},
                    {"fieldName": "excluded_services"},
                    {"fieldName": "other_covered_services"}
                ],
                "keywordsFields": [
                    {"fieldName": "plan_name"},
                    {"fieldName": "state"}
                ],
                "titleField": {"fieldName": "plan_name"}
            }
        }
    
    def _prepare_documents_for_indexing(self, json_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prepare documents for indexing by extracting and structuring data.
        
        Args:
            json_data: List of JSON data from files
            
        Returns:
            List of documents ready for indexing
        """
        documents = []
        
        for data in json_data:
            # Extract basic fields
            plan_name = data.get("plan_name", "")
            state = data.get("state", "")
            
            # Create URL-safe plan name by replacing spaces with double dashes and removing special characters
            safe_plan_name = plan_name.replace(" ", "--")
            # Remove apostrophes and other special characters
            safe_plan_name = ''.join(c for c in safe_plan_name if c.isalnum() or c == '-')
            
            # Process Q&A data
            qa_questions = []
            qa_answers = []
            qa_why_this_matters = []
            
            for qa in data.get("qa_data", []):
                qa_questions.append(qa.get("question", ""))
                qa_answers.append(qa.get("answer", ""))
                qa_why_this_matters.append(qa.get("why_this_matters", ""))
            
            # Process medical events data
            medical_events = []
            medical_services = []
            medical_costs = []
            medical_limitations = []
            
            for event in data.get("medical_events_data", []):
                medical_events.append(event.get("common_medical_event", ""))
                medical_services.append(event.get("services_you_may_need", ""))
                medical_costs.append(event.get("what_you_will_pay", ""))
                medical_limitations.append(event.get("limitations_exceptions", ""))
            
            # Process excluded services
            excluded_services = self._parse_list_items(data.get("excluded_services", ""))
            
            # Process other covered services
            other_covered_services = self._parse_list_items(data.get("other_covered_services", ""))
            
            # Create a document for each Q&A item
            for i, (question, answer, why_matters) in enumerate(zip(qa_questions, qa_answers, qa_why_this_matters)):
                # Create URL-safe chunk ID with double dashes
                chunk_id = f"{safe_plan_name}--{state}--qa--{i}"
                
                # Combine content for search
                content = f"Question: {question}\nAnswer: {answer}\nWhy This Matters: {why_matters}"
                
                document = {
                    "chunk_id": chunk_id,
                    "content": content,
                    "parent_id": plan_name,
                    "plan_name": plan_name,
                    "state": state,
                    "qa_questions": [question],
                    "qa_answers": [answer],
                    "qa_why_this_matters": [why_matters],
                    "medical_events": medical_events,
                    "medical_services": medical_services,
                    "medical_costs": medical_costs,
                    "medical_limitations": medical_limitations,
                    "excluded_services": excluded_services,
                    "other_covered_services": other_covered_services
                }
                
                documents.append(document)
            
            # Create a document for medical events
            for i, (event, service, cost, limitation) in enumerate(zip(medical_events, medical_services, medical_costs, medical_limitations)):
                # Create URL-safe chunk ID with double dashes
                chunk_id = f"{safe_plan_name}--{state}--medical--{i}"
                
                # Combine content for search
                content = f"Medical Event: {event}\nService: {service}\nCost: {cost}\nLimitations: {limitation}"
                
                document = {
                    "chunk_id": chunk_id,
                    "content": content,
                    "parent_id": plan_name,
                    "plan_name": plan_name,
                    "state": state,
                    "qa_questions": qa_questions,
                    "qa_answers": qa_answers,
                    "qa_why_this_matters": qa_why_this_matters,
                    "medical_events": [event],
                    "medical_services": [service],
                    "medical_costs": [cost],
                    "medical_limitations": [limitation],
                    "excluded_services": excluded_services,
                    "other_covered_services": other_covered_services
                }
                
                documents.append(document)
            
            # Create a document for excluded services
            if excluded_services:
                # Create URL-safe chunk ID with double dashes
                chunk_id = f"{safe_plan_name}--{state}--excluded"
                
                # Combine content for search
                content = f"Excluded Services: {', '.join(excluded_services)}"
                
                document = {
                    "chunk_id": chunk_id,
                    "content": content,
                    "parent_id": plan_name,
                    "plan_name": plan_name,
                    "state": state,
                    "qa_questions": qa_questions,
                    "qa_answers": qa_answers,
                    "qa_why_this_matters": qa_why_this_matters,
                    "medical_events": medical_events,
                    "medical_services": medical_services,
                    "medical_costs": medical_costs,
                    "medical_limitations": medical_limitations,
                    "excluded_services": excluded_services,
                    "other_covered_services": other_covered_services
                }
                
                documents.append(document)
            
            # Create a document for other covered services
            if other_covered_services:
                # Create URL-safe chunk ID with double dashes
                chunk_id = f"{safe_plan_name}--{state}--covered"
                
                # Combine content for search
                content = f"Other Covered Services: {', '.join(other_covered_services)}"
                
                document = {
                    "chunk_id": chunk_id,
                    "content": content,
                    "parent_id": plan_name,
                    "plan_name": plan_name,
                    "state": state,
                    "qa_questions": qa_questions,
                    "qa_answers": qa_answers,
                    "qa_why_this_matters": qa_why_this_matters,
                    "medical_events": medical_events,
                    "medical_services": medical_services,
                    "medical_costs": medical_costs,
                    "medical_limitations": medical_limitations,
                    "excluded_services": excluded_services,
                    "other_covered_services": other_covered_services
                }
                
                documents.append(document)
        
        return documents
    
    def create_search_index(self, data_dir: str = "data") -> Dict[str, Any]:
        """
        Create and populate the search index with data from JSON files.
        
        Args:
            data_dir: Path to the directory containing JSON files
            
        Returns:
            Dictionary with indexing results
        """
        print("Creating search index...")
        
        # Extract JSON data
        json_data = self._extract_json_files(data_dir)
        
        # Create fields for the index
        fields = self._create_index_fields()
        
        # Create scoring profile
        scoring_profile = self._create_scoring_profile()
        
        # Create semantic configuration
        semantic_config = self._create_semantic_config()
        
        # Create the index
        index = self.healrag.create_search_index(
            fields=fields,
            scoring_profile=scoring_profile,
            semantic_config=semantic_config
        )
        
        # Prepare documents for indexing
        documents = self._prepare_documents_for_indexing(json_data)
        
        # Populate the index
        result = self.healrag.populate_search_index(documents)
        
        print(f"Index created and populated with {result.get('indexed', 0)} documents")
        
        return result
    
    def search(self, query: str, top: Optional[int] = None, 
              filter: Optional[str] = None, select: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search the index with the given query.
        
        Args:
            query: Search query
            top: Number of results to return
            filter: OData filter expression
            select: List of fields to return
            
        Returns:
            List of search results
        """
        top = top or self.top_n_documents
        
        return self.healrag.search(
            query=query,
            top=top,
            filter=filter,
            select=select,
            semantic_search=True
        )
    
    def _format_citations(self, response: str, search_results: List[Dict[str, Any]]) -> str:
        """
        Format the response with citations.
        
        Args:
            response: Generated response
            search_results: List of search results
            
        Returns:
            Formatted response with citations
        """
        # Create a mapping of content to source
        content_to_source = {}
        
        for result in search_results:
            content = result.get("content", "")
            plan_name = result.get("plan_name", "Unknown Plan")
            state = result.get("state", "Unknown State")
            
            content_to_source[content] = f"{plan_name} ({state})"
        
        # Add citations to the response
        formatted_response = response
        
        for content, source in content_to_source.items():
            if content in formatted_response:
                formatted_response = formatted_response.replace(
                    content, 
                    f"{content} [Source: {source}]"
                )
        
        return formatted_response
    
    def query_rag(self, query: str, stream: bool = True, save_conversation: bool = True) -> Union[str, Generator[str, None, None]]:
        """
        Process a query using the RAG workflow.
        
        Args:
            query: User query
            stream: Whether to stream the response
            save_conversation: Whether to save the conversation to the database
            
        Returns:
            Generated response (string or generator for streaming)
        """
        # Search for relevant documents
        search_results = self.search(query)
        
        # Generate a response
        if stream:
            # For streaming, we need to collect the full response
            full_response = ""
            
            # Create a generator that yields chunks and collects the full response
            def response_generator():
                nonlocal full_response
                
                for chunk in self.healrag.generate_response(query, search_results, stream=True):
                    full_response += chunk
                    yield chunk
            
            # Start the generator
            generator = response_generator()
            
            # Save the conversation after streaming is complete
            if save_conversation:
                # We need to wait for the generator to complete
                # This is a limitation of the current implementation
                # In a real application, you would use async/await
                for _ in generator:
                    pass
                
                # Format the response with citations
                formatted_response = self._format_citations(full_response, search_results)
                
                # Create conversation record
                conversation = {
                    "query": query,
                    "search_results": search_results,
                    "response": formatted_response,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Save conversation
                self.healrag.save_conversation(conversation)
            
            return generator
        else:
            # For non-streaming, we can generate the response directly
            response = self.healrag.generate_response(query, search_results, stream=False)
            
            # Format the response with citations
            formatted_response = self._format_citations(response, search_results)
            
            # Save the conversation if requested
            if save_conversation:
                # Create conversation record
                conversation = {
                    "query": query,
                    "search_results": search_results,
                    "response": formatted_response,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Save conversation
                self.healrag.save_conversation(conversation)
            
            return formatted_response
    
    def setup_rag_pipeline(self, data_dir: str = "data") -> Dict[str, Any]:
        """
        Set up the complete RAG pipeline.
        
        This method:
        1. Uploads documents to blob storage
        2. Creates and populates the search index
        
        Args:
            data_dir: Path to the directory containing documents
            
        Returns:
            Dictionary with setup results
        """
        # Upload documents
        upload_result = self.upload_documents(data_dir)
        
        # Create and populate the search index
        index_result = self.create_search_index(data_dir)
        
        return {
            "upload": upload_result,
            "index": index_result
        } 