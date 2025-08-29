from flask import Flask, request, jsonify
import fitz  # PyMuPDF for PDF handling
from PIL import Image
import io

# Initialize Flask app
app = Flask(__name__)

# -----------------------------
# Route: Chat message handler
# -----------------------------
@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    # TODO: Send this message to Gemini/OpenAI API
    reply = f"Bot reply for: {user_message}"
    return jsonify({"reply": reply})

# -----------------------------
# Route: File upload handler
# -----------------------------
@app.route("/upload", methods=["POST"])
def upload_file():
    file = request.files.get("file")

    if not file:
        return jsonify({"reply": "No file uploaded."}), 400

    if file.filename.endswith(".pdf"):
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        reply = f"📄 I read your PDF. Extracted text:\n{text[:300]}..."  # only first 300 chars

    elif file.filename.endswith((".png", ".jpg", ".jpeg")):
        image = Image.open(file.stream)
        reply = f"🖼️ Got your image ({image.size[0]}x{image.size[1]}). I can send this to AI Vision model."

    else:
        reply = f"Uploaded file: {file.filename} (Not processed yet)."

    return jsonify({"reply": reply})

# -----------------------------
# Run the Flask app
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
