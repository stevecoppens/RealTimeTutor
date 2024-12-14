import asyncio
import os
import json
import base64
from dotenv import load_dotenv
import numpy as np
import pyaudio
import torch
from websockets import connect
import tkinter as tk
from tkinter import ttk
import tkinter.scrolledtext as scrolledtext


from google.genai.types import (GoogleSearch,Tool, GenerateContentConfig)

google_search_tool = Tool(google_search=GoogleSearch())

# load env variables from .env file
load_dotenv()

class ConfigGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Gemini Configuration")
        self.root.geometry("600x500")

        # System Prompt
        tk.Label(self.root, text="System Prompt:").pack(pady=5)
        self.system_prompt = scrolledtext.ScrolledText(self.root, width=60, height=10)
        self.system_prompt.pack(pady=5)
        self.system_prompt.insert(tk.END, "You are a friendly Gemini 2.0 model. Respond verbally in a casual, helpful tone.")

        # Voice Selection
        tk.Label(self.root, text="Voice:").pack(pady=5)
        self.voice_var = tk.StringVar(value="Puck")
        voices = ["Puck", "Charon", "Kore", "Fenrir", "Aoede"]
        voice_dropdown = ttk.Combobox(self.root, textvariable=self.voice_var, values=voices, state="readonly")
        voice_dropdown.pack(pady=5)

        # Google Search Checkbox
        self.google_search_var = tk.BooleanVar(value=True)
        google_search_cb = tk.Checkbutton(self.root, text="Enable Google Search", variable=self.google_search_var)
        google_search_cb.pack(pady=5)

        # Start Button
        tk.Button(self.root, text="Start Gemini", command=self.start_gemini).pack(pady=20)

    def get_config(self):
        return {
            "system_prompt": self.system_prompt.get("1.0", tk.END).strip(),
            "voice": self.voice_var.get(),
            "google_search": self.google_search_var.get()
        }

    def start_gemini(self):
        config = self.get_config()
        self.root.destroy()
        client = GeminiConnection(config)
        asyncio.run(client.start())

    def run(self):
        self.root.mainloop()

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
    def __init__(self, config=None):
        # Your Gemini API key. Must be set as an environment variable or replace here with a string.
        self.api_key = os.environ.get("GEMINI_API_KEY")
        # The Gemini 2.0 (flash) model name
        self.model = "gemini-2.0-flash-exp"
        self.config = config or {
            "system_prompt": "You are a friendly Gemini 2.0 model. Respond verbally in a casual, helpful tone.",
            "voice": "Puck",
            "google_search": True
        }
        
        # WebSocket endpoint for Gemini's BidiGenerateContent API
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

        self.is_playing = False

    async def start(self):
        """Create a WebSocket connection and run the capture, streaming, and playback tasks concurrently."""
        # Open the WebSocket
        self.ws = await connect(self.uri, additional_headers={"Content-Type": "application/json"})
        
        generation_config = {} if not self.config["google_search"] else GenerateContentConfig(tools=[google_search_tool])

        generation_config = {
            "response_modalities": ["AUDIO"],
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": self.config["voice"]
                    }
                }
            }
        }
        
        setup_message = {
            "setup": {
                "model": f"models/{self.model}",
                "generation_config": generation_config,
                "system_instruction": {
                    "parts": [
                        {
                            "text": self.config["system_prompt"]
                        }
                    ]
                }
            }
        }
        
        await self.ws.send(json.dumps(setup_message))

        first_msg = await self.ws.recv()
        print("Setup complete message from Gemini:", first_msg)
        print("Connected to Gemini. Speak into your microphone; press Ctrl+C to exit.")
        
        # 2) Run capture, read server messages, and playback concurrently
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.capture_audio())
            tg.create_task(self.receive_server_messages())
            tg.create_task(self.play_responses())


    async def capture_audio(self):
        """Capture audio from your Mac's microphone and send to Gemini in realtime."""
        audio = pyaudio.PyAudio()
        stream = None
        try:
            stream = audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.INPUT_RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )

            while True:
                try:
                    data = await asyncio.to_thread(stream.read, self.CHUNK, exception_on_overflow=False)
                    
                    # Only process input when we're not playing Gemini's response
                    if not self.is_playing:
                        if not self.vad.is_speech(data):
                            if not hasattr(self, '_printed_no_speech'):
                                print("No speech detected")
                                self._printed_no_speech = True
                            data = b'\x00' * len(data)
                        else:
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

                except OSError as e:
                    print(f"Audio capture error: {e}")
                    await asyncio.sleep(0.1)  # Add small delay before retrying
                    continue

        except asyncio.CancelledError:
            print("Audio capture cancelled")
        except Exception as e:
            print(f"Unexpected error in capture_audio: {e}")
        finally:
            if stream is not None and stream.is_active():
                try:
                    stream.stop_stream()
                    stream.close()
                except OSError:
                    pass  # Ignore errors during cleanup
            try:
                audio.terminate()
            except:
                pass  # Ignore errors during cleanup

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
        gui = ConfigGUI()
        gui.run()
    except KeyboardInterrupt:
        print("Exiting on user interrupt...")
