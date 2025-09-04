const express = require('express');
const cors = require('cors');
const path = require('path');
const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname)));

app.post('/chat', (req, res) => {
    const userMessage = req.body.text;
    console.log(`Received message from frontend: ${userMessage}`);

    // Placeholder for your actual Gemini API call
    const aiResponse = `You are using the '${req.body.model}' model. You typed: '${userMessage}'`;

    res.json({ response: aiResponse });
});

app.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
});
