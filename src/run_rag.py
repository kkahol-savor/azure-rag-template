#!/usr/bin/env python3
"""
RAG Pipeline Runner

This script demonstrates how to use the RAG_CREATION class to:
1. Set up the RAG pipeline (upload documents and create search index)
2. Process queries using the RAG workflow
3. Generate responses with citations
"""

import os
import sys
from dotenv import load_dotenv

from RAG_CREATION import RAGCreation

# Load environment variables
load_dotenv()

def setup_pipeline(data_dir: str = None) -> RAGCreation:
    """
    Set up the RAG pipeline.
    
    Args:
        data_dir: Path to the directory containing documents
        
    Returns:
        Initialized RAGCreation instance
    """
    # Use data_dir from environment variable if not provided
    data_dir = data_dir or os.getenv("DATA_DIR", "data")
    
    print("Setting up RAG pipeline...")
    
    # Initialize RAG creation
    rag = RAGCreation()
    
    # Set up the pipeline
    result = rag.setup_rag_pipeline(data_dir)
    
    print("RAG pipeline setup complete!")
    print(f"Uploaded {result['upload'].get('uploaded', 0)} documents")
    print(f"Indexed {result['index'].get('indexed', 0)} documents")
    
    return rag

def process_query(rag: RAGCreation, query: str, stream: bool = None) -> None:
    """
    Process a query using the RAG workflow.
    
    Args:
        rag: Initialized RAGCreation instance
        query: User query
        stream: Whether to stream the response
    """
    # Use stream from environment variable if not provided
    stream = stream if stream is not None else os.getenv("STREAM_RESPONSES", "true").lower() == "true"
    
    print(f"\nProcessing query: {query}")
    
    if stream:
        print("\nGenerating streaming response...")
        print("-" * 80)
        
        # Process the query with streaming
        for chunk in rag.query_rag(query, stream=True):
            print(chunk, end="", flush=True)
        
        print("\n" + "-" * 80)
    else:
        print("\nGenerating response...")
        print("-" * 80)
        
        # Process the query without streaming
        response = rag.query_rag(query, stream=False)
        print(response)
        
        print("-" * 80)

def main():
    """
    Main function to run the RAG pipeline.
    """
    # Check if we need to set up the pipeline
    setup_pipeline_flag = os.getenv("SETUP_PIPELINE", "false").lower() == "true"
    
    if setup_pipeline_flag:
        rag = setup_pipeline()
    else:
        rag = RAGCreation()
    
    # Interactive mode
    print("\nEntering interactive mode. Type 'exit' to quit.")
    
    while True:
        query = input("\nEnter your query: ")
        
        if query.lower() in ["exit", "quit", "q"]:
            break
        
        process_query(rag, query)

if __name__ == "__main__":
    main() 