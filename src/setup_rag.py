"""
Setup script for initializing the RAG system.
"""

from RAG_CREATION import RAGCreation

def main():
    # Initialize RAG Creation
    rag = RAGCreation()
    
    # Setup the complete RAG pipeline
    print("Setting up RAG pipeline...")
    result = rag.setup_rag_pipeline()
    
    # Interpret results
    upload_status = "Failed"
    if result.get('upload', {}).get('total', 0) > 0:
        if result.get('upload', {}).get('uploaded', 0) > 0:
            upload_status = "Success"
        elif result.get('upload', {}).get('skipped', 0) > 0:
            upload_status = "PASS (Documents already exist)"
    
    index_status = "Failed"
    if result.get('index', {}).get('total', 0) > 0:
        index_status = "Success"
    
    pipeline_ready = index_status == "Success"
    
    # Print results
    print("\nSetup Results:")
    print(f"Documents uploaded: {upload_status}")
    print(f"Search index created: {index_status}")
    print(f"Pipeline ready: {'Yes' if pipeline_ready else 'No'}")
    
    # Print detailed statistics
    print("\nDetailed Statistics:")
    print(f"Total documents indexed: {result.get('index', {}).get('total', 0)}")
    print(f"Documents uploaded: {result.get('upload', {}).get('uploaded', 0)}")
    print(f"Documents skipped (already exist): {result.get('upload', {}).get('skipped', 0)}")
    print(f"Failed uploads: {result.get('upload', {}).get('failed', 0)}")

if __name__ == "__main__":
    main() 