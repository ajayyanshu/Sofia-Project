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

# --- Securely Load API Keys from Render Environment ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

# --- Configure API Services ---
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    print("CRITICAL ERROR: GOOGLE_API_KEY environment variable not found.")

# --- GitHub PDF Configuration ---
GITHUB_USER = "ajayyanshu"
GITHUB_REPO = "collegeproject"
GITHUB_FOLDER_PATH = "upload pdf"
AVAILABLE_PDFS = [
    "2016 - Hindi (7402-01).pdf",
    "2023 - English (7403-01).pdf",
    "2023 - Hindi (7402-01).pdf",
    "2025 - English (7403-01).pdf",
    "2025 - Hindi (7402-01).pdf",
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
    message_lower = message.lower()
    if "2016" in message_lower and "hindi" in message_lower: return "2016 - Hindi (7402-01).pdf"
    if "2023" in message_lower and "english" in message_lower: return "2023 - English (7403-01).pdf"
    if "2023" in message_lower and "hindi" in message_lower: return "2023 - Hindi (7402-01).pdf"
    if "2025" in message_lower and "english" in message_lower: return "2025 - English (7403-01).pdf"
    if "2025" in message_lower and "hindi" in message_lower: return "2025 - Hindi (7402-01).pdf"
    return None

def get_video_id(video_url):
    video_id_match = re.search(r"(?:v=|\/|youtu\.be\/)([a-zA-Z0-9_-]{11})", video_url)
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
    try:
        if not GOOGLE_API_KEY:
             return jsonify({'error': 'The server is missing the required API keys.'}), 500

        data = request.json
        user_message = data.get('text', '')
        file_data = data.get('fileData')
        file_type = data.get('fileType')
        mode = data.get('mode')

        # --- Mode: Create Image ---
        if any(word in user_message.lower() for word in ["image", "photo", "picture", "pic"]):
            try:
                model = genai.GenerativeModel("gemini-2.5-flash-image-preview")
                response = model.generate_images(prompt=user_message)

                if response.generated_images:
                    img = response.generated_images[0]
                    image_b64 = base64.b64encode(img.image_bytes).decode("utf-8")
                    image_url = f"data:image/png;base64,{image_b64}"

                    return jsonify({
                        "response": f"Here’s the image for: {user_message}",
                        "imageUrl": image_url
                    })
                else:
                    return jsonify({
                        "response": "⚠️ Image generation not available right now. Try a different prompt.",
                        "imageUrl": None
                    })
            except Exception as e:
                # Fallback if API key doesn’t support images
                return jsonify({
                    "response": "⚠️ Image generation is currently not supported. Try searching online.",
                    "error": str(e),
                    "imageUrl": None
                })


        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # --- Mode: Web Search ---
        if mode == 'web_search':
            response = model.generate_content(user_message, tools=[genai.Tool(google_search=genai.GoogleSearch())])
            return jsonify({'response': response.text})

        if "youtube.com" in user_message or "youtu.be" in user_message:
            video_id = get_video_id(user_message)
            if video_id:
                transcript = get_youtube_transcript(video_id)
                if transcript:
                    prompt = f"Please provide a detailed and easy-to-understand summary of the following YouTube video transcript:\n\n{transcript}"
                    response = model.generate_content(prompt)
                    return jsonify({'response': response.text})
                else:
                    return jsonify({'response': "Sorry, I couldn't get the transcript for that video."})

        matched_filename = find_matching_pdf(user_message)
        if matched_filename:
            download_url = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/raw/main/{GITHUB_FOLDER_PATH.replace(' ', '%20')}/{matched_filename.replace(' ', '%20')}"
            if "download" in user_message.lower() or "link" in user_message.lower():
                ai_response = f"Of course! Here is the download link for '{matched_filename}':<br><br><a href='{download_url}' target='_blank' style='color: blue; text-decoration: underline;'>Download the paper here</a>"
                return jsonify({'response': ai_response})

            file_bytes = get_file_from_github(matched_filename)
            if file_bytes:
                document_text = extract_text_from_pdf(file_bytes)
                if document_text:
                    prompt = f"Based on '{matched_filename}', answer: '{user_message}'\n\nContent:\n{document_text}"
                    response = model.generate_content(prompt)
                    ai_response = f"I found **{matched_filename}**.\\n\\n" + response.text
                    ai_response += f"<br><br><a href='{download_url}' target='_blank' style='color: blue; text-decoration: underline;'>Download this paper here</a>"
                    return jsonify({'response': ai_response})
                else:
                    error_link = f"<a href='{download_url}' target='_blank' style='color: blue; text-decoration: underline;'>download it here</a>"
                    return jsonify({'response': f"Sorry, I downloaded '{matched_filename}', but couldn't read its content. You can still {error_link}."})
            else:
                return jsonify({'response': f"Sorry, I could not download '{matched_filename}' from GitHub."})

        if file_data:
            file_bytes = base64.b64decode(file_data)
            if 'pdf' in file_type:
                document_text = extract_text_from_pdf(file_bytes)
                if document_text:
                    prompt = f"Based on the uploaded PDF, answer: '{user_message}'\n\nContent:\n{document_text}"
                    response = model.generate_content(prompt)
                    return jsonify({'response': response.text})
                else:
                    return jsonify({'response': "Sorry, I could not read the content of the uploaded PDF."})
            elif 'image' in file_type:
                image = Image.open(io.BytesIO(file_bytes))
                response = model.generate_content([user_message, image])
                return jsonify({'response': response.text})

        response = model.generate_content(user_message)
        return jsonify({'response': response.text})

    except Exception as e:
        print(f"A critical error occurred: {e}")
        return jsonify({'error': 'An internal error occurred.'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

