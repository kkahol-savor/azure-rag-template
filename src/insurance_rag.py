import os
from insurance_search import InsuranceSearch  # Adjusted import
from HEALRAG.rag_manager import RAGManager  # Adjusted import
from dotenv import load_dotenv
from collections import deque

load_dotenv(override=True)  # Load environment variables from .env file

class InsuranceRAG:
    def __init__(self):
        """
        Initialize the InsuranceRAG class by setting up search and RAG components.
        """
        self.search = InsuranceSearch()
        self.rag_manager = RAGManager()
        self.history = deque(maxlen=10)  # Maintain history of last 10 request-response pairs

    def perform_rag(self, query: str, stream: bool = True):  # Default stream to True
        """
        Perform the full RAG pipeline: search and generate a response.

        Args:
            query: The user query.
            stream: Whether to enable streaming responses.

        Returns:
            Generated response from the RAG pipeline (string or generator if streaming).
        """
        # Step 1: Perform search
        search_results = self.search.perform_search(query)
        if not search_results:
            return "No relevant documents found for the query."

        # Step 2: Generate response using RAG
        system_prompt = os.getenv("SYSTEM_PROMPT")  # Fetch SYSTEM_PROMPT from .env'
        print(f"system_prompt in perform rag is: {system_prompt}")
       # print(f"System Prompt: {system_prompt}")
        if not system_prompt:
            print("SYSTEM_PROMPT not found in environment variables.")
            #exit
            return "System prompt not configured."
        
        # Patch RAGManager._process_streaming_response to include context
        original_process_fn = self.rag_manager._process_streaming_response
        def fixed_process_streaming_response(response, query):
            return original_process_fn(response, query, search_results)
        self.rag_manager._process_streaming_response = fixed_process_streaming_response

        response = self.rag_manager.generate_response(
            query=query,
            context=search_results,
            stream=stream,  # Use the stream parameter
            system_prompt=system_prompt,  # Pass SYSTEM_PROMPT
            history=list(self.history),  # Pass history as a list
            temperature=1.0,
            top_p=0.9
        )

        if stream and not isinstance(response, str):
            def streaming_with_history():
                full_response = []
                for chunk in response:
                    full_response.append(chunk)
                    yield chunk
                self.history.append((query, "".join(full_response)))
            return streaming_with_history()
        else:
            self.history.append((query, response))
            return response

if __name__ == "__main__":
    # Example usage
    query = "What is the overall deductible for Clear Choice HMO Gold 1500?"
    insurance_rag = InsuranceRAG()
    response = insurance_rag.perform_rag(query)  # Stream is True by default
    if isinstance(response, str):
        print(f"Generated Response:\n{response}")
    else:
        print("Generated Response:")
        for chunk in response:
            print(chunk, end="")
