import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder='templates')

@app.route('/')
def home():
    gemini_api_key = "AIzaSyDSVYwHKLSd_R4HOKDTW8dCY1eY9TvbnP4"
    return render_template('index.html', gemini_api_key=gemini_api_key)

@app.route('/chat', methods=['POST'])
def chat():
    # Placeholder for your actual Gemini API call
    user_message = request.json['text']
    model_name = request.json['model']
    
    # In a real application, you would call the Gemini API here.
    ai_response = f"You are using the '{model_name}' model. You typed: '{user_message}'"
    
    return jsonify({'response': ai_response})

if __name__ == '__main__':
    app.run(debug=True)
