from dotenv import load_dotenv
import os

# Reload environment variables from the .env file
load_dotenv(override=True)

# Access and print the value of INDEXING_SAMPLE
print("SYSTEM PROMPT:", os.getenv("SYSTEM_PROMPT"))


