import React, { useState, useRef, useEffect } from 'react';
import { Camera, Mic, StopCircle, Play } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

const GeminiPlayground = () => {
  const [mode, setMode] = useState('idle'); // idle, camera, audio
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);
  const videoRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);

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
      setIsStreaming(false);
      setMode('idle');
    }
  };

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, []);

  return (
    <div className="w-full max-w-4xl mx-auto p-6">
      <div className="space-y-6">
        <h1 className="text-3xl font-bold">Gemini 2.0 Playground</h1>
        
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="flex gap-4">
          <button
            onClick={startCamera}
            disabled={isStreaming}
            className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
          >
            <Camera size={20} />
            Start Camera + Audio
          </button>

          <button
            onClick={startAudio}
            disabled={isStreaming}
            className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50"
          >
            <Mic size={20} />
            Start Audio Only
          </button>

          {isStreaming && (
            <button
              onClick={stopStream}
              className="flex items-center gap-2 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600"
            >
              <StopCircle size={20} />
              Stop Stream
            </button>
          )}
        </div>

        {mode === 'camera' && (
          <div className="relative aspect-video w-full max-w-2xl mx-auto bg-gray-100 rounded-lg overflow-hidden">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="w-full h-full object-cover"
            />
          </div>
        )}

        {mode === 'audio' && (
          <div className="flex items-center justify-center h-48 bg-gray-100 rounded-lg">
            <div className="flex flex-col items-center gap-2">
              <Mic size={48} className="text-gray-600" />
              <p className="text-gray-600">Audio streaming...</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default GeminiPlayground;
