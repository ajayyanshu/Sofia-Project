import os
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi
import re
from google.generativeai import GenerativeModel
from google.generativeai.types import Tool

# ⚠️ The API key is now hardcoded here. This is NOT secure.
GOOGLE_API_KEY = "AIzaSyDSVYwHKLSd_R4HOKDTW8dCY1eY9TvbnP4"

# Configure the generative AI model right away
genai.configure(api_key=GOOGLE_API_KEY)

# Placeholder for user data (in a real app, this would be a database)
user_profiles = {}

app = Flask(__name__, template_folder='templates')

@app.route('/')
def home():
    # We no longer need to pass the key from the backend to the template
    return render_template('index.html')

def get_youtube_transcript(video_url):
    try:
        video_id_match = re.search(r"(?:v=|\/)([a-zA-Z0-9_-]{11}).*", video_url)
        if not video_id_match:
            return None
        video_id = video_id_match.group(1)
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([d['text'] for d in transcript_list])
        return transcript_text
    except Exception as e:
        print(f"Error fetching transcript for {video_url}: {e}")
        return None

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('text')
        is_vision = request.json.get('isVision')
        image_data = request.json.get('image')
        user_id = request.json.get('userId')
        
        if user_id not in user_profiles:
            user_profiles[user_id] = {'history': []}
        user_profile = user_profiles[user_id]

        # The model is already configured, so we don't need to do it again here
        
        if "youtube.com" in user_message or "youtu.be" in user_message:
            transcript = get_youtube_transcript(user_message)
            if transcript:
                prompt = f"Please provide a detailed summary of the following YouTube video transcript:\n\n{transcript}"
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(prompt)
                ai_response = response.text
            else:
                ai_response = "Sorry, I couldn't retrieve the transcript for that YouTube video."
            
            user_profile['history'].append({'role': 'user', 'parts': [{'text': user_message}]})
            user_profile['history'].append({'role': 'model', 'parts': [{'text': ai_response}]})
            return jsonify({'response': ai_response})

        if is_vision and image_data:
            from PIL import Image
            import io
            import base64
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            vision_model = genai.GenerativeModel('gemini-1.5-flash')
            response = vision_model.generate_content([user_message, image])
            ai_response = response.text
            
            user_profile['history'].append({'role': 'user', 'parts': [{'text': user_message}]})
            user_profile['history'].append({'role': 'model', 'parts': [{'text': ai_response}]})
            return jsonify({'response': ai_response})

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
