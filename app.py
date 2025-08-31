from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Access the API key
api_key = os.getenv("GOOGLE_API_KEY")
print(api_key)  # Just to check it's loaded
