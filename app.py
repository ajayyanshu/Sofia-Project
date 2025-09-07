import os
import base64
import io
import re
import requests

import fitz  # PyMuPDF
from googleapiclient.discovery import build
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi

app = Flask(__name__, template_folder='templates')

# --- Hardcoded API Keys ---
GOOGLE_API_KEY = "AIzaSyDSVYwHKLSd_R4HOKDTW8dCY1eY9TvbnP4"
YOUTUBE_API_KEY = "AIzaSyBnuUNg3S9n5jczlw_4p8hr-8zrAEKNfbI"

# --- Configure API Services ---
genai.configure(api_key=GOOGLE_API_KEY)
youtube_service = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

# --- List of known PDF files for keyword matching ---
KNOWN_PDF_FILES = {
    "2016 hindi": "2016 - Hindi (7402-01).pdf",
    "2023 english": "2023 - English (7403-01).pdf",
    "2023 hindi": "2023 - Hindi (7402-01).pdf",
    "2025 english": "2025 - English (7403-01).pdf",
    "2025 hindi": "2025 - Hindi (7402-01).pdf",
}

@app.route('/')
def home():
    return render_template('index.html')

def get_pdf_from_url(pdf_url):
    """Downloads a PDF from a given URL."""
    try:
        # This is the key change: convert a standard GitHub link to a raw content link
        if "github.com" in pdf_url and "blob" in pdf_url:
            pdf_url = pdf_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        
        print(f"Attempting to download from URL: {pdf_url}")
        response = requests.get(pdf_url)
        response.raise_for_status()
        print("Successfully fetched PDF from URL.")
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Error fetching PDF from URL: {e}")
        return None

def get_youtube_transcript(video_url):
    # This function remains unchanged
    try:
        video_id_match = re.search(r"(?:v=|\/)([a-zA-Z0-9_-]{11}).*", video_url)
        if not video_id_match: return None, None
        video_id = video_id_match.group(1)
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        video_title = "this video"
        return " ".join([d['text'] for d in transcript_list]), video_title
    except Exception:
        return None, None

def extract_text_from_pdf(pdf_bytes):
    # This function remains unchanged
    try:
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        return "".join(page.get_text() for page in pdf_document)
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return None

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('text', '')
        file_data_b64 = data.get('fileData')
        file_type = data.get('fileType')
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        ai_response = ""

        # --- New Logic to detect and handle GitHub URLs first ---
        github_url_match = re.search(r'https?://github\.com/[^\s]+\.pdf', user_message)
        
        if github_url_match:
            pdf_url = github_url_match.group(0)
            pdf_bytes = get_pdf_from_url(pdf_url)
            if pdf_bytes:
                pdf_text = extract_text_from_pdf(pdf_bytes)
                if pdf_text:
                    prompt = f"Based ONLY on the text from the document at the URL, answer the user's question: '{user_message}'\n\nDocument Text:\n---\n{pdf_text}"
                    response = model.generate_content(prompt)
                    ai_response = response.text
                else:
                    ai_response = "I was able to download the file from the link, but I couldn't read its content."
            else:
                ai_response = "Sorry, I couldn't download the PDF from the link you provided."
        
        # Keyword-based PDF search
        elif any(key in user_message.lower() for key in KNOWN_PDF_FILES):
            key = next((k for k in KNOWN_PDF_FILES if k in user_message.lower()), None)
            filename = KNOWN_PDF_FILES[key]
            # Construct the raw URL for keyword search
            raw_url = f"https://raw.githubusercontent.com/ajayyanshu/collegeproject/main/upload%20pdf/{filename.replace(' ', '%20')}"
            pdf_bytes = get_pdf_from_url(raw_url)
            if pdf_bytes:
                pdf_text = extract_text_from_pdf(pdf_bytes)
                if pdf_text:
                    prompt = f"Based ONLY on the document '{filename}', answer: '{user_message}'\n\nText:\n---\n{pdf_text}"
                    response = model.generate_content(prompt)
                    ai_response = response.text
                else:
                    ai_response = f"I found '{filename}' but could not read it."
            else:
                ai_response = f"Sorry, I couldn't find '{filename}' in the repository."

        # File Upload handling
        elif file_data_b64 and file_type:
            file_bytes = base64.b64decode(file_data_b64)
            if 'pdf' in file_type:
                pdf_text = extract_text_from_pdf(file_bytes)
                prompt = f"Answer the question '{user_message}' based on this document text: {pdf_text}"
                response = model.generate_content(prompt)
                ai_response = response.text
            elif file_type.startswith('image/'):
                from PIL import Image
                img = Image.open(io.BytesIO(file_bytes))
                response = model.generate_content([user_message, img])
                ai_response = response.text
            else:
                 ai_response = "Sorry, that file type is not supported for uploads."

        # YouTube and standard text handling
        elif "youtube.com" in user_message or "youtu.be" in user_message:
            transcript, title = get_youtube_transcript(user_message)
            if transcript:
                prompt = f"Summarize the YouTube video '{title}': {transcript}"
                response = model.generate_content(prompt)
                ai_response = response.text
            else:
                ai_response = "I couldn't get the transcript for that video."
        else:
            response = model.generate_content(user_message)
            ai_response = response.text
            
        return jsonify({'response': ai_response})
    except Exception as e:
        print(f"A critical error occurred: {e}")
        return jsonify({'error': 'An internal error occurred.'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

