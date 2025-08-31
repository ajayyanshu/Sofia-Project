body {
  font-family: Arial, sans-serif;
  background: #f0f0f0;
  margin: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
}

.chat-container {
  width: 350px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 0 10px rgba(0,0,0,0.2);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-box {
  flex: 1;
  padding: 10px;
  overflow-y: auto;
}

.user-msg {
  text-align: right;
  margin: 5px;
  background: #d1f7c4;
  padding: 8px;
  border-radius: 8px;
}

.ai-msg {
  text-align: left;
  margin: 5px;
  background: #e6e6e6;
  padding: 8px;
  border-radius: 8px;
}

.input-box {
  display: flex;
  border-top: 1px solid #ccc;
}

.input-box input {
  flex: 1;
  border: none;
  padding: 10px;
}

.input-box button {
  background: #007bff;
  color: white;
  border: none;
  padding: 10px;
  cursor: pointer;
}
