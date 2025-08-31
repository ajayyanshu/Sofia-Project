// ===== Elements =====
const chatArea   = document.getElementById("chatArea");
const userInput  = document.getElementById("userInput");
const sendBtn    = document.getElementById("sendBtn");
const fileBtn    = document.getElementById("fileBtn");
const fileInput  = document.getElementById("fileInput");
const sidebar    = document.getElementById("sidebar");
const menuBtn    = document.getElementById("menuBtn");
const mainContent= document.getElementById("mainContent");

// ===== Helpers =====
function addMessage(text, type) {
  const msg = document.createElement("div");
  msg.classList.add("message", type);
  msg.textContent = text;
  chatArea.appendChild(msg);
  chatArea.scrollTop = chatArea.scrollHeight;
  return msg;
}

async function getAIResponse(prompt) {
  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: prompt })
    });
    const data = await response.json();
    return data?.reply || "⚠️ No response from AI.";
  } catch (err) {
    return "❌ Error: " + err.message;
  }
}

// ===== Events =====
sendBtn.addEventListener("click", async () => {
  const text = userInput.value.trim();
  if (!text) return;

  addMessage(text, "sent");
  userInput.value = "";

  const thinking = addMessage("⏳ Thinking...", "received thinking");
  const reply = await getAIResponse(text);
  thinking.textContent = "🤖 " + reply;
  thinking.classList.remove("thinking");
});

userInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") sendBtn.click();
});

fileBtn.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
  if (fileInput.files.length > 0) {
    const file = fileInput.files[0];
    addMessage("📎 Uploaded: " + file.name, "sent");
  }
});

// Sidebar toggle
menuBtn.addEventListener("click", () => {
  sidebar.classList.toggle("open");
  mainContent.classList.toggle("shifted");
});
