import os
from flask import Flask, render_template

app = Flask(__name__, template_folder='templates')

@app.route('/')
def home():
    gemini_api_key = "AIzaSyDSVYwHKLSd_R4HOKDTW8dCY1eY9TvbnP4"
    return render_template('index.html', gemini_api_key=gemini_api_key)

if __name__ == '__main__':
    app.run(debug=True)
