# Gemini Multimodal Playground

A real-time multimodal playground for Google's Gemini 2.0 AI model, supporting both video and audio interactions.

## Features

- Real-time video streaming with camera + audio
- Audio-only streaming mode
- Text-to-speech playback of Gemini's responses
- WebSocket-based communication for low latency
- Modern UI with shadcn/ui components

## Prerequisites

- Python 3.8+
- Node.js 16+
- Google Cloud Project with Gemini API enabled
- Google Cloud credentials

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/gemini-multimodal-playground.git
cd gemini-multimodal-playground
```

2. Set up the backend:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Set up the frontend:
```bash
cd frontend
npm install
```

4. Configure environment variables:
- Copy `backend/.env.example` to `backend/.env` and update with your Google Cloud credentials
- Copy `frontend/.env.example` to `frontend/.env`

## Running the Application

1. Start the backend server:
```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
python main.py
```

2. In a new terminal, start the frontend:
```bash
cd frontend
npm run dev
```

3. Open http://localhost:3000 in your browser

## Development

- Backend is built with FastAPI and uses WebSockets for real-time communication
- Frontend is built with Next.js 14, TypeScript, and Tailwind CSS
- UI components from shadcn/ui library
- Real-time media handling with WebRTC and MediaRecorder APIs

## License

MIT
