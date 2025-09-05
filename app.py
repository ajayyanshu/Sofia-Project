import os
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi
import re

# Import the Google API client library
from googleapiclient.discovery import build


# --- Your API Keys ---
# ⚠️ This is NOT recommended for security reasons. Use environment variables for production.
GOOGLE_API_KEY = "AIzaSyDSVYwHKLSd_R4HOKDTW8dCY1eY9TvbnP4" # For Gemini AI
YOUTUBE_API_KEY = "AIzaSyBnuUNg3S9n5jczlw_4p8hr-8zrAEKNfbI" # Your new YouTube key

# --- Configure Services ---
genai.configure(api_key=GOOGLE_API_KEY)
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)


user_profiles = {}
app = Flask(__name__, template_folder='templates')

@app.route('/')
def home():
    return render_template('index.html')

def get_video_id(video_url):
    """Extracts the YouTube video ID from a URL."""
    video_id_match = re.search(r"(?:v=|\/)([a-zA-Z0-9_-]{11}).*", video_url)
    return video_id_match.group(1) if video_id_match else None

def get_video_details(video_id):
    """Gets video details like title using the YouTube Data API."""
    try:
        request = youtube.videos().list(
            part="snippet",
            id=video_id
        )
        response = request.execute()
        if response['items']:
            title = response['items'][0]['snippet']['title']
            return {'title': title}
        return None
    except Exception as e:
        print(f"Error getting video details: {e}")
        return None

def get_youtube_transcript(video_id):
    """Gets the transcript using youtube-transcript-api (no key needed)."""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([d['text'] for d in transcript_list])
    except Exception as e:
        print(f"Error fetching transcript: {e}")
        return None

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('text')
        user_id = request.json.get('userId')

        if user_id not in user_profiles:
            user_profiles[user_id] = {'history': []}
        user_profile = user_profiles[user_id]
        
        # --- YouTube Video Logic ---
        if "youtube.com" in user_message or "youtu.be" in user_message:
            video_id = get_video_id(user_message)
            if not video_id:
                return jsonify({'response': "That doesn't look like a valid YouTube link."})

            # 1. Get transcript (doesn't use your key)
            transcript = get_youtube_transcript(video_id)
            if not transcript:
                return jsonify({'response': "Sorry, I couldn't get the transcript for that video."})
            
            # 2. Get video details (uses your new key!)
            details = get_video_details(video_id)
            video_title = details['title'] if details else "this video"
            
            prompt = f"Please provide a detailed summary for the YouTube video titled '{video_title}'. Here is the transcript:\n\n{transcript}"
            
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            ai_response = response.text
            
            return jsonify({'response': ai_response})

        # --- Standard Chat Logic (and other features) ---
        model = genai.GenerativeModel('gemini-1.5-flash')
        chat_session = model.start_chat(history=user_profile['history'])
        response = chat_session.send_message(user_message)
        ai_response = response.text
        user_profile['history'] = chat_session.history
        
        return jsonify({'response': ai_response})

    except Exception as e:
        print(f"An error occurred in /chat endpoint: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
