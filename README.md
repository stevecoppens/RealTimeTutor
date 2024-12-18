# Gemini Multimodal Playground ✨

A basic Python app for having voice conversations with Google's Gemini 2.0 AI model. Features real-time voice input and text-to-speech responses.

*Note: the full-stack version of this playground is still WIP. Please only use the Standalone script for now.*

https://github.com/user-attachments/assets/82228033-fcfb-4730-9723-3ed09e1979a2

## Getting Your Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the generated API key and paste it into the .env file (see below under Installation)

<img width="600" alt="API key creation" src="https://github.com/saharmor/gemini-multimodal-playground/blob/main/ai%20studio%20api%20key.png">

## Installation

**Important note**: This repo requires Python 3.12 to run

1. Clone this repository or download the standalone folder

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the required packages:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the standalone directory with your API key:
```
GEMINI_API_KEY=your_api_key_here
```

## Running the Application

1. Make sure your virtual environment is activated
2. Run the script:
```bash
python standalone.py
```

## Configuration Options

The application provides several configuration options through its GUI:

- **System Prompt**: The initial instructions given to Gemini about its role and behavior
- **Voice**: Choose from different voice options for Gemini's responses:
  - Puck
  - Charon
  - Kore
  - Fenrir
  - Aoede
- **Enable Google Search**: Allows Gemini to search the internet for current information (doesn't work yet)
- **Allow Interruptions**: Enables interrupting Gemini while it's speaking (see Troubleshooting below if Gemini constantly interrupts itself)

## Usage

1. Configure your desired settings in the GUI
2. Click "Start Gemini" to begin
3. Speak into your microphone when ready
4. The equalizer will show your audio levels in real-time
5. Gemini will respond with voice
6. Click "Stop Gemini" to end the session

## Troubleshooting

- **Audio feedback loop issue** - Gemini may interrupt itself when it detects its own voice output through your microphone. This occurs because the application processes all incoming audio, including Gemini's responses. To prevent this feedback loop, either:
  1. Disable the "Allow Interruptions" option in settings
  2. Use headphones/earphones to prevent your microphone from picking up Gemini's audio output
