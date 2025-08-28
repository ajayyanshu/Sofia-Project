import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load API key
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
print("API Key Loaded:", api_key is not None)   # Debug check

genai.configure(api_key=api_key)

# Create model
model = genai.GenerativeModel("gemini-1.5-flash")

# Send message
response = model.generate_content("Hii")

# Debug print
print("Full Response:", response)

# Proper text output
if response.candidates and response.candidates[0].content.parts:
    print("Model Reply:", response.candidates[0].content.parts[0].text)
else:
    print("⚠️ No reply from model")
