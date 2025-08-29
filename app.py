from flask import Flask, request, jsonify
import fitz  # PyMuPDF for PDF
from PIL import Image
import io

app = Flask(__name__)

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    # TODO: Send to Gemini/OpenAI API
    reply = f"Bot reply for: {user_message}"
    return jsonify({"reply": reply})

@app.route("/upload", methods=["POST"])
def upload_file():
    file = request.files["file"]

    if file.filename.endswith(".pdf"):
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        reply = f"📄 I read your PDF. Extracted text:\n{text[:300]}..."
    
    elif file.filename.endswith((".png", ".jpg", ".jpeg")):
        image = Image.open(file.stream)
        reply = f"🖼️ Got your image ({image.size[0]}x{image.size[1]}). I can send this to AI Vision model."

    else:
        reply = f"Uploaded file: {file.filename} (Not processed yet)."

    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(debug=True)
