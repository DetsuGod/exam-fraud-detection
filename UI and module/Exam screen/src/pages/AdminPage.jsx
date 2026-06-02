import { useState, useEffect, useRef, useCallback } from 'react';

const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_URL = `${protocol}//${window.location.host}/ws/exam?role=admin`;

// ── Vietnamese translations ──
const EVENT_VI = {
  'BLUR': 'Rời khỏi trang',
  'VISIBILITY_CHANGE': 'Chuyển tab',
  'COPY_DETECTED': 'Phát hiện sao chép',
  'COPY_FRAME': 'Chụp sau sao chép',
  'SCREEN_SHARE_STOPPED': 'Ngắt chia sẻ màn hình',
  'SHARE_VIOLATION': 'Vi phạm chia sẻ'
};
const LEVEL_VI = { 'HIGH': 'CAO', 'MEDIUM': 'Trung Bình', 'LOW': 'Thấp' };
const MODE_VI = { 'THUC_HANH': 'Thực hành', 'TRAC_NGHIEM': 'Trắc nghiệm' };
const REASON_VI = {
  'THEORY_MODE_ALL_HIGH': 'Vi phạm quy chế',
  'COPY_ATTEMPT': 'Thao tác sao chép',
  'COPY_SESSION_ALREADY_HIGH': 'Phiên sao chép đã vi phạm',
  'NO_IMAGE_DATA': 'Không có dữ liệu ảnh',
  'SCREEN_SHARE_DISCONNECTED': 'Đã ngắt chia sẻ màn hình',
  'WRONG_SHARE_MODE': 'Sai chế độ chia sẻ'
};

function vi(map, key) { return map[key] || key; }

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ── Evidence Canvas with bounding boxes ──
function EvidenceCanvas({ imageSrc, bboxes }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!imageSrc || !bboxes?.length) return;
    const img = new Image();
    img.onload = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0);
      ctx.strokeStyle = '#ff0000';
      ctx.lineWidth = 3;
      ctx.fillStyle = 'rgba(255, 0, 0, 0.15)';
      for (const bbox of bboxes) {
        const w = bbox.x1 - bbox.x0;
        const h = bbox.y1 - bbox.y0;
        ctx.fillRect(bbox.x0, bbox.y0, w, h);
        ctx.strokeRect(bbox.x0, bbox.y0, w, h);
      }
    };
    img.src = imageSrc;
  }, [imageSrc, bboxes]);

  return <canvas ref={canvasRef} className="admin-evidence-canvas" />;
}

// ── Log Entry Component ──
function LogEntry({ entry }) {
  const time = new Date(entry.timestamp).toLocaleTimeString('vi-VN');
  const levelClass = entry.alert_level?.toLowerCase() || 'low';

  // Screen share stopped
  if (entry.event_type === 'SCREEN_SHARE_STOPPED') {
    return (
      <div className={`admin-log-entry screen-share-stopped`}>
        <div className="admin-log-header">
          <span className="admin-badge screen-share-stopped">⚠️ NGẮT KẾT NỐI</span>
          <span className="admin-log-event">{vi(EVENT_VI, 'SCREEN_SHARE_STOPPED')}</span>
          {entry.student_id && <span className="admin-log-student">👤 {entry.student_id}</span>}
          <span className="admin-log-time">{time}</span>
        </div>
        <div className="admin-log-body">🖥️ Thí sinh đã ngắt kết nối chia sẻ màn hình!</div>
      </div>
    );
  }

  // Share violation
  if (entry.event_type === 'SHARE_VIOLATION') {
    return (
      <div className={`admin-log-entry high`}>
        <div className="admin-log-header">
          <span className="admin-badge high">🚨 VI PHẠM</span>
          <span className="admin-log-event">{vi(EVENT_VI, 'SHARE_VIOLATION')}</span>
          {entry.student_id && <span className="admin-log-student">👤 {entry.student_id}</span>}
          <span className="admin-log-time">{time}</span>
        </div>
        <div className="admin-log-body">🚨 Thí sinh không chia sẻ toàn bộ màn hình!</div>
      </div>
    );
  }

  // Copy detected
  if (entry.event_type === 'COPY_DETECTED') {
    return (
      <div className={`admin-log-entry medium`}>
        <div className="admin-log-header">
          <span className="admin-badge medium">{vi(LEVEL_VI, 'MEDIUM')}</span>
          <span className="admin-log-event">{vi(EVENT_VI, 'COPY_DETECTED')}</span>
          {entry.student_id && <span className="admin-log-student">👤 {entry.student_id}</span>}
          <span className="admin-log-time">{time}</span>
        </div>
        <div className="admin-log-body">
          Thí sinh sao chép văn bản: <strong>"{escapeHtml(entry.copied_text || '')}"</strong> — Bắt đầu theo dõi...
        </div>
      </div>
    );
  }

  // Other events: BLUR, VISIBILITY_CHANGE, COPY_FRAME
  let reason = '';
  if (entry.matched_keyword) {
    reason += ` | Từ khóa phát hiện: "${entry.matched_keyword}"`;
  }
  if (entry.reason) {
    reason += ` | ${vi(REASON_VI, entry.reason)}`;
  }

  const hasBoxes = entry.image && entry.bboxes?.length > 0;

  return (
    <div className={`admin-log-entry ${levelClass}`}>
      <div className="admin-log-header">
        <span className={`admin-badge ${levelClass}`}>{vi(LEVEL_VI, entry.alert_level)}</span>
        <span className="admin-log-event">{vi(EVENT_VI, entry.event_type)}</span>
        {entry.student_id && <span className="admin-log-student">👤 {entry.student_id}</span>}
        <span className="admin-log-time">{time}</span>
      </div>
      <div className="admin-log-body">
        Chế độ: {vi(MODE_VI, entry.exam_mode)}{reason}
      </div>
      {hasBoxes && <EvidenceCanvas imageSrc={entry.image} bboxes={entry.bboxes} />}
      {entry.image && !hasBoxes && (
        <img src={entry.image} alt="Ảnh chứng cứ" className="admin-evidence-img" />
      )}
    </div>
  );
}

export default function AdminPage() {
  const [wsConnected, setWsConnected] = useState(false);
  const [studentStatus, setStudentStatus] = useState({ connected: 0, sharing: 0 });
  const [mode, setMode] = useState('TRAC_NGHIEM');
  const [blacklist, setBlacklist] = useState('chatgpt,zalo,gemini,messenger');
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState({ total: 0, high: 0, medium: 0, low: 0 });
  const [currentTab, setCurrentTab] = useState('all');
  const [tabCounts, setTabCounts] = useState({ share: 0, copy: 0, behavior: 0 });
  const wsRef = useRef(null);

  // ── Determine event category ──
  const getCategory = useCallback((eventType) => {
    if (['SCREEN_SHARE_STOPPED', 'SHARE_VIOLATION'].includes(eventType)) return 'share';
    if (['COPY_DETECTED', 'COPY_FRAME'].includes(eventType)) return 'copy';
    if (['BLUR', 'VISIBILITY_CHANGE'].includes(eventType)) return 'behavior';
    return 'other';
  }, []);

  // ── Handle incoming events ──
  const handleEvent = useCallback((data) => {
    if (data.event_type === 'STUDENT_STATUS') {
      setStudentStatus(data.status);
      return;
    }
    if (data.event_type === 'CONFIG_UPDATE') {
      if (data.config) {
        setMode(data.config.mode || 'TRAC_NGHIEM');
        setBlacklist((data.config.blacklist || []).join(','));
      }
      return;
    }

    const category = getCategory(data.event_type);
    const entry = { ...data, timestamp: Date.now(), id: Date.now() + Math.random(), category };

    setLogs(prev => [entry, ...prev]);
    setStats(prev => ({
      total: prev.total + 1,
      high: prev.high + (data.alert_level === 'HIGH' ? 1 : 0),
      medium: prev.medium + (data.alert_level === 'MEDIUM' ? 1 : 0),
      low: prev.low + (data.alert_level === 'LOW' ? 1 : 0),
    }));

    // Update tab badge counts
    if (category !== 'other') {
      setTabCounts(prev => ({ ...prev, [category]: prev[category] + 1 }));
    }
  }, [getCategory]);

  // ── WebSocket connection ──
  useEffect(() => {
    function connect() {
      const ws = new WebSocket(WS_URL);
      ws.onopen = () => setWsConnected(true);
      ws.onclose = () => {
        setWsConnected(false);
        setTimeout(connect, 3000);
      };
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleEvent(data);
        } catch { /* ignore */ }
      };
      wsRef.current = ws;
    }
    connect();
    return () => {
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
  }, [handleEvent]);

  // ── Send config to server ──
  const sendConfig = () => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      const blacklistArr = blacklist.split(',').map(s => s.trim()).filter(Boolean);
      ws.send(JSON.stringify({
        action: 'UPDATE_CONFIG',
        mode,
        blacklist: blacklistArr
      }));
    }
  };

  // ── Switch tab ──
  const switchTab = (tabId) => {
    setCurrentTab(tabId);
    if (tabId !== 'all') {
      setTabCounts(prev => ({ ...prev, [tabId]: 0 }));
    }
  };

  // ── Filter logs by tab ──
  const filteredLogs = currentTab === 'all'
    ? logs
    : logs.filter(l => l.category === currentTab);

  const isConnected = studentStatus.connected > 0;
  const isSharing = studentStatus.sharing > 0;

  return (
    <div className="admin-page">
      <header className="admin-header">
        <div className="admin-header-brand">
          <span className="admin-shield">🛡️</span>
          <h1 className="admin-title">Bảng Điều Khiển Giám Sát</h1>
        </div>
        <div className="admin-header-right">
          <div className={`admin-ws-status ${wsConnected ? 'connected' : ''}`}>
            <span className={`admin-ws-dot ${wsConnected ? 'on' : 'off'}`} />
            {wsConnected ? 'Đã kết nối' : 'Đang kết nối...'}
          </div>
        </div>
      </header>

      <main className="admin-content">
        {/* Student Status + Config Panel */}
        <div className="admin-top-panels">
          <div className="admin-panel glass-card">
            <h3 className="admin-panel-title">📡 Trạng thái thí sinh</h3>
            <div className="admin-status-grid">
              <div className="admin-status-item">
                <span className={`admin-indicator ${isConnected ? 'on' : 'off'}`} />
                <span className="admin-status-label">Hệ thống:</span>
                <strong style={{ color: isConnected ? 'var(--color-success)' : 'var(--color-danger)' }}>
                  {isConnected ? 'Đã kết nối' : 'Chưa kết nối'}
                </strong>
              </div>
              <div className="admin-status-item">
                <span className={`admin-indicator ${isSharing ? 'on' : 'off'}`} />
                <span className="admin-status-label">Màn hình:</span>
                <strong style={{ color: isSharing ? 'var(--color-success)' : 'var(--color-danger)' }}>
                  {isSharing ? 'Đang chia sẻ' : 'Chưa chia sẻ'}
                </strong>
              </div>
            </div>
          </div>

          <div className="admin-panel glass-card">
            <h3 className="admin-panel-title">⚙️ Cấu hình giám sát</h3>
            <div className="admin-config-form">
              <div className="admin-config-row">
                <label>Chế độ thi:</label>
                <select value={mode} onChange={(e) => setMode(e.target.value)} className="admin-select">
                  <option value="THUC_HANH">Thực hành</option>
                  <option value="TRAC_NGHIEM">Trắc nghiệm</option>
                </select>
              </div>
              <div className="admin-config-row">
                <label>Từ khóa cấm:</label>
                <input
                  type="text"
                  value={blacklist}
                  onChange={(e) => setBlacklist(e.target.value)}
                  className="admin-input"
                  placeholder="chatgpt,zalo,gemini,..."
                />
              </div>
              <button className="btn-primary admin-config-btn" onClick={sendConfig}>
                Cập nhật cấu hình
              </button>
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="admin-stats-row">
          <div className="admin-stat-box glass-card">
            <div className="admin-stat-num">{stats.total}</div>
            <div className="admin-stat-label">Tổng sự kiện</div>
          </div>
          <div className="admin-stat-box glass-card">
            <div className="admin-stat-num high">{stats.high}</div>
            <div className="admin-stat-label">Mức Cao</div>
          </div>
          <div className="admin-stat-box glass-card">
            <div className="admin-stat-num medium">{stats.medium}</div>
            <div className="admin-stat-label">Mức Trung Bình</div>
          </div>
          <div className="admin-stat-box glass-card">
            <div className="admin-stat-num low">{stats.low}</div>
            <div className="admin-stat-label">Mức Thấp</div>
          </div>
        </div>

        {/* Log Area */}
        <div className="admin-log-section glass-card">
          <h2 className="admin-log-title">📋 Log sự kiện</h2>

          {/* Tabs */}
          <div className="admin-tabs">
            {[
              { id: 'all', label: 'Tất cả' },
              { id: 'share', label: 'Chia sẻ MH' },
              { id: 'copy', label: 'Sao chép' },
              { id: 'behavior', label: 'Hành vi' },
            ].map(tab => (
              <button
                key={tab.id}
                className={`admin-tab-btn ${currentTab === tab.id ? 'active' : ''}`}
                onClick={() => switchTab(tab.id)}
              >
                {tab.label}
                {tab.id !== 'all' && tabCounts[tab.id] > 0 && (
                  <span className="admin-tab-badge">{tabCounts[tab.id]}</span>
                )}
              </button>
            ))}
          </div>

          {/* Log entries */}
          <div className="admin-log-area">
            {filteredLogs.length === 0 && (
              <div className="admin-log-empty">
                Chưa có sự kiện nào. Đang chờ kết nối từ thí sinh...
              </div>
            )}
            {filteredLogs.map(entry => (
              <LogEntry key={entry.id} entry={entry} />
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
