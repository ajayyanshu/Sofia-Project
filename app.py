import os
import base64
import io
import re

# Import PDF reading library
import fitz  # PyMuPDF

from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi

app = Flask(__name__, template_folder='templates')

# It's more secure to set this as an environment variable on Render
API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
genai.configure(api_key=API_KEY)

# In-memory store for chat history (replace with a database for a real app)
user_profiles = {}

@app.route('/')
def home():
    return render_template('new1.0.html')

def get_youtube_transcript(video_url):
    try:
        video_id_match = re.search(r"(?:v=|\/)([a-zA-Z0-9_-]{11}).*", video_url)
        if not video_id_match:
            return None
        video_id = video_id_match.group(1)
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([d['text'] for d in transcript_list])
    except Exception as e:
        print(f"Error getting transcript: {e}")
        return None

def extract_text_from_pdf(pdf_data):
    """Extracts text from PDF byte data."""
    try:
        # Open the PDF from in-memory data
        pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
        text = ""
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            text += page.get_text()
        return text
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return None

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('text', '')
        
        # File handling logic
        file_data_b64 = data.get('fileData')
        file_type = data.get('fileType')
        
        context_text = ""
        is_vision_request = False

        if file_data_b64 and file_type:
            # Decode the base64 file data
            file_bytes = base64.b64decode(file_data_b64)
            
            if 'pdf' in file_type:
                context_text = extract_text_from_pdf(file_bytes)
                if not context_text:
                    return jsonify({'error': 'Could not extract text from the PDF.'}), 500
            elif file_type.startswith('image/'):
                is_vision_request = True
            # Add logic for .doc/.docx later if needed
            else:
                 return jsonify({'error': 'Unsupported file type.'}), 400

        # --- AI Model Logic ---
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        if is_vision_request:
            from PIL import Image
            img = Image.open(io.BytesIO(file_bytes))
            response = model.generate_content([user_message, img])
            ai_response = response.text
        elif context_text:
            # If we have text from a PDF, use it as context
            prompt = f"""
            Based ONLY on the content of the document provided below, please answer the following question.
            
            Question: "{user_message}"

            Document Content:
            ---
            {context_text}
            ---
            """
            response = model.generate_content(prompt)
            ai_response = response.text
        elif "youtube.com" in user_message or "youtu.be" in user_message:
            transcript = get_youtube_transcript(user_message)
            if transcript:
                prompt = f"Summarize the following YouTube video transcript: {transcript}"
                response = model.generate_content(prompt)
                ai_response = response.text
            else:
                ai_response = "Could not get the transcript for that video."
        else:
            # Standard chat without files
            response = model.generate_content(user_message)
            ai_response = response.text
            
        return jsonify({'response': ai_response})

    except Exception as e:
        print(f"An error occurred in /chat: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Use the PORT environment variable provided by Render
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
