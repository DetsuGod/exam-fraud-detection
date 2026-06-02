import { useEffect, useRef, useState, useCallback } from 'react';

export default function CameraPreview() {
  const videoRef = useRef(null);
  const [minimized, setMinimized] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [position, setPosition] = useState({ x: null, y: null });
  const [hasStream, setHasStream] = useState(false);
  const dragOffset = useRef({ x: 0, y: 0 });

  // Attach camera stream to video element
  const attachStream = useCallback(() => {
    if (window.__examCameraStream && videoRef.current) {
      const tracks = window.__examCameraStream.getVideoTracks();
      if (tracks.length > 0 && tracks[0].readyState === 'live') {
        videoRef.current.srcObject = window.__examCameraStream;
        setHasStream(true);
        console.log('✅ Camera preview attached');
        return true;
      }
    }
    return false;
  }, []);

  useEffect(() => {
    // Try to attach immediately
    if (!attachStream()) {
      // If stream not available yet, retry a few times
      let retries = 0;
      const interval = setInterval(() => {
        if (attachStream() || retries >= 10) {
          clearInterval(interval);
        }
        retries++;
      }, 500);

      return () => clearInterval(interval);
    }
  }, [attachStream]);

  // Listen for stream ending
  useEffect(() => {
    if (!window.__examCameraStream) return;

    const tracks = window.__examCameraStream.getVideoTracks();
    if (tracks.length === 0) return;

    const track = tracks[0];
    const handleEnded = () => {
      setHasStream(false);
      console.log('⚠️ Camera track ended');
    };

    track.addEventListener('ended', handleEnded);
    return () => track.removeEventListener('ended', handleEnded);
  }, [hasStream]);

  const handleMouseDown = (e) => {
    if (e.target.tagName === 'BUTTON') return;
    setIsDragging(true);
    const rect = e.currentTarget.getBoundingClientRect();
    dragOffset.current = {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    };
  };

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDragging) return;
      setPosition({
        x: e.clientX - dragOffset.current.x,
        y: e.clientY - dragOffset.current.y
      });
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  const style = position.x !== null
    ? {
        left: position.x + 'px',
        top: position.y + 'px',
        right: 'auto',
        bottom: 'auto',
        width: minimized ? '60px' : '200px',
        height: minimized ? '60px' : '150px',
      }
    : {
        width: minimized ? '60px' : '200px',
        height: minimized ? '60px' : '150px',
      };

  return (
    <div
      className={`camera-preview ${minimized ? 'minimized' : ''}`}
      style={style}
      onMouseDown={handleMouseDown}
    >
      {/* ALWAYS render video so ref is not null */}
      <video 
        ref={videoRef} 
        autoPlay 
        muted 
        playsInline 
        style={{ 
          display: hasStream ? 'block' : 'none',
          width: '100%',
          height: '100%',
          objectFit: 'cover'
        }} 
      />
      
      {!hasStream && (
        <div style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'rgba(10, 10, 15, 0.9)',
          color: '#5a5a72',
          fontSize: minimized ? '1.2rem' : '1.5rem',
          position: 'absolute',
          top: 0,
          left: 0
        }}>
          📷
        </div>
      )}
      
      {!minimized && (
        <div className="camera-controls">
          <button onClick={() => setMinimized(true)} title="Thu nhỏ">−</button>
        </div>
      )}

      {minimized && (
        <div 
          className="camera-controls" 
          style={{ top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}
        >
          <button onClick={() => setMinimized(false)} title="Phóng to">+</button>
        </div>
      )}

      {!minimized && hasStream && (
        <div className="recording-indicator">
          <div className="recording-dot"></div>
          <span>REC</span>
        </div>
      )}
    </div>
  );
}
