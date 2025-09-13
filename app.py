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
GOOGLE_API_KEY = "AIzaSyCLyorq2keBX6k5J5ZUX_I7YaUQ8apRgL4"
YOUTUBE_API_KEY = "AIzaSyBnuUNg3S9n5jczlw_4p8hr-8zrAEKNfbI" # Added YouTube Key

# --- Configure API Services ---
genai.configure(api_key=GOOGLE_API_KEY)

# --- GitHub PDF Configuration ---
GITHUB_USER = "ajayyanshu"
GITHUB_REPO = "collegeproject"
GITHUB_FOLDER_PATH = "upload pdf"
PDF_KEYWORDS = {
    "2016 hindi paper": "2016 - Hindi (7402-01).pdf",
    "2023 english paper": "2023 - English (7403-01).pdf",
    "2023 hindi paper": "2023 - Hindi (7402-01).pdf",
    "2025 english paper": "2025 - English (7403-01).pdf",
    "2025 hindi paper": "2025 - Hindi (7402-01).pdf"
}

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

# --- New YouTube Helper Functions ---
def get_video_id(video_url):
    """Extracts the YouTube video ID from a URL."""
    video_id_match = re.search(r"(?:v=|\/|youtu\.be\/)([a-zA-Z0-9_-]{11})", video_url)
    return video_id_match.group(1) if video_id_match else None

def get_youtube_transcript(video_id):
    """Gets the transcript for a given video ID."""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([d['text'] for d in transcript_list])
    except Exception as e:
        print(f"Error getting YouTube transcript: {e}")
        return None

# --- Main Chat Logic (FIXED) ---
@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('text', '')
        file_data = data.get('fileData')
        file_type = data.get('fileType')
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # NEW: Create a list to hold all parts of the prompt (text, image, docs)
        prompt_parts = []
        if user_message:
            prompt_parts.append(user_message)

        # Priority 1: Handle a YouTube Link
        if "youtube.com" in user_message or "youtu.be" in user_message:
            video_id = get_video_id(user_message)
            if video_id:
                transcript = get_youtube_transcript(video_id)
                if transcript:
                    # For YouTube, we create a specific prompt and return early
                    youtube_prompt = f"Please provide a detailed and easy-to-understand summary of the following YouTube video transcript:\n\nTranscript:\n---\n{transcript}"
                    response = model.generate_content(youtube_prompt)
                    return jsonify({'response': response.text})
                else:
                    return jsonify({'response': "Sorry, I couldn't get the transcript for that video. It might be a live stream, or captions may be disabled."})
            else:
                return jsonify({'response': "That doesn't look like a valid YouTube link. Please provide the full URL."})

        # Priority 2: Check for keywords to get a file from GitHub
        matched_filename = next((filename for keyword, filename in PDF_KEYWORDS.items() if keyword in user_message.lower()), None)
        
        if matched_filename:
            file_bytes = get_file_from_github(matched_filename)
            if file_bytes:
                pdf_text = extract_text_from_pdf(file_bytes)
                # NEW: Add the PDF text to our prompt list instead of a separate variable
                prompt_parts.append(f"\n\n--- Start of Document: {matched_filename} ---\n{pdf_text}\n--- End of Document ---")
            else:
                return jsonify({'response': f"Sorry, I found the keyword for '{matched_filename}' but could not download it from GitHub."})

        # Priority 3: Handle a direct file upload from the user
        if file_data:
            file_bytes = base64.b64decode(file_data)
            if 'pdf' in file_type:
                pdf_text = extract_text_from_pdf(file_bytes)
                # NEW: Add the PDF text to our prompt list
                prompt_parts.append(f"\n\n--- Start of Uploaded PDF ---\n{pdf_text}\n--- End of Uploaded PDF ---")
            elif 'image' in file_type:
                image = Image.open(io.BytesIO(file_bytes))
                # NEW: Add the image object to our prompt list
                prompt_parts.append(image)

        # --- Generate AI Response ---
        # NEW: Generate content using the combined list of all inputs
        if not prompt_parts:
             return jsonify({'response': "Please ask a question or upload a file."})

        print(f"DEBUG: Sending to Gemini API: {len(prompt_parts)} parts.") # Helpful for debugging
        response = model.generate_content(prompt_parts)
        ai_response = response.text
            
        return jsonify({'response': ai_response})

    except Exception as e:
        print(f"A critical error occurred: {e}")
        # NEW: Provide a more detailed error message for debugging
        return jsonify({'error': f'An internal error occurred: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
