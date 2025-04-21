"""
Database Manager Module

This module provides functions for managing Cosmos DB operations.
It includes CRUD operations for containers and items, and tracks progress using NDJSON.
"""

import os
import json
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosHttpResponseError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Cosmos DB configuration
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DATABASE = os.getenv("COSMOS_DATABASE", "insurance-db")
COSMOS_CONTAINER = os.getenv("COSMOS_CONTAINER", "conversations")
COSMOS_PARTITION_KEY = os.getenv("COSMOS_PARTITION_KEY", "/user_id")
PROGRESS_FILE = os.getenv("DB_PROGRESS_FILE", "db_progress.ndjson")

class DBManager:
    """
    A class to manage Cosmos DB operations.
    
    This class provides methods for creating, reading, updating, and deleting
    databases, containers, and items, as well as tracking progress of operations.
    """
    
    def __init__(
        self,
        endpoint: Optional[str] = None,
        key: Optional[str] = None,
        database: Optional[str] = None,
        container: Optional[str] = None
    ):
        """
        Initialize the DBManager.
        
        Args:
            endpoint: Cosmos DB endpoint
            key: Cosmos DB key
            database: Name of the database to use
            container: Name of the container to use
        """
        self.endpoint = endpoint or COSMOS_ENDPOINT
        self.key = key or COSMOS_KEY
        self.database_name = database or COSMOS_DATABASE
        self.container_name = container or COSMOS_CONTAINER
        
        if not self.endpoint or not self.key:
            raise ValueError("Cosmos DB endpoint and key are required")
        
        self.client = CosmosClient(self.endpoint, self.key)
        self.database = None
        self.container = None
        self._ensure_database_exists()
        self._ensure_container_exists()
    
    def _ensure_database_exists(self) -> None:
        """
        Ensure the database exists, create it if it doesn't.
        """
        try:
            self.database = self.client.get_database_client(self.database_name)
            self.database.read()
        except CosmosHttpResponseError:
            self.database = self.client.create_database(self.database_name)
            print(f"Database '{self.database_name}' created successfully")
    
    def _ensure_container_exists(self) -> None:
        """
        Ensure the container exists, create it if it doesn't.
        """
        try:
            self.container = self.database.get_container_client(self.container_name)
            self.container.read()
        except CosmosHttpResponseError:
            self.container = self.database.create_container(
                id=self.container_name,
                partition_key=PartitionKey(path=COSMOS_PARTITION_KEY)
            )
            print(f"Container '{self.container_name}' created successfully with partition key '{COSMOS_PARTITION_KEY}'")
    
    def list_databases(self) -> List[str]:
        """
        List all databases in the Cosmos DB account.
        
        Returns:
            List of database names
        """
        databases = self.client.list_databases()
        return [db["id"] for db in databases]
    
    def create_database(self, database_name: str) -> Any:
        """
        Create a new database.
        
        Args:
            database_name: Name of the database to create
            
        Returns:
            Created database client
        """
        try:
            database = self.client.create_database(database_name)
            print(f"Database '{database_name}' created successfully")
            
            # Record progress
            self._record_progress({
                "operation": "create_database",
                "database_name": database_name,
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            })
            
            return database
        except CosmosHttpResponseError as e:
            # Record failure
            self._record_progress({
                "operation": "create_database",
                "database_name": database_name,
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e)
            })
            
            print(f"Failed to create database: {str(e)}")
            return None
    
    def delete_database(self, database_name: str) -> bool:
        """
        Delete a database.
        
        Args:
            database_name: Name of the database to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            database = self.client.get_database_client(database_name)
            database.delete()
            print(f"Database '{database_name}' deleted successfully")
            
            # Record progress
            self._record_progress({
                "operation": "delete_database",
                "database_name": database_name,
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            })
            
            return True
        except CosmosHttpResponseError as e:
            # Record failure
            self._record_progress({
                "operation": "delete_database",
                "database_name": database_name,
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e)
            })
            
            print(f"Failed to delete database: {str(e)}")
            return False
    
    def list_containers(self) -> List[str]:
        """
        List all containers in the current database.
        
        Returns:
            List of container names
        """
        containers = self.database.list_containers()
        return [container["id"] for container in containers]
    
    def create_container(self, container_name: str, partition_key_path: Optional[str] = None) -> Any:
        """
        Create a new container.
        
        Args:
            container_name: Name of the container to create
            partition_key_path: Path for the partition key (defaults to the one in environment)
            
        Returns:
            Created container client
        """
        try:
            partition_key = partition_key_path or COSMOS_PARTITION_KEY
            container = self.database.create_container(
                id=container_name,
                partition_key=PartitionKey(path=partition_key)
            )
            print(f"Container '{container_name}' created successfully with partition key '{partition_key}'")
            
            # Record progress
            self._record_progress({
                "operation": "create_container",
                "database_name": self.database_name,
                "container_name": container_name,
                "partition_key": partition_key,
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            })
            
            return container
        except CosmosHttpResponseError as e:
            # Record failure
            self._record_progress({
                "operation": "create_container",
                "database_name": self.database_name,
                "container_name": container_name,
                "partition_key": partition_key_path or COSMOS_PARTITION_KEY,
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e)
            })
            
            print(f"Failed to create container: {str(e)}")
            return None
    
    def delete_container(self, container_name: str) -> bool:
        """
        Delete a container.
        
        Args:
            container_name: Name of the container to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            container = self.database.get_container_client(container_name)
            container.delete()
            print(f"Container '{container_name}' deleted successfully")
            
            # Record progress
            self._record_progress({
                "operation": "delete_container",
                "database_name": self.database_name,
                "container_name": container_name,
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            })
            
            return True
        except CosmosHttpResponseError as e:
            # Record failure
            self._record_progress({
                "operation": "delete_container",
                "database_name": self.database_name,
                "container_name": container_name,
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e)
            })
            
            print(f"Failed to delete container: {str(e)}")
            return False
    
    def create_item(self, item: Dict[str, Any], container_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new item in the container.
        
        Args:
            item: Item to create
            container_name: Name of the container to use (defaults to the one set in constructor)
            
        Returns:
            Created item
        """
        container = self.container
        if container_name:
            container = self.database.get_container_client(container_name)
        
        try:
            result = container.create_item(body=item)
            print(f"Item created successfully with id: {result['id']}")
            
            # Record progress
            self._record_progress({
                "operation": "create_item",
                "database_name": self.database_name,
                "container_name": container_name or self.container_name,
                "item_id": result["id"],
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            })
            
            return result
        except CosmosHttpResponseError as e:
            # Record failure
            self._record_progress({
                "operation": "create_item",
                "database_name": self.database_name,
                "container_name": container_name or self.container_name,
                "item_id": item.get("id", "unknown"),
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e)
            })
            
            print(f"Failed to create item: {str(e)}")
            raise
    
    def read_item(self, item_id: str, partition_key: str, container_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Read an item from the container.
        
        Args:
            item_id: ID of the item to read
            partition_key: Partition key of the item
            container_name: Name of the container to use (defaults to the one set in constructor)
            
        Returns:
            Retrieved item
        """
        container = self.container
        if container_name:
            container = self.database.get_container_client(container_name)
        
        try:
            result = container.read_item(item=item_id, partition_key=partition_key)
            
            # Record progress
            self._record_progress({
                "operation": "read_item",
                "database_name": self.database_name,
                "container_name": container_name or self.container_name,
                "item_id": item_id,
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            })
            
            return result
        except CosmosHttpResponseError as e:
            # Record failure
            self._record_progress({
                "operation": "read_item",
                "database_name": self.database_name,
                "container_name": container_name or self.container_name,
                "item_id": item_id,
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e)
            })
            
            print(f"Failed to read item: {str(e)}")
            raise
    
    def update_item(self, item: Dict[str, Any], container_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Update an item in the container.
        
        Args:
            item: Item to update
            container_name: Name of the container to use (defaults to the one set in constructor)
            
        Returns:
            Updated item
        """
        container = self.container
        if container_name:
            container = self.database.get_container_client(container_name)
        
        try:
            result = container.replace_item(item=item["id"], body=item)
            print(f"Item updated successfully with id: {result['id']}")
            
            # Record progress
            self._record_progress({
                "operation": "update_item",
                "database_name": self.database_name,
                "container_name": container_name or self.container_name,
                "item_id": result["id"],
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            })
            
            return result
        except CosmosHttpResponseError as e:
            # Record failure
            self._record_progress({
                "operation": "update_item",
                "database_name": self.database_name,
                "container_name": container_name or self.container_name,
                "item_id": item.get("id", "unknown"),
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e)
            })
            
            print(f"Failed to update item: {str(e)}")
            raise
    
    def delete_item(self, item_id: str, partition_key: str, container_name: Optional[str] = None) -> bool:
        """
        Delete an item from the container.
        
        Args:
            item_id: ID of the item to delete
            partition_key: Partition key of the item
            container_name: Name of the container to use (defaults to the one set in constructor)
            
        Returns:
            True if successful, False otherwise
        """
        container = self.container
        if container_name:
            container = self.database.get_container_client(container_name)
        
        try:
            container.delete_item(item=item_id, partition_key=partition_key)
            print(f"Item deleted successfully with id: {item_id}")
            
            # Record progress
            self._record_progress({
                "operation": "delete_item",
                "database_name": self.database_name,
                "container_name": container_name or self.container_name,
                "item_id": item_id,
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            })
            
            return True
        except CosmosHttpResponseError as e:
            # Record failure
            self._record_progress({
                "operation": "delete_item",
                "database_name": self.database_name,
                "container_name": container_name or self.container_name,
                "item_id": item_id,
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e)
            })
            
            print(f"Failed to delete item: {str(e)}")
            return False
    
    def query_items(self, query: str, parameters: Optional[List[Dict[str, Any]]] = None, 
                   container_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query items in the container.
        
        Args:
            query: SQL query
            parameters: Query parameters
            container_name: Name of the container to use (defaults to the one set in constructor)
            
        Returns:
            List of items matching the query
        """
        container = self.container
        if container_name:
            container = self.database.get_container_client(container_name)
        
        try:
            items = list(container.query_items(
                query=query,
                parameters=parameters or [],
                enable_cross_partition_query=True
            ))
            
            # Record progress
            self._record_progress({
                "operation": "query_items",
                "database_name": self.database_name,
                "container_name": container_name or self.container_name,
                "query": query,
                "result_count": len(items),
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            })
            
            return items
        except CosmosHttpResponseError as e:
            # Record failure
            self._record_progress({
                "operation": "query_items",
                "database_name": self.database_name,
                "container_name": container_name or self.container_name,
                "query": query,
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e)
            })
            
            print(f"Failed to query items: {str(e)}")
            return []
    
    def save_conversation(self, conversation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save a conversation to the database.
        
        Args:
            conversation: Conversation to save
            
        Returns:
            Saved conversation
        """
        # Ensure the conversation has an ID
        if "id" not in conversation:
            conversation["id"] = f"conv_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Add timestamp if not present
        if "timestamp" not in conversation:
            conversation["timestamp"] = datetime.now().isoformat()
        
        return self.create_item(conversation)
    
    def get_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """
        Get a conversation from the database.
        
        Args:
            conversation_id: ID of the conversation to retrieve
            
        Returns:
            Retrieved conversation or None if not found
        """
        try:
            # Use the conversation_id as both the item_id and partition_key
            # This assumes the conversation was saved with the same ID as the partition key
            return self.read_item(item_id=conversation_id, partition_key=conversation_id)
        except CosmosHttpResponseError as e:
            if e.status_code == 404:  # Not found
                print(f"Conversation with ID {conversation_id} not found")
                return None
            else:
                # Re-raise other errors
                raise
    
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
            operation_type: Filter by operation type
            
        Returns:
            Last operation record or None
        """
        records = self.get_progress()
        
        if operation_type:
            records = [r for r in records if r.get("operation") == operation_type]
        
        return records[-1] if records else None 