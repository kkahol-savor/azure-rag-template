"""
RAG Manager Module

This module provides functions for generating responses using Azure OpenAI
with Retrieval-Augmented Generation (RAG) capabilities.
"""

import os
import json
from typing import List, Dict, Any, Optional, Generator, Tuple
from datetime import datetime
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Azure OpenAI configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "10"))
PROGRESS_FILE = os.getenv("RAG_PROGRESS_FILE", "rag_progress.ndjson")

class RAGManager:
    """
    A class to manage RAG operations using Azure OpenAI.
    
    This class provides methods for generating responses to queries
    using retrieved documents as context.
    """
    
    def __init__(
        self,
        endpoint: Optional[str] = None,
        key: Optional[str] = None,
        deployment: Optional[str] = None,
        max_history: Optional[int] = None
    ):
        """
        Initialize the RAGManager.
        
        Args:
            endpoint: Azure OpenAI endpoint
            key: Azure OpenAI key
            deployment: Azure OpenAI deployment name
            max_history: Maximum number of conversation history items to keep
        """
        self.endpoint = endpoint or AZURE_OPENAI_ENDPOINT
        self.key = key or AZURE_OPENAI_KEY
        self.deployment = deployment or AZURE_OPENAI_DEPLOYMENT
        self.max_history = max_history or MAX_HISTORY
        
        if not self.endpoint or not self.key:
            raise ValueError("Azure OpenAI endpoint and key are required")
        
        self.client = AzureOpenAI(
            api_key=self.key,
            api_version="2023-05-15",
            azure_endpoint=self.endpoint
        )
        
        self.conversation_history = []
    
    def generate_response(
        self,
        query: str,
        context: List[Dict[str, Any]],
        stream: bool = True
    ) -> Union[str, Generator[str, None, None]]:
        """
        Generate a response to a query using the provided context.
        
        Args:
            query: User query
            context: List of retrieved documents to use as context
            stream: Whether to stream the response
            
        Returns:
            Generated response (string or generator for streaming)
        """
        # Format context for the prompt
        context_text = self._format_context(context)
        
        # Create the system message
        system_message = {
            "role": "system",
            "content": (
                "You are a helpful assistant that provides accurate information based on the context provided. "
                "If the answer cannot be found in the context, say so. "
                "Do not make up information. "
                "Use the context to answer the user's question."
            )
        }
        
        # Create the user message with context
        user_message = {
            "role": "user",
            "content": f"Context:\n{context_text}\n\nQuestion: {query}"
        }
        
        # Prepare messages for the API call
        messages = [system_message]
        
        # Add conversation history (limited to max_history)
        for item in self.conversation_history[-self.max_history:]:
            messages.append(item)
        
        # Add the current query
        messages.append(user_message)
        
        try:
            # Call the Azure OpenAI API
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                stream=stream
            )
            
            # Process the response
            if stream:
                return self._process_streaming_response(response, query, context)
            else:
                return self._process_complete_response(response, query, context)
                
        except Exception as e:
            # Record error
            self._record_progress({
                "operation": "generate_response",
                "query": query,
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e)
            })
            
            raise
    
    def _format_context(self, context: List[Dict[str, Any]]) -> str:
        """
        Format the context for use in the prompt.
        
        Args:
            context: List of retrieved documents
            
        Returns:
            Formatted context string
        """
        formatted_context = []
        
        for i, doc in enumerate(context):
            # Extract relevant fields
            doc_id = doc.get("id", f"Document {i+1}")
            content = []
            
            # Add plan name and state if available
            if "plan_name" in doc:
                content.append(f"Plan: {doc['plan_name']}")
            if "state" in doc:
                content.append(f"State: {doc['state']}")
            
            # Add Q&A data if available
            if "qa_data" in doc and doc["qa_data"]:
                content.append("Q&A Information:")
                for qa in doc["qa_data"]:
                    if "question" in qa and "answer" in qa:
                        content.append(f"Q: {qa['question']}")
                        content.append(f"A: {qa['answer']}")
            
            # Add medical events data if available
            if "medical_events_data" in doc and doc["medical_events_data"]:
                content.append("Medical Events Information:")
                for event in doc["medical_events_data"]:
                    if "common_medical_event" in event:
                        content.append(f"Event: {event['common_medical_event']}")
                    if "services_you_may_need" in event:
                        content.append(f"Services: {event['services_you_may_need']}")
                    if "what_you_will_pay" in event:
                        content.append(f"Cost: {event['what_you_will_pay']}")
            
            # Add excluded services if available
            if "excluded_services" in doc and doc["excluded_services"]:
                content.append(f"Excluded Services: {doc['excluded_services']}")
            
            # Add other covered services if available
            if "other_covered_services" in doc and doc["other_covered_services"]:
                content.append(f"Other Covered Services: {doc['other_covered_services']}")
            
            # Add the formatted document to the context
            formatted_context.append(f"--- Document {i+1} ({doc_id}) ---\n" + "\n".join(content))
        
        return "\n\n".join(formatted_context)
    
    def _process_streaming_response(
        self,
        response: Any,
        query: str,
        context: List[Dict[str, Any]]
    ) -> Generator[str, None, None]:
        """
        Process a streaming response from the API.
        
        Args:
            response: Streaming response from the API
            query: User query
            context: List of retrieved documents
            
        Returns:
            Generator yielding response chunks
        """
        full_response = ""
        
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield content
        
        # Update conversation history
        self._update_conversation_history(query, full_response)
        
        # Record progress
        self._record_progress({
            "operation": "generate_response",
            "query": query,
            "response_length": len(full_response),
            "timestamp": datetime.now().isoformat(),
            "status": "success"
        })
    
    def _process_complete_response(
        self,
        response: Any,
        query: str,
        context: List[Dict[str, Any]]
    ) -> str:
        """
        Process a complete response from the API.
        
        Args:
            response: Complete response from the API
            query: User query
            context: List of retrieved documents
            
        Returns:
            Complete response string
        """
        if response.choices and response.choices[0].message.content:
            content = response.choices[0].message.content
            
            # Update conversation history
            self._update_conversation_history(query, content)
            
            # Record progress
            self._record_progress({
                "operation": "generate_response",
                "query": query,
                "response_length": len(content),
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            })
            
            return content
        
        return "No response generated"
    
    def _update_conversation_history(self, query: str, response: str) -> None:
        """
        Update the conversation history.
        
        Args:
            query: User query
            response: Assistant response
        """
        # Add the query and response to the history
        self.conversation_history.append({"role": "user", "content": query})
        self.conversation_history.append({"role": "assistant", "content": response})
        
        # Trim the history if it exceeds the maximum
        if len(self.conversation_history) > self.max_history * 2:  # * 2 because each exchange has 2 messages
            self.conversation_history = self.conversation_history[-self.max_history * 2:]
    
    def clear_history(self) -> None:
        """
        Clear the conversation history.
        """
        self.conversation_history = []
    
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
    
    def get_last_operation(self) -> Optional[Dict[str, Any]]:
        """
        Get the last recorded operation.
        
        Returns:
            Last operation record or None
        """
        records = self.get_progress()
        return records[-1] if records else None 