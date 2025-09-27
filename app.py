import os
import google.generativeai as genai

# This script helps diagnose "Model not found" errors.
# It connects to the Gemini API using your key and prints a list
# of all the models your project has permission to use.

# --- Securely Load API Key from Render Environment ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    print("Successfully configured Gemini API. Fetching models...\n")
    
    try:
        # --- List all available models ---
        for m in genai.list_models():
            # We only care about models that support the 'generateContent' method
            if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.name}")
        
        print("\nInstructions: Copy the full list above and paste it in the chat.")

    except Exception as e:
        print(f"An error occurred while fetching models: {e}")
        print("Please ensure your GOOGLE_API_KEY is correct and has the necessary permissions.")

else:
    print("CRITICAL ERROR: GOOGLE_API_KEY environment variable not found.")
    print("Please make sure you have set this variable in your Render environment.")
