import os
from dotenv import load_dotenv
import google.generativeai as genai
from flask import Flask, request, jsonify

# Load .env
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("❌ GOOGLE_API_KEY not found. Please check your .env file.")

# Configure Gemini
genai.configure(api_key=api_key)

# Create Flask app
app = Flask(__name__)

@app.route("/")
def home():
    return "🚀 Gemini Chatbot is running on Render!"

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_msg = data.get("message", "")
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(user_msg)
    return jsonify({"reply": response.text})
