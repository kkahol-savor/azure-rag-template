# HEALRAG: Azure RAG Template

HEALRAG is a Python library for enabling Retrieval-Augmented Generation (RAG) creation using Azure services. It provides a comprehensive set of tools for managing document storage, search operations, and RAG-based response generation.

## Features

- **Blob Storage Management**: Upload and manage documents in Azure Blob Storage
- **Search Operations**: Create and manage Azure Cognitive Search indices with semantic search capabilities
- **RAG Implementation**: Generate context-aware responses using Azure OpenAI
- **Database Management**: Store and retrieve conversations using Cosmos DB
- **Progress Tracking**: Monitor operations using NDJSON files
- **Type Hints**: Full type support for better IDE integration
- **Error Handling**: Comprehensive error handling and logging
- **Batch Processing**: Efficient batch processing for large datasets
- **Streaming Support**: Stream responses for real-time interactions

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

4. Copy the environment template and fill in your Azure credentials:
```bash
cp src/HEALRAG/.env.template .env
```

## Configuration

Create a `.env` file with your Azure credentials:

```env
# Azure Blob Storage Configuration
AZURE_STORAGE_CONNECTION_STRING=your_blob_storage_connection_string
AZURE_STORAGE_CONTAINER=insurance-documents
BLOB_PROGRESS_FILE=blob_progress.ndjson

# Azure Cognitive Search Configuration
AZURE_SEARCH_ENDPOINT=https://your-search-service.search.windows.net
AZURE_SEARCH_KEY=your_search_service_key
AZURE_SEARCH_INDEX_NAME=insurance-plans
TOP_N_DOCUMENTS=5
SEARCH_PROGRESS_FILE=search_progress.ndjson

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://your-openai-service.openai.azure.com
AZURE_OPENAI_KEY=your_openai_service_key
AZURE_OPENAI_DEPLOYMENT=gpt-4
MAX_HISTORY=10
RAG_PROGRESS_FILE=rag_progress.ndjson

# Cosmos DB Configuration
COSMOS_ENDPOINT=https://your-cosmos-account.documents.azure.com:443
COSMOS_KEY=your_cosmos_db_key
COSMOS_DATABASE=insurance-db
COSMOS_CONTAINER=conversations
DB_PROGRESS_FILE=db_progress.ndjson
```

## Usage

### Basic Usage

```python
from HEALRAG.main import HEALRAG

# Initialize HEALRAG
healrag = HEALRAG()

# Upload documents
healrag.upload_documents("path/to/documents")

# Create search index
fields = [
    {"name": "id", "type": "Edm.String", "key": True},
    {"name": "content", "type": "Edm.String", "searchable": True}
]
healrag.create_search_index(fields)

# Populate search index
healrag.populate_search_index(documents)

# Process a query
result = healrag.process_query("What is covered under the plan?")
print(result["response"])
```

### Advanced Usage

#### Custom Search Configuration

```python
# Create semantic configuration
semantic_config = healrag.search_manager.create_default_semantic_config(
    content_fields=["content"],
    keywords_fields=["title"]
)

# Create scoring profile
scoring_profile = healrag.search_manager.create_default_scoring_profile({
    "title": 2.0,
    "content": 1.0
})

# Create index with custom configuration
healrag.create_search_index(
    fields=fields,
    scoring_profile=scoring_profile,
    semantic_config=semantic_config
)
```

#### Streaming Responses

```python
# Generate streaming response
for chunk in healrag.generate_response("What is covered?", context, stream=True):
    print(chunk, end="", flush=True)
```

#### Conversation Management

```python
# Save conversation
conversation = {
    "query": "What is covered?",
    "response": "Based on the plan...",
    "timestamp": "2024-03-21T10:00:00Z"
}
saved = healrag.save_conversation(conversation)

# Retrieve conversation
retrieved = healrag.get_conversation(saved["id"])
```

## Project Structure

```
HEALRAG/
├── __init__.py
├── blob_manager.py      # Azure Blob Storage operations
├── search_manager.py    # Azure Cognitive Search operations
├── rag_manager.py       # RAG operations with Azure OpenAI
├── db_manager.py        # Cosmos DB operations
├── main.py             # High-level interface
└── .env.template       # Environment variables template
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -am 'Add your feature'`
4. Push to the branch: `git push origin feature/your-feature`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Azure OpenAI Service
- Azure Cognitive Search
- Azure Blob Storage
- Azure Cosmos DB 