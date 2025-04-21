"""
RAG Manager Module

This module provides functions for generating responses using Azure OpenAI
with Retrieval-Augmented Generation (RAG) capabilities.
"""

import os
import json
from typing import List, Dict, Any, Optional, Generator, Tuple, Union
from datetime import datetime
from openai import AzureOpenAI
from dotenv import load_dotenv
import uuid
from azure.cosmos import CosmosClient

# Load environment variables
load_dotenv()

# Azure OpenAI configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
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
        
        # Initialize Cosmos DB client and container using environment variables
        self.cosmos_endpoint = os.getenv("COSMOS_ENDPOINT")
        self.cosmos_key = os.getenv("COSMOS_KEY")
        self.cosmos_database = os.getenv("COSMOS_DATABASE")
        self.cosmos_container_name = os.getenv("COSMOS_CONTAINER")
        if self.cosmos_endpoint and self.cosmos_key and self.cosmos_database and self.cosmos_container_name:
            try:
                self.cosmos_client = CosmosClient(self.cosmos_endpoint, {'masterKey': self.cosmos_key})
                self.cosmos_container = self.cosmos_client.get_database_client(self.cosmos_database).get_container_client(self.cosmos_container_name)
            except Exception as e:
                print("Cosmos DB initialization error:", e)
                self.cosmos_client = None
                self.cosmos_container = None
        else:
            self.cosmos_client = None
            self.cosmos_container = None
    
    def generate_response(
        self,
        query: str,
        context: List[Dict[str, Any]],
        stream: bool = True,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.2,
        top_p: float = 0.95,
    ) -> Union[str, Generator[str, None, None]]:
        """
        Generate a response to *query* using retrieved *context*.
        """
        history = history or self.conversation_history

        # 1. Flatten the retrieved docs
        context_text = self._format_context(context)

        # (optional) write to disk for debugging
        with open("formatted_context.txt", "w") as fc:
            fc.write(context_text)

        # 2. Build the message list (new helper)
        messages = self._build_messages(
            query=query,
            context_text=context_text,
            history=history,
            system_prompt=system_prompt,
        )
        # write messages to disk for debugging
        with open("messages.txt", "w") as m:
            for message in messages:
                m.write(json.dumps(message) + "\n")
        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                stream=stream,
                temperature=temperature,
                top_p=top_p,
            )

            if stream:
                return self._process_streaming_response(response, query, context)
            return self._process_complete_response(response, query, context)

        except Exception as e:
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
            content_lines = []
            
            # Add plan name and state if available
            if "plan_name" in doc:
                content_lines.append(f"Plan: {doc['plan_name']}")
            if "state" in doc:
                content_lines.append(f"State: {doc['state']}")
            
            # Include full content if available
            if "content" in doc and doc["content"]:
                content_lines.append(f"Content: {doc['content']}")
            
            # Include Q&A information if available
            if "qa_data" in doc and doc["qa_data"]:
                content_lines.append("Q&A Information:")
                content_lines.append(doc["qa_data"])
            
            # Add medical events data if available
            if "medical_events_data" in doc and doc["medical_events_data"]:
                content_lines.append("Medical Events Information:")
                for event in doc["medical_events_data"]:
                    if "common_medical_event" in event:
                        content_lines.append(f"Event: {event['common_medical_event']}")
                    if "services_you_may_need" in event:
                        content_lines.append(f"Services: {event['services_you_may_need']}")
                    if "what_you_will_pay" in event:
                        content_lines.append(f"Cost: {event['what_you_will_pay']}")
            
            # Add excluded services if available
            if "excluded_services" in doc and doc["excluded_services"]:
                content_lines.append(f"Excluded Services: {doc['excluded_services']}")
            
            # Add other covered services if available
            if "other_covered_services" in doc and doc["other_covered_services"]:
                content_lines.append(f"Other Covered Services: {doc['other_covered_services']}")
            
            # Add the formatted document to the context
            formatted_context.append(f"--- Document {i+1} ({doc_id}) ---\n" + "\n".join(content_lines))
        
        #write formatted context to file
        with open("formatted_context.txt", "w") as f:
            for line in formatted_context:
                f.write(line + "\n")
        
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
                # Format the response as a JSON object with the content
                yield json.dumps({"response": content}) + "\n"
        
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
    
    def _update_conversation_history(self, query: str, response: str, session_id: Optional[str] = None) -> None:
        """
        Update the conversation history and store the conversation record in Cosmos DB.
        
        Args:
            query: User query
            response: Assistant response
            session_id: Optional session identifier
        """
        # Add exchange to in-memory history
        self.conversation_history.append({"role": "user", "content": query})
        self.conversation_history.append({"role": "assistant", "content": response})
        
        # Trim history if it exceeds the maximum
        if len(self.conversation_history) > self.max_history * 2:
            self.conversation_history = self.conversation_history[-self.max_history * 2:]
        
        # Create a conversation record, including session_id if provided
        conversation_record = {
            "id": str(uuid.uuid4()),
            "session_id": session_id if session_id is not None else str(uuid.uuid4()),
            "query": query,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
        
        # Store conversation record in Cosmos DB if available
        if self.cosmos_container:
            try:
                self.cosmos_container.create_item(body=conversation_record)
            except Exception as e:
                print("Error storing conversation in Cosmos DB:", e)
    
    def clear_history(self) -> None:
        """
        Clear the conversation history.
        """
        self.conversation_history = []
    
    def _build_messages(
        self,
        query: str,
        context_text: str,
        history: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        # Updated base_prompt to require citations in the answer
        print(f"system_prompt is: {system_prompt}")
        base_prompt = system_prompt or (
            "You are a helpful assistant that answers questions about insurance plans using the provided Context. "
            "Answer the question ONLY with information from the Context. If the answer is not present, say 'I don't know.' "
            "Include citations in your answer by referencing the document numbers and plan names from the Context."
        )
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": base_prompt},
            {"role": "system", "name": "context", "content": context_text},
        ]
        messages.extend(history[-self.max_history * 2 :])
        messages.append({"role": "user", "content": query})
        return messages
    
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
    
    def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for text using Azure OpenAI.
        
        Args:
            text: Text to get embedding for
            
        Returns:
            List of floats representing the embedding
        """
        try:
            response = self.client.embeddings.create(
                model=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error getting embedding: {str(e)}")
            return []