import { useState, useEffect } from 'react';

export default function PermissionModal({ onPermissionsGranted }) {
  const [cameraGranted, setCameraGranted] = useState(false);
  const [screenGranted, setScreenGranted] = useState(false);
  const [cameraLoading, setCameraLoading] = useState(false);
  const [screenLoading, setScreenLoading] = useState(false);
  const [error, setError] = useState('');
  const [apiSupported, setApiSupported] = useState(true);
  const [videoDevices, setVideoDevices] = useState([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState('');

  // Check API support on mount
  useEffect(() => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setApiSupported(false);
      setError(
        'Trình duyệt của bạn không hỗ trợ truy cập camera/màn hình. ' +
        'Vui lòng sử dụng Chrome, Edge hoặc Firefox phiên bản mới nhất, ' +
        'và truy cập trang qua HTTPS hoặc localhost.'
      );
    }
  }, []);

  const switchCamera = async (deviceId) => {
    setSelectedDeviceId(deviceId);
    setError('');
    
    // Stop current stream tracks
    if (window.__examCameraStream) {
      window.__examCameraStream.getTracks().forEach(track => track.stop());
      window.__examCameraStream = null;
    }
    
    try {
      const constraints = {
        video: { deviceId: { exact: deviceId }, width: { ideal: 320 }, height: { ideal: 240 } },
        audio: false
      };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      window.__examCameraStream = stream;
      console.log('✅ Chuyển đổi camera thành công, tracks:', stream.getVideoTracks().length);
    } catch (err) {
      console.error('❌ Lỗi khi chuyển đổi camera:', err);
      let errorMsg = 'Không thể chuyển sang camera đã chọn. Vui lòng kiểm tra lại thiết bị.';
      if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        errorMsg = 'Camera đã chọn đang được sử dụng bởi ứng dụng khác (ví dụ: tab Dashboard). Vui lòng chọn camera khác hoặc đóng tab kia.';
      }
      setError(errorMsg);
      
      // Attempt to restore default/laptop camera as fallback
      try {
        const fallbackStream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'user', width: { ideal: 320 }, height: { ideal: 240 } },
          audio: false
        });
        window.__examCameraStream = fallbackStream;
        const activeTrack = fallbackStream.getVideoTracks()[0];
        const activeDeviceId = activeTrack ? activeTrack.getSettings().deviceId : '';
        setSelectedDeviceId(activeDeviceId);
      } catch (fallbackErr) {
        console.error('Failed to restore default camera:', fallbackErr);
      }
    }
  };

  const requestCamera = async () => {
    setCameraLoading(true);
    setError('');
    try {
      // Check if getUserMedia is available
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('getUserMedia is not supported');
      }

      // Initial stream request
      const stream = await navigator.mediaDevices.getUserMedia({ 
        video: { 
          width: { ideal: 320 },
          height: { ideal: 240 },
          facingMode: 'user'
        }, 
        audio: false 
      });
      
      // Store stream globally so CameraPreview can use it
      window.__examCameraStream = stream;
      setCameraGranted(true);
      console.log('✅ Camera access granted, tracks:', stream.getVideoTracks().length);

      // Now load the list of camera devices
      const devices = await navigator.mediaDevices.enumerateDevices();
      const videoDevs = devices.filter(device => device.kind === 'videoinput');
      setVideoDevices(videoDevs);
      
      if (videoDevs.length > 0) {
        // Smart default selection logic: Laptop built-in > Iriun > Other External
        let bestIndex = 0;
        let iriunIdx = -1;
        let externalIdx = -1;
        let laptopIdx = -1;
        
        videoDevs.forEach((device, index) => {
          const name = device.label.toLowerCase();
          if (name.includes("iriun")) {
            iriunIdx = index;
          } else if (name.includes("obs") || name.includes("virtual") || name.includes("manycam") || name.includes("droidcam")) {
            if (externalIdx === -1) {
              externalIdx = index;
            }
          }
          if (name.includes("integrated") || name.includes("front") || name.includes("built-in") || name.includes("laptop") || name.includes("hp truevision") || name.includes("hd camera") || name.includes("webcam") || name.includes("facetime") || name.includes("usb video")) {
            if (laptopIdx === -1) {
              laptopIdx = index;
            }
          }
        });
        
        if (laptopIdx !== -1) {
          bestIndex = laptopIdx;
        } else if (iriunIdx !== -1) {
          bestIndex = iriunIdx;
        } else if (externalIdx !== -1) {
          bestIndex = externalIdx;
        }
        
        const bestDeviceId = videoDevs[bestIndex].deviceId;
        setSelectedDeviceId(bestDeviceId);

        // Get the active track deviceId to see if we need to switch
        const activeTrack = stream.getVideoTracks()[0];
        const activeSettings = activeTrack ? activeTrack.getSettings() : {};
        
        // If the active camera is not the best camera, switch automatically!
        if (bestDeviceId && activeSettings.deviceId !== bestDeviceId) {
          console.log('🔄 Auto-switching to preferred camera:', videoDevs[bestIndex].label);
          try {
            // Stop initial track
            stream.getTracks().forEach(t => t.stop());
            
            const newStream = await navigator.mediaDevices.getUserMedia({
              video: { deviceId: { exact: bestDeviceId }, width: { ideal: 320 }, height: { ideal: 240 } },
              audio: false
            });
            window.__examCameraStream = newStream;
          } catch (switchErr) {
            console.warn('⚠️ Preferred camera is locked/in-use. Gracefully falling back to integrated/default webcam.', switchErr);
            // Re-acquire default/laptop camera
            const fallbackStream = await navigator.mediaDevices.getUserMedia({
              video: { facingMode: 'user', width: { ideal: 320 }, height: { ideal: 240 } },
              audio: false
            });
            window.__examCameraStream = fallbackStream;
            
            // Set selection back to the fallback camera
            const fallbackTrack = fallbackStream.getVideoTracks()[0];
            const fallbackDeviceId = fallbackTrack ? fallbackTrack.getSettings().deviceId : '';
            setSelectedDeviceId(fallbackDeviceId);
          }
        }
      }
    } catch (err) {
      console.error('❌ Camera error:', err.name, err.message);
      
      let errorMsg = '';
      switch (err.name) {
        case 'NotAllowedError':
        case 'PermissionDeniedError':
          errorMsg = 'Bạn đã từ chối quyền camera. Vui lòng nhấn vào biểu tượng camera trên thanh địa chỉ trình duyệt và cho phép.';
          break;
        case 'NotFoundError':
        case 'DevicesNotFoundError':
          errorMsg = 'Không tìm thấy camera. Vui lòng kiểm tra camera đã được kết nối.';
          break;
        case 'NotReadableError':
        case 'TrackStartError':
          errorMsg = 'Camera đang được sử dụng bởi ứng dụng khác. Vui lòng đóng các ứng dụng khác và thử lại.';
          break;
        case 'OverconstrainedError':
          errorMsg = 'Camera không đáp ứng được yêu cầu. Đang thử lại...';
          // Retry with basic constraints
          try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            window.__examCameraStream = stream;
            setCameraGranted(true);
            setCameraLoading(false);
            return;
          } catch {
            errorMsg = 'Không thể truy cập camera.';
          }
          break;
        default:
          errorMsg = `Lỗi camera: ${err.message || err.name || 'Không xác định'}. Vui lòng thử lại.`;
      }
      setError(errorMsg);
    }
    setCameraLoading(false);
  };

  const requestScreen = async () => {
    setScreenLoading(true);
    setError('');
    try {
      // Check if getDisplayMedia is available
      if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
        throw new Error('getDisplayMedia is not supported');
      }

      const stream = await navigator.mediaDevices.getDisplayMedia({ 
        video: { 
          cursor: 'always',
          displaySurface: 'monitor'
        },
        audio: false
      });

      // Check if user selected entire screen
      const track = stream.getVideoTracks()[0];
      if (track.getSettings().displaySurface !== 'monitor') {
        track.stop();
        throw new Error('Bạn BẮT BUỘC phải chọn thẻ "Toàn màn hình" (Entire screen). Vui lòng không chọn Tab hoặc Cửa sổ.');
      }

      // Listen for when user stops sharing
      track.addEventListener('ended', () => {
        console.log('⚠️ Screen sharing stopped by user');
        window.__examScreenStream = null;
      });

      // Store stream globally
      window.__examScreenStream = stream;
      setScreenGranted(true);
      console.log('✅ Screen access granted, tracks:', stream.getVideoTracks().length);
    } catch (err) {
      console.error('❌ Screen error:', err.name, err.message);
      
      let errorMsg = '';
      switch (err.name) {
        case 'NotAllowedError':
        case 'PermissionDeniedError':
          errorMsg = 'Bạn đã từ chối quyền ghi màn hình. Vui lòng nhấn "Cho phép" và chọn màn hình để chia sẻ.';
          break;
        case 'NotSupportedError':
          errorMsg = 'Trình duyệt không hỗ trợ ghi màn hình. Vui lòng sử dụng Chrome hoặc Edge.';
          break;
        case 'AbortError':
          errorMsg = 'Ghi màn hình bị hủy. Vui lòng thử lại và chọn màn hình để chia sẻ.';
          break;
        default:
          errorMsg = `Lỗi ghi màn hình: ${err.message || err.name || 'Không xác định'}. Vui lòng thử lại.`;
      }
      setError(errorMsg);
    }
    setScreenLoading(false);
  };

  const handleContinue = () => {
    if (cameraGranted && screenGranted) {
      onPermissionsGranted();
    }
  };

  const allGranted = cameraGranted && screenGranted;

  return (
    <div className="modal-overlay">
      <div className="modal-content glass-card">
        <div className="modal-icon">🔒</div>
        <h2 className="modal-title">Yêu cầu quyền truy cập</h2>
        <p className="modal-desc">
          Để đảm bảo tính công bằng của kỳ thi, hệ thống cần truy cập camera và ghi màn hình
          trong suốt quá trình làm bài.
        </p>

        {!apiSupported && (
          <div className="error-message" style={{ marginBottom: '16px' }}>
            ⚠️ Trình duyệt không hỗ trợ. Hãy dùng Chrome/Edge/Firefox mới nhất.
          </div>
        )}

        <div className="permission-list">
          {/* Camera Permission */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%' }}>
            <div className={`permission-item ${cameraGranted ? 'granted' : ''}`} style={{ width: '100%' }}>
              <span className="icon">📷</span>
              <div className="info">
                <h4>Camera</h4>
                <p>Giám sát thí sinh trong suốt bài thi</p>
              </div>
              {cameraGranted ? (
                <span className="status">✅</span>
              ) : (
                <button 
                  className="btn-secondary" 
                  onClick={requestCamera}
                  disabled={cameraLoading || !apiSupported}
                  style={{ fontSize: '0.8rem', padding: '6px 14px', minWidth: '80px' }}
                >
                  {cameraLoading ? '...' : 'Cho phép'}
                </button>
              )}
            </div>
            
            {cameraGranted && videoDevices.length > 1 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'rgba(255, 255, 255, 0.03)', padding: '8px 12px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.08)', animation: 'fadeIn 0.3s ease' }}>
                <span style={{ fontSize: '0.75rem', color: '#a5b4fc', fontWeight: '600', whiteSpace: 'nowrap' }}>Chọn Camera thi:</span>
                <select 
                  value={selectedDeviceId}
                  onChange={(e) => switchCamera(e.target.value)}
                  style={{
                    flex: 1,
                    background: '#13112b',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    borderRadius: '4px',
                    color: '#fff',
                    padding: '4px 8px',
                    fontSize: '0.75rem',
                    outline: 'none',
                    cursor: 'pointer'
                  }}
                >
                  {videoDevices.map(d => (
                    <option key={d.deviceId} value={d.deviceId} style={{ background: '#13112b', color: '#fff' }}>
                      {d.label || `Camera ${d.deviceId.slice(0, 5)}`}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Screen Permission */}
          <div className={`permission-item ${screenGranted ? 'granted' : ''}`}>
            <span className="icon">🖥️</span>
            <div className="info">
              <h4>Ghi màn hình</h4>
              <p>Giám sát hoạt động màn hình trong bài thi</p>
            </div>
            {screenGranted ? (
              <span className="status">✅</span>
            ) : (
              <button 
                className="btn-secondary" 
                onClick={requestScreen}
                disabled={screenLoading || !apiSupported}
                style={{ fontSize: '0.8rem', padding: '6px 14px', minWidth: '80px' }}
              >
                {screenLoading ? '...' : 'Cho phép'}
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="error-message" style={{ marginBottom: '16px', textAlign: 'left', lineHeight: '1.6' }}>
            {error}
          </div>
        )}

        <div className="modal-actions">
          <button 
            className="btn-primary" 
            onClick={handleContinue}
            disabled={!allGranted}
            style={{ width: '100%' }}
          >
            {allGranted ? 'Tiếp tục vào phòng thi →' : 'Vui lòng cấp đủ quyền truy cập'}
          </button>
        </div>
      </div>
    </div>
  );
}
