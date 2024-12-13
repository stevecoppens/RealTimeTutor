import asyncio
import base64
import json
import os
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from websockets.asyncio.client import connect
import pyaudio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GeminiConnection:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.model = "gemini-2.0-flash-exp"
        self.uri = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?key={self.api_key}"
        self.ws = None
        self.audio_queue = asyncio.Queue()

    async def connect(self):
        self.ws = await connect(
            self.uri,
            additional_headers={"Content-Type": "application/json"}
        )
        
        # Initialize the connection with model setup
        await self.ws.send(json.dumps({
            "setup": {
                "model": f"models/{self.model}",
                "generation_config": {
                    "speech_config": {
                        "voice_config": {
                            "prebuilt_voice_config": {
                                "voice_name": "Aoede"
                            }
                        }
                    }
                }
            }
        }))
        await self.ws.recv()

    async def send_audio(self, audio_data):
        if not self.ws:
            await self.connect()
            
        await self.ws.send(json.dumps({
            "realtime_input": {
                "media_chunks": [{
                    "data": audio_data,
                    "mime_type": "audio/pcm"
                }]
            }
        }))

    async def close(self):
        if self.ws:
            await self.ws.close()
            self.ws = None

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    gemini = GeminiConnection()
    
    try:
        await gemini.connect()
        
        async def receive_from_gemini():
            while True:
                msg = await gemini.ws.recv()
                response = json.loads(msg)
                
                try:
                    # Check for text response
                    text = response.get("serverContent", {}).get("modelTurn", {}).get("parts", [{}])[0].get("text")
                    if text:
                        await websocket.send_json({
                            "type": "text",
                            "data": text
                        })

                    # Check for audio response
                    audio_data = response.get("serverContent", {}).get("modelTurn", {}).get("parts", [{}])[0].get("inlineData", {}).get("data")
                    if audio_data:
                        await websocket.send_json({
                            "type": "audio",
                            "data": audio_data  # Already base64 encoded
                        })

                    # Check for turn completion
                    turn_complete = response.get("serverContent", {}).get("turnComplete", False)
                    if turn_complete:
                        await websocket.send_json({
                            "type": "turn_complete",
                            "data": True
                        })
                        
                except Exception as e:
                    print(f"Error processing Gemini response: {e}")

        # Start receiving from Gemini in the background
        receive_task = asyncio.create_task(receive_from_gemini())
        
        while True:
            data = await websocket.receive_json()
            
            if data["type"] == "audio":
                # Forward the audio data to Gemini
                await gemini.send_audio(data["data"].split(',')[1])  # Remove data URL prefix
                
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
    finally:
        await gemini.close()
        if not websocket.client_state.is_disconnected:
            await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)