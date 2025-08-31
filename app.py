from flask import Flask, request, render_template, jsonify
import google.generativeai as genai
from dotenv import load_dotenv
import os

# Load .env
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

genai.configure(api_key=api_key)

app = Flask(__name__)

# Gemini model
model = genai.GenerativeModel("gemini-1.5-flash")

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_message = request.json.get("message")
        if not user_message:
            return jsonify({"reply": "⚠️ No message received"})

        # Generate content
        response = model.generate_content(user_message)

        # Agar Gemini ne kuch nahi diya
        if not hasattr(response, "text") or response.text is None:
            return jsonify({"reply": "⚠️ Gemini did not return a response"})

        return jsonify({"reply": response.text})
    except Exception as e:
        # Error ko return bhi karo aur Render logs me print bhi
        print("❌ Backend Error:", str(e))
        return jsonify({"reply": f"❌ Error: {str(e)}"})
        

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
