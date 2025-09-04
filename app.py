import os
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi
import re

app = Flask(__name__, template_folder='templates')

# Place your YouTube API key here
YOUTUBE_API_KEY = "AIzaSyBWMoLPnKlg_hCV2huRc2LlUYYLDXKCsYE"

@app.route('/')
def home():
    gemini_api_key = os.environ.get("GEMINI_API_KEY") or "AIzaSyDSVYwHKLSd_R4HOKDTW8dCY1eY9TvbnP4"
    return render_template('index.html', gemini_api_key=gemini_api_key)

def get_youtube_transcript(video_url):
    video_id_match = re.search(r"v=([a-zA-Z0-9_-]{11})", video_url)
    if not video_id_match:
        return None
    
    video_id = video_id_match.group(1)
    transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
    transcript_text = " ".join([d['text'] for d in transcript_list])
    return transcript_text

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('text')
        model_name = request.json.get('model')
        api_key = request.json.get('apiKey')
        is_vision = request.json.get('isVision')
        image_data = request.json.get('image')
        
        genai.configure(api_key=api_key)
        
        # Check for YouTube URL in the message
        if "youtube.com" in user_message or "youtu.be" in user_message:
            transcript = get_youtube_transcript(user_message)
            if transcript:
                prompt = f"Summarize the following YouTube video transcript: {transcript}"
            else:
                prompt = "Could not retrieve transcript for the given YouTube video."
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            ai_response = response.text
            return jsonify({'response': ai_response})
        
        # Handle live data search
        tools = []
        if any(keyword in user_message.lower() for keyword in ["what is the latest", "who won", "what's the current"]):
            tools.append({"google_search": {}})

        # Handle image or PDF input
        if is_vision and image_data:
            from PIL import Image
            import io
            import base64

            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            vision_model = genai.GenerativeModel('gemini-1.5-flash')
            response = vision_model.generate_content(['Describe the image.', image])
            ai_response = response.text
            return jsonify({'response': ai_response})

        model = genai.GenerativeModel('gemini-1.5-flash', tools=tools)
        response = model.generate_content(user_message)
        ai_response = response.text
        
        return jsonify({'response': ai_response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
