# Sofia AI 🤖

Sofia AI is a full-stack, intelligent AI chat assistant built with a Python (Flask) backend, a pure JavaScript (no framework) frontend, and a MongoDB database. It's designed to be a versatile and feature-rich chat application, integrating multiple AI models (Google Gemini and Groq), web search, file analysis, and user authentication.

### ✨ Features

* **Multi-Model AI:** Dynamically routes requests to **Google Gemini** (for powerful, general-purpose, and multimodal chats) and **Groq** (for high-speed text generation, contextual search, and code analysis).
* **Full User Authentication:** Secure user signup, login, password reset (via email), and session management using Flask-Login.
* **Rich Chat Interface:** Real-time chat with Markdown rendering, code block highlighting, and message actions (copy, share, etc.).
* **Contextual Web Search:** A "Web Search" mode that uses the Serper.dev API to fetch real-time Google search results and provide context-aware, cited answers.
* **File & Code Analysis:**
    * Upload and chat with images, PDFs, and `.docx` files.
    * A special "Code Security Scan" mode for vulnerability analysis.
* **Personal Library:** Users can upload files to a persistent "Library," where they are stored, automatically summarized by AI, and can be retrieved for use in future chats.
* **Voice Capabilities:**
    * **Voice-to-Text:** Use your microphone to dictate messages.
    * **Text-to-Speech:** Listen to AI responses.
    * **Voice Conversation Mode:** Full hands-free, voice-activated conversation.
* **Persistent Chat History:** Conversations are saved to the database. Users can load, rename, and delete past chats.
* **Subscription & Usage Tiers:** Built-in logic for "Free" and "Premium" user tiers, including daily message/search limits and a (client-side) Razorpay payment button for upgrades.
* **User Profile Management:** Dark/Light/System theme, language selection, and secure "Delete Account" option.

### 🖼️ Screenshots

*(I recommend adding a screenshot of your application here!)*

`![Sofia AI Screenshot](link-to-your-screenshot.png)`

---

### 🛠️ Tech Stack

* **Backend:**
    * **Framework:** Flask
    * **Database:** MongoDB (with `pymongo`)
    * **Authentication:** Flask-Login, Flask-Mail (for password resets)
* **Frontend:**
    * **Markup:** HTML
    * **Styling:** Tailwind CSS
    * **Logic:** Vanilla JavaScript (ES6+)
    * **Libraries:** Showdown (for Markdown), Razorpay (for payments)
* **Core APIs & Services:**
    * **Google Gemini API:** For primary AI generation.
    * **Groq API:** For high-speed text and code analysis.
    * **Serper.dev API:** For real-time Google Search results.
    * **Web Speech API:** For browser-based voice I/O.
* **Python Libraries:**
    * `PyMuPDF (fitz)`: For PDF text extraction.
    * `python-docx`: For `.docx` text extraction.
    * `Pillow (PIL)`: For image processing.

---

### 🚀 Getting Started

Follow these instructions to get a copy of the project up and running on your local machine.

#### 1. Prerequisites

* Python 3.8+
* MongoDB account (a free cluster on MongoDB Atlas is perfect)
* API keys for Google Gemini, Groq, and Serper.dev

#### 2. Installation & Setup

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/ajayyanshu/Sofia-Project.git
    cd Sofia-Project
    ```

2.  **Set up the project structure:**
    Your `app.py` file is set up to serve files from `static` and `templates` folders. You must place your files in the correct directories:

    ```
    /
    ├── app.py              <-- Your Python file
    ├── requirements.txt    <-- Generated for you
    ├── .env.example        <-- Generated for you
    ├── templates/
    │   └── index.html      <-- Move index.html here
    │   └── login.html      <-- (You will need to create this)
    │   └── signup.html     <-- (You will need to create this)
    └── static/
        ├── style.css       <-- Move style.css here
        └── script.js       <-- Move script.js here
    ```

3.  **Create a Python virtual environment:**
    ```sh
    # Windows
    python -m venv venv
    venv\Scripts\activate

    # macOS / Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

4.  **Install dependencies:**
    ```sh
    pip install -r requirements.txt
    ```

5.  **Set up environment variables:**
    Copy the example file and fill in your API keys and database URI.
    ```sh
    cp .env.example .env
    ```
    Now, open the `.env` file in your text editor and add your secret keys.

#### 3. Running the Application

1.  **Load environment variables:**
    *(Note: Flask often does this automatically if `python-dotenv` is installed and you use `flask run`)*
    ```sh
    # (If needed, depending on your OS)
    # macOS / Linux
    export $(grep -v '^#' .env | xargs)
    ```

2.  **Run the Flask app:**
    ```sh
    flask run
    ```
    Or, for development:
    ```sh
    python app.py
    ```

3.  Open your browser and navigate to `http://127.0.0.1:5000`.

---
## Donations

If you find HashCrackPro useful and would like to support its development, please consider making a donation. Your contributions help us maintain and improve the project.

[![Donate](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEjd9o3K2CK9LObsNOok8nY4WYMSwKkhAzsz7NDxmO8eZU-d8dw4kEKW1Ycp3QpzVsT2okmWwoBXLXB757yQhoL0Xandlt3Wjwdw7tTlU4hTGdJcFH1tq1i0K6o7uTTGK-20fKi7DQhgoYEZkHI1-Y9UPBWAjiNhtn8TceqHS4O6kTaaeNweZe6OBJ0Ve0ou/s424/download.png)](https://buymeacoffee.com/ajayyanshu)

[![Donate](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEgMgW12teTME3e1Ap4Lc6MuQ7mFoEfyKINWAQ8dDx0vRR6XXNXGNXSaOgFdFhB2kTv8d6r5TiMIpRqJv9EnrM2YU1Syrvq4KO32YcmjiJk-GLuxHGMwfTPIO1Zz1JE2lCSMTRcrY1JJues1jpC4qotBNumo3d3dC79uRFulGasM8vzSdneJmzunxKDiUKI2/s386/upi.PNG)]()


### 📄 License

This project is open-source. Feel free to add a license file  [License](https://github.com/ajayyanshu/Sofia-Project/blob/main/LICENSE).

## Contact with us

For inquiries and support, please contact us at [ajayyanshu@gmail.com](mailto:ajayyanshu@gmail.com).


## Contributions

Contributions are welcome! Please fork this repository and submit pull requests with your enhancements.


---
