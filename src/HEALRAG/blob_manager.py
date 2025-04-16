"""
Blob Manager Module

This module provides functions for managing Azure Blob Storage operations.
It includes CRUD operations for containers and files, and tracks progress using NDJSON.
"""

import os
import json
import time
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from azure.storage.blob import BlobServiceClient, ContainerClient, BlobClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Azure Blob Storage configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER", "insurance-documents")
PROGRESS_FILE = os.getenv("BLOB_PROGRESS_FILE", "blob_progress.ndjson")

class BlobManager:
    """
    A class to manage Azure Blob Storage operations.
    
    This class provides methods for creating, reading, updating, and deleting
    containers and blobs, as well as tracking progress of operations.
    """
    
    def __init__(self, connection_string: Optional[str] = None, container_name: Optional[str] = None):
        """
        Initialize the BlobManager.
        
        Args:
            connection_string: Azure Storage connection string
            container_name: Name of the container to use
        """
        self.connection_string = connection_string or AZURE_STORAGE_CONNECTION_STRING
        self.container_name = container_name or AZURE_STORAGE_CONTAINER
        
        if not self.connection_string:
            raise ValueError("Azure Storage connection string is required")
        
        self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
        self.container_client = None
        self._ensure_container_exists()
    
    def _ensure_container_exists(self) -> None:
        """
        Ensure the container exists, create it if it doesn't.
        """
        try:
            self.container_client = self.blob_service_client.get_container_client(self.container_name)
            self.container_client.get_container_properties()
        except ResourceNotFoundError:
            self.container_client = self.blob_service_client.create_container(self.container_name)
            print(f"Container '{self.container_name}' created successfully")
    
    def list_containers(self) -> List[str]:
        """
        List all containers in the storage account.
        
        Returns:
            List of container names
        """
        containers = self.blob_service_client.list_containers()
        return [container.name for container in containers]
    
    def create_container(self, container_name: str) -> ContainerClient:
        """
        Create a new container.
        
        Args:
            container_name: Name of the container to create
            
        Returns:
            ContainerClient for the created container
        """
        try:
            container_client = self.blob_service_client.create_container(container_name)
            print(f"Container '{container_name}' created successfully")
            return container_client
        except ResourceExistsError:
            print(f"Container '{container_name}' already exists")
            return self.blob_service_client.get_container_client(container_name)
    
    def delete_container(self, container_name: str) -> bool:
        """
        Delete a container.
        
        Args:
            container_name: Name of the container to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            container_client = self.blob_service_client.get_container_client(container_name)
            container_client.delete_container()
            print(f"Container '{container_name}' deleted successfully")
            return True
        except ResourceNotFoundError:
            print(f"Container '{container_name}' not found")
            return False
    
    def upload_file(self, file_path: str, blob_name: Optional[str] = None) -> Tuple[bool, str]:
        """
        Upload a file to blob storage.
        
        Args:
            file_path: Path to the file to upload
            blob_name: Name to give the blob (defaults to file name)
            
        Returns:
            Tuple of (success, message)
        """
        if not os.path.exists(file_path):
            return False, f"File '{file_path}' not found"
        
        if blob_name is None:
            blob_name = os.path.basename(file_path)
        
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            with open(file_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)
            
            # Record progress
            self._record_progress({
                "operation": "upload",
                "file_path": file_path,
                "blob_name": blob_name,
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            })
            
            return True, f"File '{file_path}' uploaded successfully as '{blob_name}'"
        except Exception as e:
            # Record failure
            self._record_progress({
                "operation": "upload",
                "file_path": file_path,
                "blob_name": blob_name,
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e)
            })
            
            return False, f"Failed to upload file: {str(e)}"
    
    def upload_directory(self, directory_path: str, recursive: bool = True) -> Dict[str, Any]:
        """
        Upload all files in a directory to blob storage.
        
        Args:
            directory_path: Path to the directory to upload
            recursive: Whether to upload subdirectories recursively
            
        Returns:
            Dictionary with upload results
        """
        if not os.path.isdir(directory_path):
            return {"success": False, "message": f"Directory '{directory_path}' not found"}
        
        results = {
            "success": True,
            "total": 0,
            "uploaded": 0,
            "failed": 0,
            "errors": []
        }
        
        for root, _, files in os.walk(directory_path):
            if not recursive and root != directory_path:
                continue
                
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, directory_path)
                blob_name = relative_path.replace("\\", "/")
                
                success, message = self.upload_file(file_path, blob_name)
                results["total"] += 1
                
                if success:
                    results["uploaded"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({"file": file_path, "error": message})
        
        return results
    
    def download_file(self, blob_name: str, file_path: Optional[str] = None) -> Tuple[bool, str]:
        """
        Download a blob to a file.
        
        Args:
            blob_name: Name of the blob to download
            file_path: Path to save the file (defaults to blob name)
            
        Returns:
            Tuple of (success, message)
        """
        if file_path is None:
            file_path = blob_name
        
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            with open(file_path, "wb") as file:
                data = blob_client.download_blob()
                file.write(data.readall())
            
            # Record progress
            self._record_progress({
                "operation": "download",
                "blob_name": blob_name,
                "file_path": file_path,
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            })
            
            return True, f"Blob '{blob_name}' downloaded successfully to '{file_path}'"
        except ResourceNotFoundError:
            return False, f"Blob '{blob_name}' not found"
        except Exception as e:
            # Record failure
            self._record_progress({
                "operation": "download",
                "blob_name": blob_name,
                "file_path": file_path,
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e)
            })
            
            return False, f"Failed to download blob: {str(e)}"
    
    def list_blobs(self, name_starts_with: Optional[str] = None) -> List[str]:
        """
        List all blobs in the container.
        
        Args:
            name_starts_with: Filter blobs by name prefix
            
        Returns:
            List of blob names
        """
        blobs = self.container_client.list_blobs(name_starts_with=name_starts_with)
        return [blob.name for blob in blobs]
    
    def delete_blob(self, blob_name: str) -> Tuple[bool, str]:
        """
        Delete a blob.
        
        Args:
            blob_name: Name of the blob to delete
            
        Returns:
            Tuple of (success, message)
        """
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            blob_client.delete_blob()
            
            # Record progress
            self._record_progress({
                "operation": "delete",
                "blob_name": blob_name,
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            })
            
            return True, f"Blob '{blob_name}' deleted successfully"
        except ResourceNotFoundError:
            return False, f"Blob '{blob_name}' not found"
        except Exception as e:
            # Record failure
            self._record_progress({
                "operation": "delete",
                "blob_name": blob_name,
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e)
            })
            
            return False, f"Failed to delete blob: {str(e)}"
    
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
            operation_type: Filter by operation type (upload, download, delete)
            
        Returns:
            Last operation record or None
        """
        records = self.get_progress()
        
        if operation_type:
            records = [r for r in records if r.get("operation") == operation_type]
        
        return records[-1] if records else None 