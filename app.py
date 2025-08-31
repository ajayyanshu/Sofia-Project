import os
from flask import Flask, render_template
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, template_folder='templates')

@app.route('/')
def home():
    gemini_api_key = os.getenv('GOOGLE_API_KEY')
    if not gemini_api_key:
        return "Internal Server Error: Gemini API key is not set. Please set the GOOGLE_API_KEY environment variable.", 500
    return render_template('recreated_ui.html', gemini_api_key=gemini_api_key)

if __name__ == '__main__':
    app.run(debug=True)
