import os
import base64
import io
import re
import requests

import fitz  # PyMuPDF
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi

app = Flask(__name__, template_folder='templates')

# --- Hardcoded API Keys ---
# ⚠️ This is NOT recommended for security reasons. Use environment variables for production.
GOOGLE_API_KEY = "AIzaSyDSVYwHKLSd_R4HOKDTW8dCY1eY9TvbnP4"
YOUTUBE_API_KEY = "AIzaSyBnuUNg3S9n5jczlw_4p8hr-8zrAEKNfbI"

# --- Configure API Services ---
genai.configure(api_key=GOOGLE_API_KEY)
youtube_service = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
# Add Google Drive service using the same API key for public file access
drive_service = build('drive', 'v3', developerKey=GOOGLE_API_KEY)

@app.route('/')
def home():
    # The HTML file is named index.html in the templates folder
    return render_template('index.html')

def get_file_from_drive_url(url):
    """Downloads a file from a public Google Drive link."""
    try:
        file_id_match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
        if not file_id_match:
            return None, "Invalid Google Drive Link"
        
        file_id = file_id_match.group(1)
        print(f"Found Google Drive file ID: {file_id}")
        
        # Get file metadata to determine the type
        file_metadata = drive_service.files().get(fileId=file_id, fields='mimeType, name').execute()
        mime_type = file_metadata.get('mimeType')
        file_name = file_metadata.get('name')

        if mime_type == 'application/vnd.google-apps.document':
            # Export Google Docs as plain text
            request = drive_service.files().export_media(fileId=file_id, mimeType='text/plain')
        else:
            # For other file types like PDF, directly download
            request = drive_service.files().get_media(fileId=file_id)
            
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}%.")
        
        print(f"Successfully downloaded '{file_name}' from Google Drive.")
        return fh.getvalue(), file_name
        
    except Exception as e:
        print(f"Error fetching from Google Drive: {e}")
        return None, "Could not access the file. Make sure it is shared publicly ('Anyone with the link')."

def extract_text_from_pdf(pdf_bytes):
    """Extracts text from a PDF file's bytes."""
    try:
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        return "".join(page.get_text() for page in pdf_document)
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return ""

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('text', '')
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        ai_response = ""

        # --- New: Priority 1 - Handle Google Drive links ---
        drive_link_match = re.search(r'https?://drive\.google\.com/[^\s]+', user_message)
        if drive_link_match:
            drive_url = drive_link_match.group(0)
            file_bytes, message = get_file_from_drive_url(drive_url)
            
            if file_bytes:
                # Check if it's a PDF or plain text (from Google Doc)
                try:
                    # Attempt to decode as text first (for exported GDocs)
                    document_text = file_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    # If it fails, it's likely a binary file like a PDF
                    document_text = extract_text_from_pdf(file_bytes)
                
                if document_text:
                    prompt = f"Based ONLY on the following document content, answer the user's question.\nUser Question: '{user_message}'\n\nDocument Content:\n---\n{document_text}"
                    response = model.generate_content(prompt)
                    ai_response = response.text
                else:
                    ai_response = f"I downloaded the file '{message}', but I was unable to read its content."
            else:
                ai_response = message # Return the error message (e.g., "Make sure it's public")
        
        # Priority 2: Handle standard text messages
        else:
            # This is the default case for any regular text message
            response = model.generate_content(user_message)
            ai_response = response.text
            
        return jsonify({'response': ai_response})
    except Exception as e:
        print(f"A critical error occurred: {e}")
        return jsonify({'error': 'An internal error occurred.'}), 500

if __name__ == '__main__':
    # This is used for local testing. Render uses its own start command.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

