from flask import Flask, request, render_template, jsonify
import google.generativeai as genai
from dotenv import load_dotenv
import os

# Load .env
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

genai.configure(api_key=api_key)

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    response = genai.chat.create(
        model="chat-bison-001",
        messages=[{"author": "user", "content": user_message}]
    )
    return jsonify({"reply": response.last["content"]["text"]})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
