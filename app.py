# filename: app.py

import base64
import io
import os
import re
import sys
from datetime import datetime

import docx
import fitz  # PyMuPDF
import google.generativeai as genai
import requests  # We will use this for DeepSeek API
from flask import Flask, jsonify, render_template, request
from PIL import Image
from pymongo import MongoClient
from youtube_transcript_api import YouTubeTranscriptApi

app = Flask(__name__, template_folder='templates')

# --- Securely Load API Keys from Render Environment ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY") # <-- ADDED for DeepSeek

# --- Configure API Services ---
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    print("CRITICAL ERROR: GOOGLE_API_KEY environment variable not found.")

if not DEEPSEEK_API_KEY:
    print("WARNING: DEEPSEEK_API_KEY environment variable not found. Text-only chat will not work.")

# --- MongoDB Configuration ---
chat_history_collection = None
if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI)
        db = mongo_client.get_database("ai_assistant_db")
        chat_history_collection = db.get_collection("chat_history")
        print("✅ Successfully connected to MongoDB.")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not connect to MongoDB. Chat history will not be saved. Error: {e}")
else:
    print("WARNING: MONGO_URI environment variable not found. Chat history will not be saved.")


# --- GitHub PDF Configuration (No Changes Here) ---
GITHUB_USER = "ajayyanshu"
# ... (rest of the GitHub config is the same)
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
    return render_template('coming_soon.html')


# --- Helper Functions for File Processing (No Changes Here) ---
def extract_text_from_pdf(pdf_bytes):
# ... (function is the same)
    try:
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        return "".join(page.get_text() for page in pdf_document)
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return ""

def extract_text_from_docx(docx_bytes):
# ... (function is the same)
    try:
        document = docx.Document(io.BytesIO(docx_bytes))
        return "\n".join([para.text for para in document.paragraphs])
    except Exception as e:
        print(f"Error extracting DOCX text: {e}")
        return ""

def get_file_from_github(filename):
# ... (function is the same)
    url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/{GITHUB_FOLDER_PATH.replace(' ', '%20')}/{filename.replace(' ', '%20')}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        print(f"Successfully downloaded {filename} from GitHub.")
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Error downloading from GitHub: {e}")
        return None


def get_video_id(video_url):
# ... (function is the same)
    video_id_match = re.search(r"(?:v=|\/|youtu\.be\/)([a-zA-Z0-9_-]{11})",
                               video_url)
    return video_id_match.group(1) if video_id_match else None


def get_youtube_transcript(video_id):
# ... (function is the same)
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([d['text'] for d in transcript_list])
    except Exception as e:
        print(f"Error getting YouTube transcript: {e}")
        return None

# --- NEW: Helper Function for DeepSeek API ---
def call_deepseek_api(user_message):
    if not DEEPSEEK_API_KEY:
        return "Sorry, the DeepSeek API is not configured."
    try:
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": user_message}
            ]
        }
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        result = response.json()
        return result['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        print(f"Error calling DeepSeek API: {e}")
        return "Sorry, there was an error contacting the AI service for text chat."
    except (KeyError, IndexError) as e:
        print(f"Error parsing DeepSeek API response: {e}")
        return "Sorry, I received an invalid response from the AI service."
# --- END NEW SECTION ---


# --- Main Chat Logic (HEAVILY MODIFIED) ---
@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('text', '')
        file_data = data.get('fileData')
        file_type = data.get('fileType', '')
        
        ai_response = ""
        api_used = "" # To track which API was called

        # --- Determine which API to use ---
        is_youtube_link = "youtube.com" in user_message or "youtu.be" in user_message
        matched_github_keyword = any(keyword in user_message.lower() for keyword in PDF_KEYWORDS)
        is_multimodal_request = bool(file_data) or is_youtube_link or matched_github_keyword

        # --- Route 1: Gemini for Files, YouTube, or GitHub Keywords ---
        if is_multimodal_request:
            api_used = "Gemini"
            print("Routing to Gemini for multimodal request.")
            prompt_parts = []
            if user_message:
                prompt_parts.append(user_message)
            
            # This logic is mostly the same as your previous version
            # It just sets prompt_parts instead of returning immediately
            
            # YouTube Link
            if is_youtube_link:
                video_id = get_video_id(user_message)
                if video_id:
                    transcript = get_youtube_transcript(video_id)
                    if transcript:
                        prompt_parts = [f"Please provide a detailed and easy-to-understand summary of the following YouTube video transcript:\n\nTranscript:\n---\n{transcript}"]
                    else:
                        return jsonify({'response': "Sorry, I couldn't get the transcript for that video."})
                else:
                    return jsonify({'response': "That doesn't look like a valid YouTube link."})
            
            # GitHub Keyword
            elif matched_github_keyword:
                filename = next(filename for keyword, filename in PDF_KEYWORDS.items() if keyword in user_message.lower())
                file_bytes = get_file_from_github(filename)
                if file_bytes:
                    pdf_text = extract_text_from_pdf(file_bytes)
                    if pdf_text.strip():
                        prompt_parts.append(f"\n--- Document: {filename} ---\n{pdf_text}\n--- End of Document ---")
                    else:
                        return jsonify({'response': f"Sorry, could not extract text from '{filename}'."})
                else:
                    return jsonify({'response': f"Sorry, I could not download '{filename}'."})
            
            # Direct File Upload
            elif file_data:
                file_bytes = base64.b64decode(file_data)
                if 'pdf' in file_type:
                    text = extract_text_from_pdf(file_bytes)
                    prompt_parts.append(f"\n--- Uploaded PDF ---\n{text}\n--- End of PDF ---")
                elif 'word' in file_type or 'vnd.openxmlformats-officedocument.wordprocessingml.document' in file_type:
                    text = extract_text_from_docx(file_bytes)
                    prompt_parts.append(f"\n--- Uploaded Document ---\n{text}\n--- End of Document ---")
                elif 'image' in file_type:
                    image = Image.open(io.BytesIO(file_bytes))
                    prompt_parts.append(image)
                else:
                    return jsonify({'response': f"Sorry, unsupported file type '{file_type}'."})

            # Call Gemini API
            model = genai.GenerativeModel('gemini-1.5-flash')
            if not any(isinstance(p, str) and p.strip() for p in prompt_parts if isinstance(p, str)) and any(isinstance(p, Image.Image) for p in prompt_parts):
                prompt_parts.insert(0, "Describe this image in detail.")
            
            response = model.generate_content(prompt_parts)
            ai_response = response.text

        # --- Route 2: DeepSeek for Normal Text Chat ---
        else:
            api_used = "DeepSeek"
            print("Routing to DeepSeek for text-only request.")
            if not user_message.strip():
                return jsonify({'response': "Please ask a question or upload a file."})
            ai_response = call_deepseek_api(user_message)

        # --- Save to MongoDB (runs for both routes) ---
        if chat_history_collection is not None and ai_response:
            try:
                chat_history_collection.insert_one({
                    "user_message": user_message,
                    "ai_response": ai_response,
                    "api_used": api_used,
                    "has_file": bool(file_data),
                    "file_type": file_type if file_data else None,
                    "timestamp": datetime.utcnow()
                })
            except Exception as e:
                print(f"Error saving chat to MongoDB: {e}")

        return jsonify({'response': ai_response})

    except Exception as e:
        print(f"A critical error occurred: {e}")
        user_facing_error = "Sorry, something went wrong. Please try again."
        return jsonify({'response': user_facing_error})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
