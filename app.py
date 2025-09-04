import os
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__, template_folder='templates')

@app.route('/')
def home():
    gemini_api_key = os.environ.get("GEMINI_API_KEY") or "AIzaSyDSVYwHKLSd_R4HOKDTW8dCY1eY9TvbnP4"
    return render_template('index.html', gemini_api_key=gemini_api_key)

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json['text']
        model_name = request.json['model']
        api_key = request.json['apiKey']
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Call the Gemini API with the user's message
        response = model.generate_content(user_message)
        ai_response = response.text

        return jsonify({'response': ai_response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
