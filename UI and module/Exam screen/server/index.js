import express from 'express';
import { WebSocketServer } from 'ws';
import Tesseract from 'tesseract.js';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ── State ──────────────────────────────────────────────
let config = {
  mode: 'TRAC_NGHIEM',
  blacklist: ['chatgpt', 'zalo', 'gemini', 'messenger']
};
let isCurrentCopySessionHigh = false;

// ── OCR Queue (sequential processing to prevent image-label mismatch) ──
let ocrQueue = Promise.resolve();
function enqueueTask(fn) {
  ocrQueue = ocrQueue.then(fn).catch(err => console.error('[QUEUE] Error:', err));
  return ocrQueue;
}

// ── Tesseract Worker (singleton) ───────────────────────
let worker = null;

async function initWorker() {
  worker = await Tesseract.createWorker('eng');
  console.log('[OCR] Tesseract worker initialized (eng)');
}

// ── OCR Analysis ───────────────────────────────────────
async function analyzeImage(imageBase64, blacklist) {
  // Validate image data before OCR
  if (!imageBase64 || imageBase64.length < 100) {
    console.log('[OCR] Skipped: empty or too-short image data');
    return { found: false, keyword: null, bboxes: [] };
  }

  if (!worker) await initWorker();

  try {
    // Strip data URI prefix if present
    const base64Data = imageBase64.replace(/^data:image\/\w+;base64,/, '');
    const buffer = Buffer.from(base64Data, 'base64');

    // Validate buffer has enough data to be a real image
    if (buffer.length < 100) {
      console.log('[OCR] Skipped: buffer too small to be a valid image');
      return { found: false, keyword: null, bboxes: [] };
    }

    const { data } = await worker.recognize(buffer);
    const normalized = data.text.toLowerCase().replace(/\s+/g, '');

    console.log(`[OCR] Extracted text (${normalized.length} chars): "${normalized.substring(0, 100)}..."`);

    // Find matching keyword
    let matchedKeyword = null;
    for (const keyword of blacklist) {
      if (normalized.includes(keyword.toLowerCase())) {
        matchedKeyword = keyword;
        break;
      }
    }

    if (!matchedKeyword) {
      return { found: false, keyword: null, bboxes: [] };
    }

    // Extract bounding boxes from word-level data
    const bboxes = [];
    let words = data.words || [];
    if (words.length === 0 && data.blocks) {
      for (const block of data.blocks) {
        for (const para of (block.paragraphs || [])) {
          for (const line of (para.lines || [])) {
            words = words.concat(line.words || []);
          }
        }
      }
    }
    console.log(`[OCR] Words count: ${words.length}`);
    if (words.length > 0) {
      console.log(`[OCR] Sample words: ${words.slice(0, 5).map(w => `"${w.text}"`).join(', ')}`);
    }
    const kwLower = matchedKeyword.toLowerCase();

    // Try single-word match first
    for (const word of words) {
      if (!word.bbox) continue;
      const wText = word.text.toLowerCase().replace(/\s+/g, '');
      if (wText.includes(kwLower) || (kwLower.includes(wText) && wText.length >= 3)) {
        bboxes.push({ x0: word.bbox.x0, y0: word.bbox.y0, x1: word.bbox.x1, y1: word.bbox.y1 });
      }
    }

    // If no single-word match, try sliding window over consecutive words
    if (bboxes.length === 0) {
      for (let i = 0; i < words.length; i++) {
        let concat = '';
        for (let j = i; j < words.length && concat.length < kwLower.length + 20; j++) {
          concat += words[j].text.toLowerCase().replace(/\s+/g, '');
          if (concat.includes(kwLower)) {
            const group = words.slice(i, j + 1).filter(w => w.bbox);
            if (group.length > 0) {
              bboxes.push({
                x0: Math.min(...group.map(w => w.bbox.x0)),
                y0: Math.min(...group.map(w => w.bbox.y0)),
                x1: Math.max(...group.map(w => w.bbox.x1)),
                y1: Math.max(...group.map(w => w.bbox.y1))
              });
            }
            break;
          }
        }
        if (bboxes.length > 0) break;
      }
    }

    console.log(`[OCR] Found "${matchedKeyword}" with ${bboxes.length} bbox(es)`);
    return { found: true, keyword: matchedKeyword, bboxes };
  } catch (err) {
    console.error('[OCR] Error analyzing image:', err.message);
    return { found: false, keyword: null, bboxes: [] };
  }
}

// ── Express (HTTP on port 3000) ────────────────────────
const app = express();

app.listen(3000, () => {
  console.log('[HTTP] Server running on http://localhost:3000');
});

// ── WebSocket (port 8080) ──────────────────────────────
const wss = new WebSocketServer({ port: 8080 });

// Track connected admins
const admins = new Set();
// Track student statuses
let studentStatus = { connected: 0, sharing: 0 };

function broadcastStudentStatus() {
  broadcastToAdmins({
    event_type: 'STUDENT_STATUS',
    status: studentStatus
  });
}

// Periodically broadcast status just in case it was missed
setInterval(broadcastStudentStatus, 5000);

function broadcastToAdmins(data) {
  const msg = JSON.stringify(data);
  for (const admin of admins) {
    if (admin.readyState === 1) {
      admin.send(msg);
    }
  }
}

wss.on('connection', (ws, req) => {
  const url = new URL(req.url, 'http://localhost:8080');
  const role = url.searchParams.get('role');

  if (role === 'admin') {
    admins.add(ws);
    console.log('[WS] Admin connected');
    // Send current config and status to the newly connected admin
    ws.send(JSON.stringify({
      event_type: 'STUDENT_STATUS',
      status: studentStatus
    }));
    ws.send(JSON.stringify({
      event_type: 'CONFIG_UPDATE',
      config: config
    }));
  } else {
    console.log('[WS] Student connected');
    ws.isStudent = true;
    ws.isSharing = false;
    studentStatus.connected++;
    broadcastStudentStatus();
  }

  ws.on('message', (raw) => {
    let data;
    try {
      data = JSON.parse(raw);
    } catch {
      return;
    }

    // ── Admin sends config update ──
    if (data.action === 'UPDATE_CONFIG') {
      config.mode = data.mode || config.mode;
      config.blacklist = data.blacklist || config.blacklist;
      console.log('[CONFIG] Updated:', JSON.stringify(config));
      return;
    }

    const eventType = data.event_type;
    console.log(`[EVENT] ${eventType} | Mode: ${config.mode}`);

    // ── SCREEN_SHARE_STARTED ──
    if (eventType === 'SCREEN_SHARE_STARTED') {
      if (ws.isStudent && !ws.isSharing) {
        ws.isSharing = true;
        studentStatus.sharing++;
        broadcastStudentStatus();
      }
      return;
    }

    // ── SCREEN_SHARE_STOPPED: Broadcast immediately, no OCR ──
    if (eventType === 'SCREEN_SHARE_STOPPED') {
      if (ws.isStudent && ws.isSharing) {
        ws.isSharing = false;
        studentStatus.sharing--;
        broadcastStudentStatus();
      }
      broadcastToAdmins({
        exam_mode: config.mode,
        event_type: 'SCREEN_SHARE_STOPPED',
        alert_level: 'HIGH',
        reason: 'SCREEN_SHARE_DISCONNECTED',
        student_id: data.student_id || null
      });
      console.log('[ALERT] SCREEN_SHARE_STOPPED -> HIGH');
      return;
    }

    // ── SHARE_VIOLATION: Wrong share mode timeout ──
    if (eventType === 'SHARE_VIOLATION') {
      broadcastToAdmins({
        exam_mode: config.mode,
        event_type: 'SHARE_VIOLATION',
        alert_level: 'HIGH',
        reason: data.reason || 'WRONG_SHARE_MODE',
        student_id: data.student_id || null
      });
      console.log(`[ALERT] SHARE_VIOLATION -> HIGH (${data.reason})`);
      return;
    }

    // ── CHẾ ĐỘ TRẮC NGHIỆM: Mọi event → HIGH, không OCR ──
    if (config.mode === 'TRAC_NGHIEM') {
      broadcastToAdmins({
        exam_mode: 'TRAC_NGHIEM',
        event_type: eventType,
        alert_level: 'HIGH',
        reason: 'THEORY_MODE_ALL_HIGH',
        copied_text: data.copied_text || null,
        image: data.image || null,
        student_id: data.student_id || null
      });
      console.log(`[ALERT] TRAC_NGHIEM -> HIGH (${eventType})`);
      return;
    }

    // ── CHẾ ĐỘ THỰC HÀNH ──

    // COPY_DETECTED — no OCR needed, process immediately
    if (eventType === 'COPY_DETECTED') {
      isCurrentCopySessionHigh = false;
      broadcastToAdmins({
        exam_mode: 'THUC_HANH',
        event_type: 'COPY_DETECTED',
        alert_level: 'MEDIUM',
        reason: 'COPY_ATTEMPT',
        copied_text: data.copied_text || '',
        student_id: data.student_id || null
      });
      console.log('[ALERT] COPY_DETECTED -> MEDIUM');
      return;
    }

    // ── Events needing OCR: enqueue to prevent image-label mismatch ──
    enqueueTask(async () => {
      const studentId = data.student_id || null;

      // COPY_FRAME
      if (eventType === 'COPY_FRAME') {
        if (isCurrentCopySessionHigh) {
          broadcastToAdmins({
            exam_mode: 'THUC_HANH',
            event_type: 'COPY_FRAME',
            alert_level: 'HIGH',
            reason: 'COPY_SESSION_ALREADY_HIGH',
            image: data.image,
            student_id: studentId
          });
          console.log('[ALERT] COPY_FRAME -> HIGH (skip OCR, forwarding evidence)');
        } else if (!data.image || data.image.length < 100) {
          broadcastToAdmins({
            exam_mode: 'THUC_HANH',
            event_type: 'COPY_FRAME',
            alert_level: 'MEDIUM',
            reason: 'NO_IMAGE_DATA',
            image: null,
            student_id: studentId
          });
          console.log('[ALERT] COPY_FRAME -> MEDIUM (no image)');
        } else {
          const result = await analyzeImage(data.image, config.blacklist);
          if (result.found) {
            isCurrentCopySessionHigh = true;
            broadcastToAdmins({
              exam_mode: 'THUC_HANH',
              event_type: 'COPY_FRAME',
              alert_level: 'HIGH',
              matched_keyword: result.keyword,
              bboxes: result.bboxes,
              image: data.image,
              student_id: studentId
            });
            console.log(`[ALERT] COPY_FRAME -> HIGH (found: "${result.keyword}")`);
          } else {
            broadcastToAdmins({
              exam_mode: 'THUC_HANH',
              event_type: 'COPY_FRAME',
              alert_level: 'MEDIUM',
              image: data.image,
              student_id: studentId
            });
            console.log('[ALERT] COPY_FRAME -> MEDIUM (clean)');
          }
        }
        return;
      }

      // BLUR / VISIBILITY_CHANGE
      if (eventType === 'BLUR' || eventType === 'VISIBILITY_CHANGE') {
        if (!data.image || data.image.length < 100) {
          console.log(`[ALERT] ${eventType} -> LOW (no image to analyze)`);
          broadcastToAdmins({
            exam_mode: 'THUC_HANH',
            event_type: eventType,
            alert_level: 'LOW',
            reason: 'NO_IMAGE_DATA',
            image: null,
            student_id: studentId
          });
          return;
        }
        const result = await analyzeImage(data.image, config.blacklist);
        if (result.found) {
          broadcastToAdmins({
            exam_mode: 'THUC_HANH',
            event_type: eventType,
            alert_level: 'HIGH',
            matched_keyword: result.keyword,
            bboxes: result.bboxes,
            image: data.image,
            student_id: studentId
          });
          console.log(`[ALERT] ${eventType} -> HIGH (found: "${result.keyword}")`);
        } else {
          broadcastToAdmins({
            exam_mode: 'THUC_HANH',
            event_type: eventType,
            alert_level: 'LOW',
            image: data.image,
            student_id: studentId
          });
          console.log(`[ALERT] ${eventType} -> LOW (clean)`);
        }
        return;
      }

      console.log(`[WARN] Unknown event_type: ${eventType}`);
    });
  });

  ws.on('close', () => {
    if (role === 'admin') {
      admins.delete(ws);
      console.log('[WS] Admin disconnected');
    } else {
      console.log('[WS] Student disconnected (Browser closed or connection lost)');
      if (ws.isStudent) {
        studentStatus.connected = Math.max(0, studentStatus.connected - 1);
        if (ws.isSharing) {
          studentStatus.sharing = Math.max(0, studentStatus.sharing - 1);
        }
        broadcastStudentStatus();
      }
      // Broadcast to admins that student disconnected
      broadcastToAdmins({
        exam_mode: config.mode,
        event_type: 'SCREEN_SHARE_STOPPED',
        alert_level: 'HIGH',
        reason: 'Mất kết nối (Đóng trình duyệt / rớt mạng)'
      });
    }
  });
});

console.log('[WS] WebSocket server running on ws://localhost:8080');

// Init Tesseract worker on startup
initWorker().catch(err => console.error('[OCR] Init failed:', err));
