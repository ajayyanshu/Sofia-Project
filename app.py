from flask import Flask, render_template, request, jsonify
import openai
import os

app = Flask(__name__)

# Use environment variable for API key
openai.api_key = os.getenv("AIzaSyCIbfSriPTJKrmWS0jFzdf2GAvcMMgjf_I")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message")

    # Call OpenAI API
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=user_message,
        max_tokens=100
    )

    return jsonify({"reply": response.choices[0].text.strip()})

if __name__ == "__main__":
    app.run(debug=True)
