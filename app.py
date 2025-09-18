# filename: app.py

import base64
import io
import os
import re
import sys
from datetime import datetime  # <-- ADDED for timestamps

import docx
import fitz  # PyMuPDF
import google.generativeai as genai
import requests
from flask import Flask, jsonify, render_template, request
from PIL import Image
from pymongo import MongoClient  # <-- ADDED for MongoDB
from youtube_transcript_api import YouTubeTranscriptApi

app = Flask(__name__, template_folder='templates')

# --- Securely Load API Keys from Render Environment ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI") # <-- ADDED for MongoDB URI

# --- Configure API Services ---
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    print("CRITICAL ERROR: GOOGLE_API_KEY environment variable not found.")

# --- NEW: MongoDB Configuration ---
chat_history_collection = None
if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI)
        db = mongo_client.get_database("ai_assistant_db") # You can name your database anything
        chat_history_collection = db.get_collection("chat_history") # You can name your collection anything
        print("✅ Successfully connected to MongoDB.")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not connect to MongoDB. Chat history will not be saved. Error: {e}")
else:
    print("WARNING: MONGO_URI environment variable not found. Chat history will not be saved.")
# --- END NEW SECTION ---


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
    return render_template('coming_soon.html')


# --- Helper Functions for File Processing (No Changes Here) ---
def extract_text_from_pdf(pdf_bytes):
    try:
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        return "".join(page.get_text() for page in pdf_document)
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return ""


def extract_text_from_docx(docx_bytes):
    try:
        document = docx.Document(io.BytesIO(docx_bytes))
        return "\n".join([para.text for para in document.paragraphs])
    except Exception as e:
        print(f"Error extracting DOCX text: {e}")
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


def get_video_id(video_url):
    video_id_match = re.search(r"(?:v=|\/|youtu\.be\/)([a-zA-Z0-9_-]{11})",
                               video_url)
    return video_id_match.group(1) if video_id_match else None


def get_youtube_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([d['text'] for d in transcript_list])
    except Exception as e:
        print(f"Error getting YouTube transcript: {e}")
        return None


# --- Main Chat Logic ---
@app.route('/chat', methods=['POST'])
def chat():
    # Diagnostic code can remain as is, no changes needed there.

    try:
        data = request.json
        user_message = data.get('text', '')
        file_data = data.get('fileData')
        file_type = data.get('fileType', '')

        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt_parts = []
        if user_message:
            prompt_parts.append(user_message)

        # Priority 1: Handle a YouTube Link (No changes in this block)
        if "youtube.com" in user_message or "youtu.be" in user_message:
            video_id = get_video_id(user_message)
            if video_id:
                transcript = get_youtube_transcript(video_id)
                if transcript:
                    youtube_prompt = f"Please provide a detailed and easy-to-understand summary of the following YouTube video transcript:\n\nTranscript:\n---\n{transcript}"
                    response = model.generate_content(youtube_prompt)
                    # --- NEW: Save to MongoDB ---
                    if chat_history_collection is not None:
                        try:
                            chat_history_collection.insert_one({
                                "user_message": user_message,
                                "ai_response": response.text,
                                "type": "youtube_summary",
                                "timestamp": datetime.utcnow()
                            })
                        except Exception as e:
                            print(f"Error saving chat to MongoDB: {e}")
                    # --- END NEW SECTION ---
                    return jsonify({'response': response.text})
                else:
                    return jsonify({
                        'response': "Sorry, I couldn't get the transcript for that video. It might be a live stream, or captions may be disabled."
                    })
            else:
                return jsonify({
                    'response': "That doesn't look like a valid YouTube link. Please provide the full URL."
                })

        # Priority 2: Check for keywords to get a file from GitHub (No changes in this block)
        matched_filename = next(
            (filename
             for keyword, filename in PDF_KEYWORDS.items()
             if keyword in user_message.lower()), None)
        if matched_filename:
            file_bytes = get_file_from_github(matched_filename)
            if file_bytes:
                pdf_text = extract_text_from_pdf(file_bytes)
                if pdf_text.strip():
                    prompt_parts.append(
                        f"\n\n--- Start of Document: {matched_filename} ---\n{pdf_text}\n--- End of Document ---"
                    )
                else:
                    return jsonify({
                        'response': f"Sorry, I downloaded '{matched_filename}' but could not extract any text from it. It might be a scanned document."
                    })
            else:
                return jsonify({
                    'response': f"Sorry, I could not download '{matched_filename}' from GitHub."
                })

        # Priority 3: Handle a direct file upload (No changes in this block)
        if file_data:
            try:
                file_bytes = base64.b64decode(file_data)
                file_processed = False

                if 'pdf' in file_type:
                    pdf_text = extract_text_from_pdf(file_bytes)
                    if pdf_text.strip():
                        prompt_parts.append(
                            f"\n\n--- Start of Uploaded PDF ---\n{pdf_text}\n--- End of Uploaded PDF ---"
                        )
                        file_processed = True
                    else:
                        return jsonify({
                            'response': "Sorry, I could not extract any text from the uploaded PDF. It might be a scanned document."
                        })

                elif 'word' in file_type or 'vnd.openxmlformats-officedocument.wordprocessingml.document' in file_type:
                    docx_text = extract_text_from_docx(file_bytes)
                    if docx_text.strip():
                        prompt_parts.append(
                            f"\n\n--- Start of Uploaded Document ---\n{docx_text}\n--- End of Uploaded Document ---"
                        )
                        file_processed = True
                    else:
                        return jsonify({
                            'response': "Sorry, the uploaded DOCX file appears to be empty."
                        })

                elif 'image' in file_type:
                    image = Image.open(io.BytesIO(file_bytes))
                    prompt_parts.append(image)
                    file_processed = True

                if not file_processed:
                    return jsonify({
                        'response': f"Sorry, I don't know how to handle the file type '{file_type}'. Please upload a PDF, DOCX, or image file."
                    })

            except Exception as e:
                print(f"Error decoding or processing file data: {e}")
                return jsonify({
                    'response': "Sorry, there was an error processing the uploaded file. It might be corrupted."
                })

        # Generate AI Response
        if not prompt_parts:
            return jsonify(
                {'response': "Please ask a question or upload a file."})

        has_text = any(
            isinstance(part, str) and part.strip() for part in prompt_parts)
        has_image = any(isinstance(part, Image.Image) for part in prompt_parts)

        if has_image and not has_text:
            prompt_parts.insert(0,
                                "What is in this image? Describe it in detail.")

        response = model.generate_content(prompt_parts)
        ai_response = response.text

        # --- NEW: Save to MongoDB ---
        # This is the general catch-all for saving conversations
        if chat_history_collection is not None:
            try:
                chat_history_collection.insert_one({
                    "user_message": user_message,
                    "ai_response": ai_response,
                    "has_file": bool(file_data),
                    "file_type": file_type if file_data else None,
                    "timestamp": datetime.utcnow()
                })
            except Exception as e:
                print(f"Error saving chat to MongoDB: {e}")
        # --- END NEW SECTION ---

        return jsonify({'response': ai_response})

    except Exception as e:
        print(f"A critical error occurred: {e}")
        if "429" in str(e) and "quota" in str(e).lower():
            user_facing_error = "Sorry, the daily limit for the AI service has been reached. Please try again tomorrow."
        else:
            user_facing_error = "Sorry, something went wrong. Please try again."
        return jsonify({'response': user_facing_error})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
