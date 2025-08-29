from flask import Flask, request, jsonify, render_template_string
import fitz  # PyMuPDF
from PIL import Image
import io

app = Flask(__name__)

# -----------------------------
# Home page with simple HTML form
# -----------------------------
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Flask Bot</title>
</head>
<body>
    <h1>Welcome to Flask Bot</h1>
    
    <h2>Chat with Bot</h2>
    <form id="chatForm">
        <input type="text" name="message" placeholder="Type your message" required>
        <button type="submit">Send</button>
    </form>
    <p id="chatReply"></p>

    <h2>Upload File</h2>
    <form id="uploadForm" enctype="multipart/form-data">
        <input type="file" name="file" required>
        <button type="submit">Upload</button>
    </form>
    <p id="uploadReply"></p>

<script>
    const chatForm = document.getElementById('chatForm');
    const chatReply = document.getElementById('chatReply');
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = chatForm.message.value;
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message})
        });
        const data = await response.json();
        chatReply.textContent = data.reply;
    });

    const uploadForm = document.getElementById('uploadForm');
    const uploadReply = document.getElementById('uploadReply');
    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(uploadForm);
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        uploadReply.textContent = data.reply;
    });
</script>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def home():
    return render_template_string(HTML_PAGE)

# -----------------------------
# Chat route
# -----------------------------
@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    reply = f"Bot reply for: {user_message}"
    return jsonify({"reply": reply})

# -----------------------------
# File upload route
# -----------------------------
@app.route("/upload", methods=["POST"])
def upload_file():
    file = request.files.get("file")
    if not file:
        return jsonify({"reply": "No file uploaded."}), 400

    if file.filename.endswith(".pdf"):
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text = "".join([page.get_text() for page in doc])
        reply = f"📄 I read your PDF. Extracted text:\n{text[:300]}..."

    elif file.filename.endswith((".png", ".jpg", ".jpeg")):
        image = Image.open(file.stream)
        reply = f"🖼️ Got your image ({image.size[0]}x{image.size[1]})."

    else:
        reply = f"Uploaded file: {file.filename} (Not processed yet)."

    return jsonify({"reply": reply})

# -----------------------------
# Run Flask app
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
