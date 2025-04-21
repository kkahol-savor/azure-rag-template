# Point32 Health Insurance RAG Application

A Retrieval-Augmented Generation (RAG) application for health insurance queries, built with FastAPI, Azure OpenAI, and Azure Cognitive Search.

## Features

- Natural language querying of health insurance documents
- Real-time streaming responses
- Document context retrieval with citations
- Configurable settings for response generation
- Modern web interface with streaming support
- Azure DevOps CI/CD pipeline for automated deployment

## Prerequisites

- Python 3.9+
- Azure subscription
- Azure OpenAI service
- Azure Cognitive Search service
- Azure Container Registry
- Azure App Service
- Azure DevOps organization

## Setup

### Local Development

1. Clone the repository:
```bash
git clone https://github.com/yourusername/point32-rag.git
cd point32-rag
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your Azure credentials
```

4. Run the application:
```bash
uvicorn src.app:app --reload
```

### Azure DevOps Pipeline Setup

1. Create service connections in Azure DevOps:
   - Azure Container Registry (ACR) connection named "acr-connection"
   - Azure Resource Manager connection named "Azure subscription" with App registration identity type
   - Both connections should have "Grant access to all pipelines" checked

2. Create deployment environment:
   - Go to Pipelines > Environments
   - Create new environment named "healrag-p3v3"

3. Request pipeline parallelism:
   - Visit https://aka.ms/azpipelines-parallelism-request
   - Fill out the form with your organization details
   - Wait for approval (usually 24 hours)

4. Import repository to Azure DevOps:
   - Go to Repos > Import
   - Enter your GitHub repository URL
   - Click Import

5. Create pipeline:
   - Go to Pipelines > New Pipeline
   - Select "Azure Repos Git"
   - Select your repository
   - Choose "Existing Azure Pipelines YAML file"
   - Select azure-pipeline.yml

## Deployment

The application is automatically deployed through Azure DevOps pipeline when changes are pushed to the main branch. The pipeline:

1. Builds the Docker image
2. Pushes it to Azure Container Registry
3. Deploys to Azure App Service

## Architecture

- Frontend: HTML, CSS, JavaScript with streaming support
- Backend: FastAPI with Azure OpenAI integration
- Search: Azure Cognitive Search for document retrieval
- Storage: Azure Blob Storage for documents
- Container: Docker for containerization
- CI/CD: Azure DevOps pipeline

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- HEALRAG library for the core RAG functionality
- Azure Blob Storage for insurance document storage
- Azure Cognitive Search for semantic search capabilities
- Azure OpenAI for language model integration
- Azure Cosmos DB for conversation storage
- Point32 Health for insurance domain expertise 