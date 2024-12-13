
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from google import genai
import asyncio
import json
import os
from typing import Optional
import base64
import io
from PIL import Image

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini client
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_REGION", "us-central1")
client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
MODEL_ID = "gemini-2.0-flash-exp"

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    try:
        # Initialize chat session
        chat = client.chats.create(model=MODEL_ID)
        
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            if data["type"] == "video":
                # Handle video frame
                frame_data = base64.b64decode(data["data"].split(',')[1])
                image = Image.open(io.BytesIO(frame_data))
                
                # Send frame to Gemini
                response = chat.send_message([
                    genai.types.Part.from_image(image),
                    "What do you see in this frame?"
                ])
                
                # Send response back to client
                await websocket.send_json({
                    "type": "text",
                    "data": response.text
                })
                
            elif data["type"] == "audio":
                # Handle audio data
                audio_data = base64.b64decode(data["data"])
                
                # Send audio to Gemini
                response = chat.send_message([
                    genai.types.Part.from_bytes(audio_data, mime_type="audio/webm"),
                    "What was said in this audio?"
                ])
                
                # Send response back to client
                await websocket.send_json({
                    "type": "text",
                    "data": response.text
                })
                
    except Exception as e:
        print(f"Error: {e}")
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
