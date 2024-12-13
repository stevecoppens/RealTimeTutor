'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Camera, Mic, StopCircle, Play } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

export default function GeminiPlayground() {
  const [mode, setMode] = useState('idle'); // idle, camera, audio
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);
  const [response, setResponse] = useState('');
  const [isPlaying, setIsPlaying] = useState(false);
  const audioContextRef = useRef(null);
  const audioQueueRef = useRef([]);
  const videoRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const wsRef = useRef(null);
  
  // Initialize audio context
  useEffect(() => {
    audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
    return () => {
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    // Setup WebSocket connection
    wsRef.current = new WebSocket('ws://localhost:8000/ws');
    
    wsRef.current.onmessage = async (event) => {
      const response = JSON.parse(event.data);
      
      if (response.type === 'text') {
        setResponse(response.data);
      } else if (response.type === 'audio') {
        // Convert base64 audio to ArrayBuffer
        const audioData = base64ToArrayBuffer(response.data);
        
        // Add to audio queue
        audioQueueRef.current.push(audioData);
        
        // Start playing if not already playing
        if (!isPlaying) {
          setIsPlaying(true);
          playNextAudio();
        }
      }
    };

    wsRef.current.onerror = (error) => {
      setError('WebSocket error: ' + error.message);
    };

    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  // Function to capture and send video frames
  useEffect(() => {
    if (mode === 'camera' && videoRef.current && wsRef.current) {
      const canvas = document.createElement('canvas');
      const context = canvas.getContext('2d');
      
      const sendFrame = () => {
        if (videoRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          canvas.width = videoRef.current.videoWidth;
          canvas.height = videoRef.current.videoHeight;
          context.drawImage(videoRef.current, 0, 0);
          
          const frame = canvas.toDataURL('image/jpeg');
          wsRef.current.send(JSON.stringify({
            type: 'video',
            data: frame
          }));
        }
      };

      const interval = setInterval(sendFrame, 1000); // Send frame every second

      return () => clearInterval(interval);
    }
  }, [mode]);

  // Function to handle audio recording and sending
  // Audio helper functions
  const base64ToArrayBuffer = (base64) => {
    const binaryString = window.atob(base64);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
  };

  const playNextAudio = async () => {
    if (audioQueueRef.current.length === 0) {
      setIsPlaying(false);
      return;
    }

    const audioData = audioQueueRef.current.shift();
    
    try {
      // Decode the audio data
      const audioBuffer = await audioContextRef.current.decodeAudioData(audioData);
      
      // Create audio source
      const source = audioContextRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContextRef.current.destination);
      
      // Play the audio
      source.onended = playNextAudio;
      source.start(0);
    } catch (error) {
      console.error('Error playing audio:', error);
      playNextAudio(); // Skip to next audio if there's an error
    }
  };

  const startRecording = async () => {
    if (streamRef.current && wsRef.current) {
      const mediaRecorder = new MediaRecorder(streamRef.current);
      mediaRecorderRef.current = mediaRecorder;
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0 && wsRef.current.readyState === WebSocket.OPEN) {
          const reader = new FileReader();
          reader.onload = () => {
            wsRef.current.send(JSON.stringify({
              type: 'audio',
              data: reader.result
            }));
          };
          reader.readAsDataURL(event.data);
        }
      };

      mediaRecorder.start(1000); // Capture audio every second
    }
  };

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        video: true,
        audio: true 
      });
      
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        streamRef.current = stream;
        setMode('camera');
        setIsStreaming(true);
        startRecording();
      }
    } catch (err) {
      setError('Failed to access camera: ' + err.message);
    }
  };

  const startAudio = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: true 
      });
      streamRef.current = stream;
      setMode('audio');
      setIsStreaming(true);
      startRecording();
    } catch (err) {
      setError('Failed to access microphone: ' + err.message);
    }
  };

  const stopStream = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }
      if (mediaRecorderRef.current) {
        mediaRecorderRef.current.stop();
      }
      setIsStreaming(false);
      setMode('idle');
    }
  };

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="space-y-6">
        <h1 className="text-4xl font-bold tracking-tight">Gemini 2.0 Playground</h1>
        
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="flex gap-4">
          <Button
            onClick={startCamera}
            disabled={isStreaming}
            className="gap-2"
          >
            <Camera className="h-4 w-4" />
            Start Camera + Audio
          </Button>

          <Button
            onClick={startAudio}
            disabled={isStreaming}
            variant="secondary"
            className="gap-2"
          >
            <Mic className="h-4 w-4" />
            Start Audio Only
          </Button>

          {isStreaming && (
            <Button
              onClick={stopStream}
              variant="destructive"
              className="gap-2"
            >
              <StopCircle className="h-4 w-4" />
              Stop Stream
            </Button>
          )}
        </div>

        {mode === 'camera' && (
          <Card className="relative aspect-video w-full max-w-2xl mx-auto overflow-hidden">
            <CardContent className="p-0">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="w-full h-full object-cover"
              />
            </CardContent>
          </Card>
        )}

        {mode === 'audio' && (
          <Card>
            <CardContent className="flex items-center justify-center h-48">
              <div className="flex flex-col items-center gap-2">
                <Mic className="h-12 w-12 text-gray-600" />
                <p className="text-gray-600">Audio streaming...</p>
              </div>
            </CardContent>
          </Card>
        )}

        {response && (
          <Card>
            <CardContent className="pt-6">
              <h2 className="text-lg font-semibold mb-2">Gemini's Response:</h2>
              <p className="text-gray-700">{response}</p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}