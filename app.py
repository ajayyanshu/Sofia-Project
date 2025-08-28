from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import os

app = Flask(__name__)

# Set API key from environment variable
genai.configure(api_key=os.getenv("AIzaSyDvLAK3y_jJP7GNvVrVHYv0Vz7LWviLXmw"))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message")

    # Create Gemini model
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content(user_message)

    return jsonify({"reply": response.text})

if __name__ == "__main__":
    app.run(debug=True)
