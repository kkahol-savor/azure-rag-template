import os
from HEALRAG.search_manager import SearchManager
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

class InsuranceSearch:
    def __init__(self):
        """
        Initialize the InsuranceSearch class with configuration from environment variables.
        """
        self.index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")
        self.top_n_documents = int(os.getenv("NUMBER_OF_DOCUMENTS_TO_RETRIEVE", 10))
        self.search_method = os.getenv("SEARCH_METHOD", "hybrid").lower()
        self.select_fields = eval(os.getenv("SELECT_FIELDS", "[]"))  # Convert string to list
        self.scoring_profile = os.getenv("SCORING_PROFILE", "basic")  # Ensure 'basic' is the correct name
        self.semantic_configuration_name = os.getenv("SEMANTIC_CONFIGURATION_NAME", None)
        self.search_manager = SearchManager()

    def perform_search(self, query: str):
        """
        Perform a search on the insurance index using the SearchManager.

        Args:
            query: The search query.

        Returns:
            List of search results as dictionaries.
        """
        results = self.search_manager.search(
            query=query,
            index_name=self.index_name,
            search_type=self.search_method,
            top=self.top_n_documents,
            select_fields=self.select_fields,
            scoring_profile=self.scoring_profile,
            semantic_configuration_name=self.semantic_configuration_name  # Pass semantic configuration
        )
        return results

if __name__ == "__main__":
    # Example usage
    query = "what is my overall deductible in Clear Choice HMO Gold 1500"
    insurance_search = InsuranceSearch()
    search_results = insurance_search.perform_search(query)
    print(f"Search Results:\n{search_results}")
    #write to a file
    with open("search_results.txt", "w") as f:
        for result in search_results:
            f.write(f"{result}\n")
