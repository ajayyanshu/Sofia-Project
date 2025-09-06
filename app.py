import os
import base64
import io
import re

# Import PDF and Google API libraries
import fitz  # PyMuPDF
from googleapiclient.discovery import build

from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi

app = Flask(__name__, template_folder='templates')

# --- Hardcoded API Keys ---
# WARNING: This is not secure for a live application.
GOOGLE_API_KEY = "AIzaSyDSVYwHKLSd_R4HOKDTW8dCY1eY9TvbnP4"
YOUTUBE_API_KEY = "AIzaSyBnuUNg3S9n5jczlw_4p8hr-8zrAEKNfbI"

# --- Configure API Services ---
genai.configure(api_key=GOOGLE_API_KEY)
# This handles getting YouTube video titles
youtube_service = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)


@app.route('/')
def home():
    return render_template('index.html')

def get_video_details(video_id):
    """Gets video details like title using the YouTube Data API."""
    try:
        request = youtube_service.videos().list(part="snippet", id=video_id)
        response = request.execute()
        if response['items']:
            return response['items'][0]['snippet']['title']
        return None
    except Exception as e:
        print(f"Error getting video details: {e}")
        return None

def get_youtube_transcript(video_url):
    """Extracts transcript from a YouTube video URL."""
    try:
        video_id_match = re.search(r"(?:v=|\/)([a-zA-Z0-9_-]{11}).*", video_url)
        if not video_id_match: return None
        video_id = video_id_match.group(1)
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        video_title = get_video_details(video_id) or "this video"
        
        return " ".join([d['text'] for d in transcript_list]), video_title
    except Exception as e:
        print(f"Error getting YouTube transcript: {e}")
        return None, None

def extract_text_from_pdf(pdf_bytes):
    """Extracts all text from the bytes of a PDF file."""
    try:
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = "".join(page.get_text() for page in pdf_document)
        return text
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

        if file_data_b64 and file_type:
            file_bytes = base64.b64decode(file_data_b64)
            if 'pdf' in file_type:
                pdf_text = extract_text_from_pdf(file_bytes)
                if pdf_text:
                    prompt = f"Based ONLY on the text from the document provided, please answer the question: '{user_message}'\n\nDocument Text:\n---\n{pdf_text}"
                    response = model.generate_content(prompt)
                    ai_response = response.text
                else:
                    ai_response = "Sorry, I could not read the content of that PDF."
            elif file_type.startswith('image/'):
                from PIL import Image
                img = Image.open(io.BytesIO(file_bytes))
                response = model.generate_content([user_message, img])
                ai_response = response.text
            else:
                 ai_response = "Sorry, that file type is not supported."
        elif "youtube.com" in user_message or "youtu.be" in user_message:
            transcript, title = get_youtube_transcript(user_message)
            if transcript:
                prompt = f"Please provide a detailed summary for the YouTube video titled '{title}'. Here is the transcript:\n\n{transcript}"
                response = model.generate_content(prompt)
                ai_response = response.text
            else:
                ai_response = "I couldn't get the transcript for that video. It might be a live stream or have transcripts disabled."
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

