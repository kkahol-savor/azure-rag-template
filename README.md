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
- **Smart Citations**: Show only high-relevance sources with collapsible citation details
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
- **Relevance Scoring**: Results are scored based on semantic relevance
- **Smart Citations**: Only high-scoring sources (>0.7) are shown in responses

### Search Results
Each search result includes:
- Plan name and state
- Combined content from SBC and SOB documents
- Structured data fields
- Relevance score
- Source document references

## Web Interface

The project includes a modern web interface with the following features:

### Chat Interface
- Real-time streaming responses
- Collapsible citation display
- Conversation history
- Settings management

### Settings
- Plan name filtering
- Temperature control for response generation
- Top-p parameter adjustment
- Settings persistence across sessions

### Citations
- High-relevance source filtering (>0.7 score)
- Collapsible citation details
- Source document references
- Content snippets from source documents

## Docker Deployment

The application can be deployed using Docker for easier setup and consistency across environments.

### Prerequisites

- Docker and Docker Compose installed on your system
- Azure credentials configured in a `.env` file

### Setup

1. Create a `.env` file based on the `.env.template`:
```bash
cp .env.template .env
```

2. Edit the `.env` file with your Azure credentials.

3. Create the necessary directories:
```bash
mkdir -p data logs
```

4. Build and start the Docker container:
```bash
docker-compose up -d
```

5. The application will be available at `http://localhost:8000`.

### Data Handling

The application uses volume mounts for data persistence:
- `./data:/app/data`: For insurance documents
- `./logs:/app/logs`: For application logs

### Environment Variables

All environment variables from the `.env` file are passed to the container.

### Health Checks

The container includes a health check that verifies the application is running correctly.

### Scaling

For production deployments, consider using a container orchestration platform like Kubernetes.

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

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_KEY=your_key
AZURE_OPENAI_DEPLOYMENT=your_deployment_name

# Azure Cognitive Search Configuration
AZURE_SEARCH_ENDPOINT=your_search_endpoint
AZURE_SEARCH_KEY=your_search_key
AZURE_SEARCH_INDEX_NAME=your_index_name

# Cosmos DB Configuration
COSMOS_ENDPOINT=your_cosmos_endpoint
COSMOS_KEY=your_cosmos_key
COSMOS_DATABASE=your_database_name
COSMOS_CONTAINER=your_container_name
```

5. Run the application:
```bash
python src/app.py
```

The web interface will be available at `http://localhost:8000`.

## Usage

1. Start the application and navigate to the web interface
2. Use the settings panel to configure:
   - Plan name filter
   - Temperature (0.0-1.0)
   - Top-p (0.0-1.0)
3. Ask questions about insurance plans
4. View responses with collapsible citations
5. Access conversation history

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- HEALRAG library for the core RAG functionality
- Azure Blob Storage for insurance document storage
- Azure Cognitive Search for semantic search capabilities
- Azure OpenAI for language model integration
- Azure Cosmos DB for conversation storage
- Point32 Health for insurance domain expertise 