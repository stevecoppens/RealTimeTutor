import asyncio
import os
import json
import base64
from dotenv import load_dotenv
import numpy as np
import pyaudio
import torch
from websockets.client import connect

# load env variables from .env file
load_dotenv()

class VoiceActivityDetector:
    def __init__(self):
        self.model, _ = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                     model='silero_vad',
                                     force_reload=False)
        self.model.eval()

    def is_speech(self, audio_data: bytes) -> bool:
        # Convert raw bytes directly to numpy array of int16
        audio_np = np.frombuffer(audio_data, dtype=np.int16)
        
        # Convert to float32 and normalize to [-1, 1]
        audio_float = audio_np.astype(np.float32) / 32768.0
        
        # Convert to torch tensor
        audio_tensor = torch.from_numpy(audio_float)
        
        # Get speech probability
        speech_prob = self.model(audio_tensor, 16000).item()
        return speech_prob > 0.8  # Adjust threshold as needed

class GeminiConnection:
    def __init__(self):
        # Your Gemini API key. Must be set as an environment variable or replace here with a string.
        self.api_key = os.environ.get("GEMINI_API_KEY")
        # The Gemini 2.0 (flash) model name
        self.model = "gemini-2.0-flash-exp"
        
        # WebSocket endpoint for Gemini’s BidiGenerateContent API
        # Format: wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?key=API_KEY
        self.uri = (
            "wss://generativelanguage.googleapis.com/ws/"
            "google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"
            f"?key={self.api_key}"
        )
        self.ws = None
        self.vad = VoiceActivityDetector()


        # Audio settings
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.INPUT_RATE = 16000   # Gemini expects 16 kHz for input
        self.OUTPUT_RATE = 24000  # Gemini outputs audio at 24 kHz
        self.CHUNK = 512

        # An asyncio.Queue to buffer server audio data
        self.audio_queue = asyncio.Queue()

        self.is_playing = False  # Add this flag

    async def start(self):
        """Create a WebSocket connection and run the capture, streaming, and playback tasks concurrently."""
        # Open the WebSocket
        self.ws = await connect(self.uri, extra_headers={"Content-Type": "application/json"})
        
        # 1) Send the BidiGenerateContentSetup message 
        #    specifying the model and any generation configs (we want audio output).
        setup_message = {
            "setup": {
                "model": f"models/{self.model}",
                "generation_config": {
                    "response_modalities": ["AUDIO"],
                    "speech_config": {
                        "voice_config": {
                            "prebuilt_voice_config": {
                                # Pick a voice: "Puck", "Charon", "Kore", "Fenrir", or "Aoede"
                                "voice_name": "Puck"
                            }
                        }
                    }
                },
                "system_instruction": {
                    "parts": [
                        {
                            "text": "You are a friendly Gemini 2.0 model. Respond verbally in a casual, helpful tone."
                        }
                    ]
                }
            }
        }
        await self.ws.send(json.dumps(setup_message))

        # The first server response is BidiGenerateContentSetupComplete. We can read and ignore it or log it.
        first_msg = await self.ws.recv()
        print("Setup complete message from Gemini:", first_msg)

        print("Connected to Gemini. Speak into your microphone; press Ctrl+C to exit.")
        
        # 2) Run capture, read server messages, and playback concurrently
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.capture_audio())
            tg.create_task(self.receive_server_messages())
            tg.create_task(self.play_responses())


    async def capture_audio(self):
        """Capture audio from your Mac’s microphone and send to Gemini in realtime."""
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.INPUT_RATE,
            input=True,
            frames_per_buffer=self.CHUNK
        )

        try:
            while True:
                data = await asyncio.to_thread(stream.read, self.CHUNK)
                
                # Only process input when we're not playing Gemini's response
                if not self.is_playing:
                    if not self.vad.is_speech(data):
                        if not hasattr(self, '_printed_no_speech'):
                            print("No speech detected")
                            self._printed_no_speech = True
                        data = b'\x00' * len(data)
                    
                    self._printed_no_speech = False
                    encoded_data = base64.b64encode(data).decode("utf-8")
                    realtime_input_msg = {
                        "realtime_input": {
                            "media_chunks": [
                                {
                                    "data": encoded_data,
                                    "mime_type": "audio/pcm"
                                }
                            ]
                        }
                    }
                    await self.ws.send(json.dumps(realtime_input_msg))
                else:
                    if not hasattr(self, '_printed_skip_message'):
                        print("Skipping input while Gemini is speaking")
                        self._printed_skip_message = True
                    # Reset the flag when we're not playing anymore
                    elif not self.is_playing:
                        self._printed_skip_message = False

        except asyncio.CancelledError:
            pass
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()

    async def receive_server_messages(self):
        async for msg in self.ws:
            response = json.loads(msg)
            
            # If the server gave us audio data, store it for playback
            try:
                parts = response["serverContent"]["modelTurn"]["parts"]
                for p in parts:
                    if "inlineData" in p:
                        # This indicates audio data
                        audio_data_b64 = p["inlineData"]["data"]
                        audio_bytes = base64.b64decode(audio_data_b64)
                        self.audio_queue.put_nowait(audio_bytes)
                    elif "text" in p:
                        # If the model also responds with text, you can process it here
                        print("Gemini text response:", p["text"])
            except KeyError:
                pass

            # Check if the model ended its turn
            try:
                turn_complete = response["serverContent"]["turnComplete"]
                if turn_complete:
                    # If the user interrupts or the turn is done, any leftover audio is ignored or cleared.
                    while not self.audio_queue.empty():
                        self.audio_queue.get_nowait()
            except KeyError:
                pass

    async def play_responses(self):
        """Pull audio data from the queue and play it through speakers."""
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.OUTPUT_RATE,
            output=True
        )

        try:
            while True:
                audio_chunk = await self.audio_queue.get()
                self.is_playing = True  # Set flag before playing
                await asyncio.to_thread(stream.write, audio_chunk)
                self.is_playing = False  # Clear flag after playing
        except asyncio.CancelledError:
            pass
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()

if __name__ == "__main__":
    try:
        client = GeminiConnection()
        asyncio.run(client.start())
    except KeyboardInterrupt:
        print("Exiting on user interrupt...")
