import os
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi
import re
from google.generativeai import GenerativeModel
from google.generativeai.types import Tool

# Placeholder for user data (in a real app, this would be a database)
user_profiles = {}

app = Flask(__name__, template_folder='templates')

@app.route('/')
def home():
    # Load the API key securely from environment variables
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    # 🚨 Important: Do NOT hardcode the key here.
    if not gemini_api_key:
        return "Error: GEMINI_API_KEY environment variable not set.", 500
    return render_template('index.html', gemini_api_key=gemini_api_key)

def get_youtube_transcript(video_url):
    """
    Fetches the transcript for a YouTube video from its URL.
    Includes error handling and supports multiple URL formats.
    """
    try:
        # Regex to find video ID from different YouTube URL formats
        video_id_match = re.search(r"(?:v=|\/)([a-zA-Z0-9_-]{11}).*", video_url)
        
        if not video_id_match:
            return None
        
        video_id = video_id_match.group(1)
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([d['text'] for d in transcript_list])
        return transcript_text
    except Exception as e:
        # This will catch errors if transcripts are disabled or the video is invalid
        print(f"Error fetching transcript for {video_url}: {e}")
        return None

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('text')
        model_name = request.json.get('model')
        api_key = request.json.get('apiKey')
        is_vision = request.json.get('isVision')
        image_data = request.json.get('image')
        user_id = request.json.get('userId')
        
        # User personalization logic (in-memory)
        if user_id not in user_profiles:
            user_profiles[user_id] = {'history': []}
        
        user_profile = user_profiles[user_id]

        genai.configure(api_key=api_key)
        
        # Check for YouTube URL and handle it
        if "youtube.com" in user_message or "youtu.be" in user_message:
            transcript = get_youtube_transcript(user_message)
            if transcript:
                prompt = f"Please provide a detailed summary of the following YouTube video transcript:\n\n{transcript}"
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(prompt)
                ai_response = response.text
            else:
                ai_response = "Sorry, I couldn't retrieve the transcript for that YouTube video. The video might not exist, or transcripts may be disabled."
            
            user_profile['history'].append({'role': 'user', 'parts': [{'text': user_message}]})
            user_profile['history'].append({'role': 'model', 'parts': [{'text': ai_response}]})
            return jsonify({'response': ai_response})
        
        # Handle image input
        if is_vision and image_data:
            from PIL import Image
            import io
            import base64

            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            vision_model = genai.GenerativeModel('gemini-1.5-flash')
            # You can combine the user's text message with the image
            if user_message:
                response = vision_model.generate_content([user_message, image])
            else:
                response = vision_model.generate_content(['Describe this image.', image])

            ai_response = response.text
            
            user_profile['history'].append({'role': 'user', 'parts': [{'text': user_message}]}) # Store original prompt
            user_profile['history'].append({'role': 'model', 'parts': [{'text': ai_response}]})
            return jsonify({'response': ai_response})

        # Standard chat logic
        model = genai.GenerativeModel('gemini-1.5-flash')
        chat_session = model.start_chat(history=user_profile['history'])
        response = chat_session.send_message(user_message)
        ai_response = response.text
        
        # Update history from the chat session
        user_profile['history'] = chat_session.history
        
        return jsonify({'response': ai_response})

    except Exception as e:
        print(f"An error occurred in /chat endpoint: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
