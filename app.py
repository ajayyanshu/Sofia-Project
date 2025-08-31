from flask import Flask, request, jsonify
import os
import google.generativeai as genai

app = Flask(__name__)

# Load API key (from environment variables in Render)
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

@app.route("/chat", methods=["POST"])
def chat():
    user_msg = request.json.get("message")
    try:
        response = genai.chat.create(
            model="gpt-3.5-mini",
            messages=[{"role": "user", "content": user_msg}]
        )
        # Send the AI reply back to frontend
        return jsonify({"reply": response.last})
    except Exception as e:
        return jsonify({"reply": f"Error: {str(e)}"})
