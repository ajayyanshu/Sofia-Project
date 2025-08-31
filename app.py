from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import os

app = Flask(__name__)

# Gemini API Key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

@app.route("/")
def home():
    return render_template("index.html")   # 👈 yehi HTML page show karega

@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_msg = request.json.get("message")
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(user_msg)
        return jsonify({"reply": response.text})
    except Exception as e:
        return jsonify({"reply": f"⚠️ Error: {str(e)}"})

if __name__ == "__main__":
    app.run(debug=True)
