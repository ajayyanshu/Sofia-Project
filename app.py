import os
import base64
import io
import re
import requests

import fitz  # PyMuPDF
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from PIL import Image
from youtube_transcript_api import YouTubeTranscriptApi

app = Flask(__name__, template_folder='templates')

# --- Hardcoded API Keys ---
# ⚠️ This is NOT recommended for security reasons. Use environment variables for production.
GOOGLE_API_KEY = "AIzaSyDSVYwHKLSd_R4HOKDTW8dCY1eY9TvbnP4"
YOUTUBE_API_KEY = "AIzaSyBnuUNg3S9n5jczlw_4p8hr-8zrAEKNfbI"

# --- Configure API Services ---
genai.configure(api_key=GOOGLE_API_KEY)

# --- GitHub PDF Configuration ---
GITHUB_USER = "ajayyanshu"
GITHUB_REPO = "collegeproject"
GITHUB_FOLDER_PATH = "upload pdf"
# This is a list of all available files. The AI will search this list.
AVAILABLE_PDFS = [
    "2016 - Hindi (7402-01).pdf",
    "2023 - English (7403-01).pdf",
    "2023 - Hindi (7402-01).pdf",
    "2025 - English (7403-01).pdf",
    "2025 - Hindi (7402-01).pdf"
]

@app.route('/')
def home():
    return render_template('index.html')

# --- Helper Functions for File Processing ---
def extract_text_from_pdf(pdf_bytes):
    try:
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        return "".join(page.get_text() for page in pdf_document)
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return ""

def get_file_from_github(filename):
    url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/{GITHUB_FOLDER_PATH.replace(' ', '%20')}/{filename.replace(' ', '%20')}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        print(f"Successfully downloaded {filename} from GitHub.")
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Error downloading from GitHub: {e}")
        return None

def find_matching_pdf(message):
    """Smarter function to find a PDF based on keywords in the user's message."""
    message_lower = message.lower()
    
    # Simple keyword matching
    if "2016" in message_lower and "hindi" in message_lower:
        return "2016 - Hindi (7402-01).pdf"
    if "2023" in message_lower and "english" in message_lower:
        return "2023 - English (7403-01).pdf"
    if "2023" in message_lower and "hindi" in message_lower:
        return "2023 - Hindi (7402-01).pdf"
    if "2025" in message_lower and "english" in message_lower:
        return "2025 - English (7403-01).pdf"
    if "2025" in message_lower and "hindi" in message_lower:
        return "2025 - Hindi (7402-01).pdf"
        
    return None # No match found

# --- Main Chat Logic ---
@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('text', '')
        file_data = data.get('fileData')
        file_type = data.get('fileType')
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Priority 1: Check for keywords to get a file from GitHub
        matched_filename = find_matching_pdf(user_message)
        
        if matched_filename:
            download_url = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/raw/main/{GITHUB_FOLDER_PATH.replace(' ', '%20')}/{matched_filename.replace(' ', '%20')}"
            
            if "download" in user_message.lower() or "link" in user_message.lower():
                ai_response = f"Of course! Here is the download link for '{matched_filename}':\n\n[Download the paper here]({download_url})"
                return jsonify({'response': ai_response})

            file_bytes = get_file_from_github(matched_filename)
            if file_bytes:
                document_text = extract_text_from_pdf(file_bytes)
                if document_text:
                    prompt = f"I have found the document '{matched_filename}'. Based on its content, please answer the user's question: '{user_message}'\n\nDocument Content:\n---\n{document_text}"
                    response = model.generate_content(prompt)
                    ai_response = f"I found the file **{matched_filename}**.\n\n" + response.text
                    ai_response += f"\n\n[Download this paper here]({download_url})"
                    return jsonify({'response': ai_response})
                else:
                    return jsonify({'response': f"Sorry, I found and downloaded '{matched_filename}', but could not read its content. You can still [download it here]({download_url})."})
            else:
                return jsonify({'response': f"Sorry, I found a match for '{matched_filename}' but could not download it from GitHub."})

        # Priority 2: Handle a direct file upload from the user
        if file_data:
            # This part of the code handles files uploaded from the user's computer
            pass # The logic for this would go here

        # Priority 3: Normal Conversation
        response = model.generate_content(user_message)
        return jsonify({'response': response.text})

    except Exception as e:
        print(f"A critical error occurred: {e}")
        return jsonify({'error': 'An internal error occurred.'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

