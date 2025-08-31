import os
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

app = Flask(__name__)

# This route serves the main HTML file.
# It passes the Firebase and Gemini API keys from environment variables to the HTML template.
@app.route('/')
def index():
    firebase_config = {
        "apiKey": os.environ.get("FIREBASE_API_KEY"),
        "authDomain": os.environ.get("FIREBASE_AUTH_DOMAIN"),
        "projectId": os.environ.get("FIREBASE_PROJECT_ID"),
        "storageBucket": os.environ.get("FIREBASE_STORAGE_BUCKET"),
        "messagingSenderId": os.environ.get("FIREBASE_MESSAGING_SENDER_ID"),
        "appId": os.environ.get("FIREBASE_APP_ID"),
    }
    
    # Get the Gemini API key from the environment
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    
    return render_template('index.html', 
                           firebase_config=firebase_config,
                           gemini_api_key=gemini_api_key)

if __name__ == '__main__':
    # You may need to change host to '0.0.0.0' for Render deployment.
    app.run(host='127.0.0.1', port=5000, debug=True)
