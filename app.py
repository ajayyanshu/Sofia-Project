import os
from dotenv import load_dotenv
import google.generativeai as genai
from flask import Flask, request, jsonify, render_template

# Load API Key
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("❌ GOOGLE_API_KEY not found.")

genai.configure(api_key=api_key)

app = Flask(__name__)

@app.route("/")
def home():
    # Ye index.html templates folder se load karega
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_msg = request.json.get("message", "")
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(user_msg)
    return jsonify({"reply": response.text})
