import { useRef, useState, useCallback } from "react";

type ASRState = "idle" | "connecting" | "recording" | "error";

interface UseASROptions {
  onResult?: (text: string, isFinal: boolean) => void;
  onDone?: () => void;
  onError?: (msg: string) => void;
}

/**
 * 语音识别 Hook：麦克风录音 → 后端 WebSocket 代理 → DashScope ASR → 实时文本
 */
export function useASR({ onResult, onDone, onError }: UseASROptions = {}) {
  const [state, setState] = useState<ASRState>("idle");
  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const SILENCE_TIMEOUT = 4000; // 4秒无声自动停止
  const SILENCE_THRESHOLD = 0.01; // 音量阈值

  const stop = useCallback(() => {
    // Clear silence timer
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }

    // Stop audio processing
    processorRef.current?.disconnect();
    processorRef.current = null;
    ctxRef.current?.close();
    ctxRef.current = null;

    // Stop mic
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;

    // Tell server to stop, then close
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: "stop" }));
      setTimeout(() => {
        wsRef.current?.close();
        wsRef.current = null;
      }, 500);
    }

    setState("idle");
  }, []);

  const start = useCallback(() => {
    if (state !== "idle") return;
    setState("connecting");

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = import.meta.env.VITE_API_URL
      ? new URL(import.meta.env.VITE_API_URL).host
      : window.location.host;
    const ws = new WebSocket(`${protocol}//${host}/api/asr`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "ready") {
        // ASR ready, start recording
        startRecording(ws);
      } else if (msg.type === "result") {
        onResult?.(msg.text, msg.is_end);
      } else if (msg.type === "done") {
        onDone?.();
        stop();
      } else if (msg.type === "error") {
        onError?.(msg.message || "识别失败");
        stop();
        setState("error");
        setTimeout(() => setState("idle"), 2000);
      }
    };

    ws.onerror = () => {
      onError?.("连接失败");
      stop();
      setState("error");
      setTimeout(() => setState("idle"), 2000);
    };

    ws.onclose = () => {
      stop();
    };
  }, [state, onResult, onDone, onError, stop]);

  async function startRecording(ws: WebSocket) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;

      const audioCtx = new AudioContext({ sampleRate: 16000 });
      ctxRef.current = audioCtx;
      const source = audioCtx.createMediaStreamSource(stream);

      // ScriptProcessor: 4096 samples buffer, mono in, mono out
      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN) return;
        const float32 = e.inputBuffer.getChannelData(0);

        // Silence detection: check RMS volume
        let sum = 0;
        for (let i = 0; i < float32.length; i++) sum += float32[i] * float32[i];
        const rms = Math.sqrt(sum / float32.length);

        if (rms > SILENCE_THRESHOLD) {
          // Voice detected, reset silence timer
          if (silenceTimerRef.current) {
            clearTimeout(silenceTimerRef.current);
            silenceTimerRef.current = null;
          }
        } else if (!silenceTimerRef.current) {
          // Start silence timer
          silenceTimerRef.current = setTimeout(() => {
            stop();
          }, SILENCE_TIMEOUT);
        }

        // Convert Float32 → Int16 PCM
        const pcm = new Int16Array(float32.length);
        for (let i = 0; i < float32.length; i++) {
          const s = Math.max(-1, Math.min(1, float32[i]));
          pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        ws.send(pcm.buffer);
      };

      source.connect(processor);
      processor.connect(audioCtx.destination);

      setState("recording");
    } catch (err) {
      onError?.("无法获取麦克风权限");
      stop();
      setState("error");
      setTimeout(() => setState("idle"), 2000);
    }
  }

  return { state, start, stop };
}
