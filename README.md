# Point32 Insurance RAG Assistant

An intelligent insurance plan assistant built using the HEALRAG library. This project provides a complete solution for insurance document retrieval and question answering using Azure services.

## Overview

This project leverages the HEALRAG library to create a specialized RAG (Retrieval-Augmented Generation) system for insurance plans. It allows users to ask questions about their insurance coverage, benefits, and policies, and receive accurate responses based on the actual insurance documents.

## Features

- **Insurance Document Management**: Upload and manage insurance documents in Azure Blob Storage
- **Semantic Search**: Find relevant insurance information using Azure Cognitive Search
  - Natural language queries
  - Semantic understanding of insurance terms
  - Filter by plan, state, or document type
  - Combined SBC and SOB document search
- **Intelligent Responses**: Generate accurate answers to insurance-related questions using Azure OpenAI
- **Conversation History**: Store and retrieve user conversations using Cosmos DB
- **Progress Tracking**: Monitor operations using NDJSON format
- **Type Hints**: Full type support for better code completion and error detection
- **Error Handling**: Comprehensive error handling and logging
- **Batch Processing**: Support for batch operations on insurance documents
- **Streaming Support**: Stream responses for real-time interactions
- **Web Interface**: User-friendly web application for interacting with the system

## Search Functionality

The system provides powerful search capabilities through Azure Cognitive Search:

### Basic Search
```python
from HEALRAG.main import HEALRAG

# Initialize HEALRAG
healrag = HEALRAG()

# Simple search
results = healrag.search(
    query="What are the covered services for diabetes?",
    top=5  # Number of results to return
)
```

### Advanced Search
```python
# Search with filters and field selection
results = healrag.search(
    query="What are the covered services for diabetes?",
    top=5,
    filter="state eq 'MA'",  # Filter by state
    select=["plan_name", "state", "content", "qa_questions", "qa_answers"]  # Fields to return
)
```

### Search Features
- **Semantic Search**: Understands natural language queries about insurance
- **Field Filtering**: Filter results by any indexed field (plan_name, state, file_type)
- **Field Selection**: Choose which fields to return in results
- **Combined Documents**: Each result contains data from both SBC and SOB files
- **Structured Data**: Access specific fields like:
  - Q&A data (questions, answers, why it matters)
  - Medical events (events, services, costs, limitations)
  - Excluded services
  - Other covered services

### Search Results
Each search result includes:
- Plan name and state
- Combined content from SBC and SOB documents
- Structured data fields
- Relevance score
- Source document references

## Installation

1. Clone the repository:
```bash
git clone https://github.com/kkahol-savor/azure-rag-template.git
cd azure-rag-template
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure Azure credentials:
Create a `.env` file in the root directory with the following variables:

```env
# Azure Blob Storage Configuration
AZURE_STORAGE_CONNECTION_STRING=your_connection_string
BLOB_PROGRESS_FILE=blob_progress.ndjson

# Azure Cognitive Search Configuration
AZURE_SEARCH_ENDPOINT=your_search_endpoint
AZURE_SEARCH_KEY=your_search_key
AZURE_SEARCH_INDEX_NAME=insurance-plans
TOP_N_DOCUMENTS=5
SEARCH_PROGRESS_FILE=search_progress.ndjson

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=your_openai_endpoint
AZURE_OPENAI_KEY=your_openai_key
AZURE_OPENAI_DEPLOYMENT=your_deployment_name
MAX_HISTORY=10
RAG_PROGRESS_FILE=rag_progress.ndjson

# Cosmos DB Configuration
COSMOS_ENDPOINT=your_cosmos_endpoint
COSMOS_KEY=your_cosmos_key
COSMOS_DATABASE=insurance-db
COSMOS_CONTAINER=conversations
COSMOS_PARTITION_KEY=/user_id
DB_PROGRESS_FILE=db_progress.ndjson

# File specific configuration
TOP_N_DOCUMENTS=5

# RAG Pipeline Configuration
DATA_DIR=data
SETUP_PIPELINE=false
STREAM_RESPONSES=true
```

## Project Structure

```
azure-rag-template/
├── src/
│   ├── HEALRAG/              # Core RAG library
│   │   ├── __init__.py
│   │   ├── blob_manager.py   # Azure Blob Storage operations
│   │   ├── search_manager.py # Azure Cognitive Search operations
│   │   ├── rag_manager.py    # RAG operations with Azure OpenAI
│   │   ├── db_manager.py     # Cosmos DB operations
│   │   └── main.py           # High-level interface
│   ├── templates/
│   │   └── index.html        # Web interface template
│   ├── app.py                # Flask web application
│   └── RAG_CREATION.py       # Insurance-specific RAG implementation
├── data/                     # Sample insurance documents
├── requirements.txt
├── run_app.py                # Application entry point
└── .env                      # Configuration file
```

## Usage

### Basic Usage

```python
from src.HEALRAG.main import HEALRAG

# Initialize HEALRAG
healrag = HEALRAG()

# Upload insurance documents
healrag.upload_documents("path/to/insurance_documents")

# Create and populate search index
healrag.create_search_index()
healrag.populate_search_index()

# Process an insurance-related query
response = healrag.process_query("What are the benefits of my insurance plan?")
print(response)
```

### Advanced Usage

```python
from src.HEALRAG.main import HEALRAG

# Initialize with custom configuration
healrag = HEALRAG(
    blob_connection_string="your_connection_string",
    search_endpoint="your_search_endpoint",
    search_key="your_search_key",
    search_index_name="insurance-plans",
    openai_endpoint="your_openai_endpoint",
    openai_key="your_openai_key",
    openai_deployment="your_deployment",
    cosmos_endpoint="your_cosmos_endpoint",
    cosmos_key="your_cosmos_key",
    cosmos_database="insurance-db",
    cosmos_container="conversations"
)

# Upload insurance documents with progress tracking
healrag.upload_documents(
    "path/to/insurance_documents",
    container_name="insurance-documents",
    progress_file="insurance_upload_progress.ndjson"
)

# Create search index with insurance-specific fields
healrag.create_search_index(
    index_name="insurance-plans",
    fields=[
        {"name": "content", "type": "searchable", "facetable": False},
        {"name": "plan_type", "type": "searchable", "facetable": True},
        {"name": "coverage_details", "type": "searchable", "facetable": True},
        {"name": "benefits", "type": "searchable", "facetable": True}
    ]
)

# Process insurance query with streaming
for chunk in healrag.process_query(
    "What are the benefits of my insurance plan?",
    stream=True,
    user_id="user123"
):
    print(chunk, end="", flush=True)
```

### Web Interface

Run the web application:

```bash
python run_app.py
```

This will start a Flask server with a web interface for interacting with the insurance RAG system.

## Insurance-Specific Features

- **Plan Comparison**: Compare different insurance plans based on coverage and benefits
- **Coverage Verification**: Check if specific treatments or procedures are covered
- **Benefit Explanation**: Get detailed explanations of insurance benefits
- **Policy Interpretation**: Understand complex insurance policy language
- **Claim Guidance**: Receive guidance on filing insurance claims
- **Premium Calculation**: Understand how premiums are calculated
- **Network Information**: Find information about in-network providers

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin feature/your-feature-name`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- HEALRAG library for the core RAG functionality
- Azure Blob Storage for insurance document storage
- Azure Cognitive Search for semantic search capabilities
- Azure OpenAI for language model integration
- Azure Cosmos DB for conversation storage
- Point32 Health for insurance domain expertise 