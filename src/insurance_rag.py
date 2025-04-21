import os
from .insurance_search import InsuranceSearch  # Adjusted import
from .HEALRAG.rag_manager import RAGManager  # Adjusted import
from dotenv import load_dotenv
from collections import deque
from typing import Optional

load_dotenv(override=True)  # Load environment variables from .env file

class InsuranceRAG:
    def __init__(self):
        """
        Initialize the InsuranceRAG class by setting up search and RAG components.
        """
        self.search = InsuranceSearch()
        self.rag_manager = RAGManager()
        self.history = deque(maxlen=10)  # Maintain history of last 10 request-response pairs

    def perform_rag(self, query: str, stream: bool = True, session_id: Optional[str] = None, 
                    plan_name_filter: Optional[str] = None, temperature: float = 1.0, top_p: float = 0.95):  # Added temperature and top_p parameters
        """
        Perform the full RAG pipeline: search and generate a response.

        Args:
            query: The user query.
            stream: Whether to enable streaming responses.
            session_id: Optional session identifier.
            plan_name_filter: Optional filter for plan names.
            temperature: Sampling temperature for response generation.
            top_p: Nucleus sampling parameter for response generation.

        Returns:
            Generated response from the RAG pipeline (string or generator if streaming).
        """
        # Step 1: Perform search
        search_results = self.search.perform_search(query, plan_name_filter=plan_name_filter)
        if not search_results:
            return "No relevant documents found for the query."

        # Step 2: Generate response using RAG
        system_prompt = os.getenv("SYSTEM_PROMPT")  # Fetch SYSTEM_PROMPT from .env'
        print(f"system_prompt in perform rag is: {system_prompt}")
        if not system_prompt:
            print("SYSTEM_PROMPT not found in environment variables.")
            return "System prompt not configured."
        
        # Patch RAGManager._process_streaming_response to include context
        original_process_fn = self.rag_manager._process_streaming_response
        def fixed_process_streaming_response(response, query):
            return original_process_fn(response, query, search_results)
        self.rag_manager._process_streaming_response = fixed_process_streaming_response
        
        # Patch _update_conversation_history to include session_id
        original_update_fn = self.rag_manager._update_conversation_history
        def fixed_update_history(query, response):
            return original_update_fn(query, response, session_id=session_id)
        self.rag_manager._update_conversation_history = fixed_update_history

        response = self.rag_manager.generate_response(
            query=query,
            context=search_results,
            stream=stream,  # Use the stream parameter
            system_prompt=system_prompt,  # Pass SYSTEM_PROMPT
            history=list(self.history),  # Pass history as a list
            temperature=temperature,
            top_p=top_p
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
    response = insurance_rag.perform_rag(query, session_id="123")  # Stream is True by default
    if isinstance(response, str):
        print(f"Generated Response:\n{response}")
    else:
        print("Generated Response:")
        for chunk in response:
            print(chunk, end="")
