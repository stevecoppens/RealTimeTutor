'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Mic, StopCircle } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';

interface Config {
  systemPrompt: string;
  voice: string;
  googleSearch: boolean;
  allowInterruptions: boolean;
}

export default function GeminiVoiceChat() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);
  const [text, setText] = useState('');
  const [config, setConfig] = useState<Config>({
    systemPrompt: "You are a friendly Gemini 2.0 model. Respond verbally in a casual, helpful tone.",
    voice: "Puck",
    googleSearch: true,
    allowInterruptions: false
  });
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const audioInputRef = useRef(null);
  const audioOutputRef = useRef(null);
  const clientId = useRef(crypto.randomUUID());
  let audioBuffer = []
  let isPlaying = false

  const voices = ["Puck", "Charon", "Kore", "Fenrir", "Aoede"];

  const startStream = async () => {
    // Initialize WebSocket first
    wsRef.current = new WebSocket(`ws://localhost:8000/ws/${clientId.current}`);
    
    wsRef.current.onopen = async () => {
      // Send configuration as first message
      wsRef.current.send(JSON.stringify({
        type: 'config',
        config: config
      }));
      
      // Start audio stream after config is sent
      await startAudioStream();
      setIsStreaming(true);
    };

    wsRef.current.onmessage = async (event) => {
      const response = JSON.parse(event.data);
      if (response.type === 'audio') {
        const audioData = base64ToFloat32Array(response.data);
        playAudioData(audioData);
      } else if (response.type === 'text') {
        setText(prev => prev + response.text + '\n');
      }
    };

    wsRef.current.onerror = (error) => {
      setError('WebSocket error: ' + error.message);
      setIsStreaming(false);
    };

    wsRef.current.onclose = () => {
      setIsStreaming(false);
    };
  };

  // Initialize audio context and stream
  const startAudioStream = async () => {
    try {
      // Initialize audio context
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: 16000 // Required by Gemini
      });

      // Get microphone stream
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Create audio input node
      const source = audioContextRef.current.createMediaStreamSource(stream);
      const processor = audioContextRef.current.createScriptProcessor(512, 1, 1);
      
      processor.onaudioprocess = (e) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            const inputData = e.inputBuffer.getChannelData(0);
            const pcmData = float32ToPcm16(inputData);
            // Convert to base64 and send as binary
            const base64Data = btoa(String.fromCharCode(...new Uint8Array(pcmData.buffer)));
            wsRef.current.send(new Blob([base64Data], { type: 'application/octet-stream' }));
        }
      };

      source.connect(processor);
      processor.connect(audioContextRef.current.destination);
      
      audioInputRef.current = { source, processor, stream };
      setIsStreaming(true);
    } catch (err) {
      setError('Failed to access microphone: ' + err.message);
    }
  };

  // Stop streaming
  const stopStream = () => {
    if (audioInputRef.current) {
      const { source, processor, stream } = audioInputRef.current;
      source.disconnect();
      processor.disconnect();
      stream.getTracks().forEach(track => track.stop());
      audioInputRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsStreaming(false);
  };

  // Utility function to convert base64 to Float32Array
  const base64ToFloat32Array = (base64) => {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    // Convert to 16-bit PCM
    const pcm16 = new Int16Array(bytes.buffer);
    // Convert to float32
    const float32 = new Float32Array(pcm16.length);
    for (let i = 0; i < pcm16.length; i++) {
      float32[i] = pcm16[i] / 32768.0;
    }
    return float32;
  };

  // Utility function to convert Float32Array to PCM16
  const float32ToPcm16 = (float32Array) => {
    const pcm16 = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
      const s = Math.max(-1, Math.min(1, float32Array[i]));
      pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return pcm16;
  };

  // Play received audio data
  const playAudioData = async (audioData) => {
    audioBuffer.push(audioData)
    if (!isPlaying) {
      playNextInQueue(); // Start playback if not already playing
      }
    }

  const playNextInQueue = async () => {
    if (!audioContextRef.current || audioBuffer.length == 0) {
      isPlaying = false;
      return;
    }

    isPlaying = true
    const audioData = audioBuffer.shift()

    const buffer = audioContextRef.current.createBuffer(1, audioData.length, 24000);
    buffer.copyToChannel(audioData, 0);

    const source = audioContextRef.current.createBufferSource();
    source.buffer = buffer;
    source.connect(audioContextRef.current.destination);
    source.onended = () => {
      playNextInQueue()
    }
    source.start();
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopStream();
    };
  }, []);

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="space-y-6">
        <h1 className="text-4xl font-bold tracking-tight">Gemini 2.0 Realtime Playground ✨</h1>
        
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <Card>
          <CardContent className="pt-6 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="system-prompt">System Prompt</Label>
              <Textarea
                id="system-prompt"
                value={config.systemPrompt}
                onChange={(e) => setConfig(prev => ({ ...prev, systemPrompt: e.target.value }))}
                disabled={isConnected}
                className="min-h-[100px]"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="voice-select">Voice</Label>
              <Select
                value={config.voice}
                onValueChange={(value) => setConfig(prev => ({ ...prev, voice: value }))}
                disabled={isConnected}
              >
                <SelectTrigger id="voice-select">
                  <SelectValue placeholder="Select a voice" />
                </SelectTrigger>
                <SelectContent>
                  {voices.map((voice) => (
                    <SelectItem key={voice} value={voice}>
                      {voice}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center space-x-2">
              <Checkbox
                id="google-search"
                checked={config.googleSearch}
                onCheckedChange={(checked) => 
                  setConfig(prev => ({ ...prev, googleSearch: checked as boolean }))}
                disabled={isConnected}
              />
              <Label htmlFor="google-search">Enable Google Search</Label>
            </div>

            <div className="flex items-center space-x-2">
              <Checkbox
                id="allow-interruptions"
                checked={config.allowInterruptions}
                onCheckedChange={(checked) => 
                  setConfig(prev => ({ ...prev, allowInterruptions: checked as boolean }))}
                disabled={isConnected}
              />
              <Label htmlFor="allow-interruptions">Allow Interruptions</Label>
            </div>
          </CardContent>
        </Card>

        <div className="flex gap-4">
          <Button
            onClick={startStream}
            disabled={isStreaming}
            className="gap-2"
          >
            <Mic className="h-4 w-4" />
            Start Voice Chat
          </Button>

          {isStreaming && (
            <Button
              onClick={stopStream}
              variant="destructive"
              className="gap-2"
            >
              <StopCircle className="h-4 w-4" />
              Stop Chat
            </Button>
          )}
        </div>

        {isStreaming && (
          <Card>
            <CardContent className="flex items-center justify-center h-24 mt-6">
              <div className="flex flex-col items-center gap-2">
                <Mic className="h-8 w-8 text-blue-500 animate-pulse" />
                <p className="text-gray-600">Listening...</p>
              </div>
            </CardContent>
          </Card>
        )}

        {text && (
          <Card>
            <CardContent className="pt-6">
              <h2 className="text-lg font-semibold mb-2">Conversation:</h2>
              <pre className="whitespace-pre-wrap text-gray-700">{text}</pre>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}