# Testing the HEALRAG Website

This document provides instructions on how to test the HEALRAG website.

## Prerequisites

- Python 3.8 or higher
- Azure account with the following services set up:
  - Azure Blob Storage
  - Azure Cognitive Search
  - Azure OpenAI
  - Azure Cosmos DB

## Setup

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

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up your environment variables:
   - Copy the `.env.template` file to `.env`
   - Fill in your Azure credentials and configuration

5. Prepare your data:
   - Place your insurance plan documents in the `data` directory
   - The documents should be in a format that can be processed by the RAG pipeline

## Running the Application

1. Start the FastAPI application:
   ```bash
   python run_app.py
   ```

2. Open your web browser and navigate to:
   ```
   http://localhost:8000
   ```

## Testing the Website

1. **Basic Query Testing**:
   - Enter a query in the input field and click "Submit"
   - The response will be displayed in the response section
   - Citations will be shown as clickable markers in the response

2. **Conversation History**:
   - After submitting a query, the conversation will be saved in the history panel
   - Click on a previous conversation to load it
   - Use the "Clear Session" button to start a new session without deleting history

3. **Citation Panel**:
   - Click on a citation marker in the response to view the source document
   - The citation panel will slide in from the right
   - Click the close button to hide the citation panel

4. **History Panel**:
   - The history panel shows your recent conversations
   - Click the toggle button to collapse/expand the panel
   - Click on a conversation to load it

## Troubleshooting

- If you encounter any issues with the Azure services, check your credentials in the `.env` file
- Make sure your data is in the correct format and placed in the `data` directory
- Check the console output for any error messages

## Next Steps

- Customize the frontend by modifying the HTML, CSS, and JavaScript files
- Add more features to the RAG pipeline by extending the `RAG_CREATION.py` file
- Deploy the application to a production environment 