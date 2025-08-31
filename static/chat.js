async function sendMessage() {
  const input = document.getElementById("userInput");
  const userMsg = input.value.trim();
  if (!userMsg) return;

  addMessage("You", userMsg);
  input.value = "";

  try {
    const res = await fetch("/chat", {   // 👈 same domain par call karega
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: userMsg })
    });

    const data = await res.json();
    addMessage("AI", data.reply);
  } catch (err) {
    addMessage("AI", "⚠️ Error: Server not reachable.");
  }
}

function addMessage(sender, text) {
  const chatBox = document.getElementById("chatBox");
  const msg = document.createElement("div");
  msg.className = sender === "You" ? "user-msg" : "ai-msg";
  msg.innerText = `${sender}: ${text}`;
  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;
}

