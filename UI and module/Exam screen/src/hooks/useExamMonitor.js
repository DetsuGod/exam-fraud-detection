import { useEffect, useRef, useState, useCallback } from 'react';

const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_URL = `${protocol}//${window.location.host}/ws/exam?role=student`;
const RECONNECT_DELAY = 3000;

/**
 * Custom hook for real-time exam monitoring.
 * Connects to the WebSocket server and sends violation events
 * (BLUR, VISIBILITY_CHANGE, COPY, SCREEN_SHARE) with screenshots.
 * 
 * @param {Object} options
 * @param {boolean} options.enabled - Whether monitoring is active
 * @param {string} options.studentId - Student identifier
 * @returns {{ wsConnected: boolean, violationCount: number, lastViolation: object|null }}
 */
export default function useExamMonitor({ enabled = false, studentId = '' } = {}) {
  const [wsConnected, setWsConnected] = useState(false);
  const [violationCount, setViolationCount] = useState(0);
  const [lastViolation, setLastViolation] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const copyIntervalRef = useRef(null);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const webcamVideoRef = useRef(null);
  const webcamCanvasRef = useRef(null);

  // ── Capture screenshot from screen share ──
  const captureFrame = useCallback(() => {
    const stream = window.__examScreenStream;
    if (!stream) return '';

    // Lazy-create hidden video + canvas elements
    if (!videoRef.current) {
      videoRef.current = document.createElement('video');
      videoRef.current.autoplay = true;
      videoRef.current.muted = true;
      videoRef.current.playsInline = true;
      videoRef.current.style.position = 'absolute';
      videoRef.current.style.left = '-9999px';
      videoRef.current.style.top = '-9999px';
      videoRef.current.style.width = '1px';
      videoRef.current.style.height = '1px';
      document.body.appendChild(videoRef.current);
    }
    if (!canvasRef.current) {
      canvasRef.current = document.createElement('canvas');
      canvasRef.current.style.display = 'none';
      document.body.appendChild(canvasRef.current);
    }

    const video = videoRef.current;
    const canvas = canvasRef.current;

    // Attach stream if not attached
    if (video.srcObject !== stream) {
      video.srcObject = stream;
      video.play().catch(e => console.warn('Video play failed:', e));
    }

    if (!video.videoWidth) return '';

    const scale = 960 / video.videoWidth;
    canvas.width = 960;
    canvas.height = video.videoHeight * scale;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.3);
  }, []);

  // ── Capture screenshot from webcam stream ──
  const captureWebcamFrame = useCallback(() => {
    const stream = window.__examCameraStream;
    if (!stream) return '';

    if (!webcamVideoRef.current) {
      webcamVideoRef.current = document.createElement('video');
      webcamVideoRef.current.autoplay = true;
      webcamVideoRef.current.muted = true;
      webcamVideoRef.current.playsInline = true;
      webcamVideoRef.current.style.position = 'absolute';
      webcamVideoRef.current.style.left = '-9999px';
      webcamVideoRef.current.style.top = '-9999px';
      webcamVideoRef.current.style.width = '1px';
      webcamVideoRef.current.style.height = '1px';
      document.body.appendChild(webcamVideoRef.current);
    }
    if (!webcamCanvasRef.current) {
      webcamCanvasRef.current = document.createElement('canvas');
      webcamCanvasRef.current.style.display = 'none';
      document.body.appendChild(webcamCanvasRef.current);
    }

    const video = webcamVideoRef.current;
    const canvas = webcamCanvasRef.current;

    if (video.srcObject !== stream) {
      video.srcObject = stream;
      video.play().catch(e => console.warn('Webcam video play failed:', e));
    }

    if (!video.videoWidth) return '';

    canvas.width = 320;
    canvas.height = 240;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.35);
  }, []);

  // ── Send event through WebSocket ──
  const sendEvent = useCallback((data) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ ...data, student_id: studentId }));
    }
  }, [studentId]);

  // ── Record a violation locally ──
  const recordViolation = useCallback((type) => {
    setViolationCount(prev => prev + 1);
    setLastViolation({ type, time: new Date().toISOString() });
  }, []);

  // ── WebSocket connection ──
  useEffect(() => {
    if (!enabled) return;

    function connect() {
      const ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        setWsConnected(true);
        console.log('[Monitor] WebSocket connected');

        // If screen share is already active, notify server
        if (window.__examScreenStream) {
          const tracks = window.__examScreenStream.getVideoTracks();
          if (tracks.length > 0 && tracks[0].readyState === 'live') {
            ws.send(JSON.stringify({ event_type: 'SCREEN_SHARE_STARTED', student_id: studentId }));
          }
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        console.log('[Monitor] WebSocket disconnected, reconnecting...');
        reconnectTimerRef.current = setTimeout(connect, RECONNECT_DELAY);
      };

      ws.onerror = () => {
        console.log('[Monitor] WebSocket error');
      };

      wsRef.current = ws;
    }

    connect();

    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnect on intentional close
        wsRef.current.close();
      }
    };
  }, [enabled, studentId]);

  // ── Stream webcam and screen frames dynamically to the server ──
  useEffect(() => {
    if (!wsConnected || !enabled || !studentId) return;

    // Use Web Worker to prevent browser from throttling timers when the tab is in the background (resolving lag/stutter)
    let worker = null;
    let fallbackInterval = null;

    try {
      const workerCode = `
        let timer = null;
        self.onmessage = function(e) {
          if (e.data.action === 'start') {
            if (timer) clearInterval(timer);
            timer = setInterval(() => {
              self.postMessage('tick');
            }, e.data.interval);
          } else if (e.data.action === 'stop') {
            if (timer) clearInterval(timer);
            timer = null;
          }
        };
      `;
      const blob = new Blob([workerCode], { type: 'application/javascript' });
      const workerUrl = URL.createObjectURL(blob);
      worker = new Worker(workerUrl);

      worker.onmessage = () => {
        const webcamFrame = captureWebcamFrame();
        const screenFrame = captureFrame();

        if (webcamFrame || screenFrame) {
          sendEvent({
            event_type: 'stream_frame',
            image: webcamFrame,
            screen_image: screenFrame
          });
        }
      };

      worker.postMessage({ action: 'start', interval: 120 });
      console.log('[Monitor] Background Web Worker timer started successfully');
    } catch (e) {
      console.warn('[Monitor] Web Worker blocked or not supported, falling back to setInterval:', e);
      fallbackInterval = setInterval(() => {
        const webcamFrame = captureWebcamFrame();
        const screenFrame = captureFrame();

        if (webcamFrame || screenFrame) {
          sendEvent({
            event_type: 'stream_frame',
            image: webcamFrame,
            screen_image: screenFrame
          });
        }
      }, 120);
    }

    return () => {
      if (worker) {
        worker.postMessage({ action: 'stop' });
        worker.terminate();
      }
      if (fallbackInterval) {
        clearInterval(fallbackInterval);
      }
    };
  }, [wsConnected, enabled, studentId, captureWebcamFrame, captureFrame, sendEvent]);

  // ── Blur event listener ──
  useEffect(() => {
    if (!enabled) return;

    const handleBlur = () => {
      if (!window.__examScreenStream) return;
      // Introduce a 350ms delay so screen sharing stream track can register/switch to the newly focused tab/window
      setTimeout(() => {
        const image = captureFrame();
        sendEvent({ event_type: 'BLUR', image });
        recordViolation('BLUR');
      }, 350);
    };

    window.addEventListener('blur', handleBlur);
    return () => window.removeEventListener('blur', handleBlur);
  }, [enabled, captureFrame, sendEvent, recordViolation]);

  // ── Visibility change listener ──
  useEffect(() => {
    if (!enabled) return;

    const handleVisibilityChange = () => {
      if (!window.__examScreenStream) return;
      if (document.hidden) {
        // Introduce a 350ms delay so screen sharing stream track can register/switch to the newly focused tab/window
        setTimeout(() => {
          const image = captureFrame();
          sendEvent({ event_type: 'VISIBILITY_CHANGE', image });
          recordViolation('VISIBILITY_CHANGE');
        }, 350);
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [enabled, captureFrame, sendEvent, recordViolation]);

  // ── Copy event listener ──
  useEffect(() => {
    if (!enabled) return;

    const handleCopy = () => {
      if (!window.__examScreenStream) return;
      const copiedText = window.getSelection().toString();

      // 1. Send COPY_DETECTED immediately
      sendEvent({ event_type: 'COPY_DETECTED', copied_text: copiedText });
      recordViolation('COPY');

      // 2. Clear any previous copy frame interval
      if (copyIntervalRef.current) clearInterval(copyIntervalRef.current);

      // 3. Send 5 COPY_FRAMEs every 2 seconds
      let count = 0;
      copyIntervalRef.current = setInterval(() => {
        const image = captureFrame();
        sendEvent({ event_type: 'COPY_FRAME', image });
        count++;
        if (count >= 5) {
          clearInterval(copyIntervalRef.current);
          copyIntervalRef.current = null;
        }
      }, 2000);
    };

    document.addEventListener('copy', handleCopy);
    return () => {
      document.removeEventListener('copy', handleCopy);
      if (copyIntervalRef.current) clearInterval(copyIntervalRef.current);
    };
  }, [enabled, captureFrame, sendEvent, recordViolation]);

  // ── Screen share status monitoring ──
  useEffect(() => {
    if (!enabled) return;

    let lastShareState = false;

    const checkShareStatus = () => {
      const stream = window.__examScreenStream;
      const isSharing = stream && stream.getVideoTracks().length > 0 &&
        stream.getVideoTracks()[0].readyState === 'live';

      if (isSharing && !lastShareState) {
        sendEvent({ event_type: 'SCREEN_SHARE_STARTED' });
        lastShareState = true;
      } else if (!isSharing && lastShareState) {
        sendEvent({ event_type: 'SCREEN_SHARE_STOPPED' });
        lastShareState = false;
      }
    };

    const interval = setInterval(checkShareStatus, 2000);
    return () => clearInterval(interval);
  }, [enabled, sendEvent]);

  // ── Cleanup hidden elements on unmount ──
  useEffect(() => {
    return () => {
      if (videoRef.current && videoRef.current.parentNode) {
        videoRef.current.srcObject = null;
        videoRef.current.parentNode.removeChild(videoRef.current);
      }
      if (canvasRef.current && canvasRef.current.parentNode) {
        canvasRef.current.parentNode.removeChild(canvasRef.current);
      }
      if (webcamVideoRef.current && webcamVideoRef.current.parentNode) {
        webcamVideoRef.current.srcObject = null;
        webcamVideoRef.current.parentNode.removeChild(webcamVideoRef.current);
      }
      if (webcamCanvasRef.current && webcamCanvasRef.current.parentNode) {
        webcamCanvasRef.current.parentNode.removeChild(webcamCanvasRef.current);
      }
    };
  }, []);

  return { wsConnected, violationCount, lastViolation };
}
