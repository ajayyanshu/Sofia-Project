const express = require('express');
const dotenv = require('dotenv');
const path = require('path');

// Load environment variables from .env file for local development
dotenv.config();

const app = express();
const port = process.env.PORT || 3000;

// Serve static files from the root directory (where index.html is)
app.use(express.static(path.join(__dirname)));

// API endpoint to get the Gemini API key
app.get('/api/key', (req, res) => {
  // This line reads the environment variable you set on Render
  const apiKey = process.env.GOOGLE_API_KEY; 
  if (apiKey) {
    res.json({ apiKey: apiKey });
  } else {
    res.status(500).json({ error: 'API key not found on the server. Make sure the GOOGLE_API_KEY environment variable is set.' });
  }
});

// Fallback to serve index.html for any other requests
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});


app.listen(port, () => {
  console.log(`Server listening on port ${port}`);
});

