from flask import Flask, render_template, request, jsonify
import openai

app = Flask(__name__)

# 🔑 Add your OpenAI API Key here
openai.api_key = "YOUR_API_KEY"

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/get", methods=["POST"])
def get_bot_response():
    user_text = request.json["message"]

    # Call OpenAI GPT model
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # Or "gpt-4" if you have access
        messages=[
            {"role": "system", "content": "You are a helpful college assistant chatbot."},
            {"role": "user", "content": user_text}
        ]
    )

    reply = response["choices"][0]["message"]["content"]
    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(debug=True)

