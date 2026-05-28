import os
import cv2
import json
import base64
import math
import numpy as np
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from ultralytics import YOLO

# Get current directory path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Templates Setup
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
print(f"[INIT] BASE_DIR: {BASE_DIR}")
print(f"[INIT] TEMPLATES_DIR: {TEMPLATES_DIR}")
print(f"[INIT] Templates exists: {os.path.isdir(TEMPLATES_DIR)}")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

class CandidateTracker:
    def __init__(self, max_disappeared=20, distance_threshold=200):
        self.next_id = 1
        self.candidates = {}       # label (str) -> centroid (tuple)
        self.bboxes = {}           # label (str) -> bbox [x1, y1, x2, y2]
        self.confs = {}            # label (str) -> conf (float)
        self.disappeared = {}      # label (str) -> count (int)
        self.max_disappeared = max_disappeared
        self.distance_threshold = distance_threshold

    def register(self, centroid, bbox, conf):
        label = f"id{self.next_id:02d}"
        self.candidates[label] = centroid
        self.bboxes[label] = bbox
        self.confs[label] = conf
        self.disappeared[label] = 0
        self.next_id += 1
        return label

    def deregister(self, label):
        if label in self.candidates:
            del self.candidates[label]
        if label in self.bboxes:
            del self.bboxes[label]
        if label in self.confs:
            del self.confs[label]
        if label in self.disappeared:
            del self.disappeared[label]

    def update(self, rects_with_confs):
        # rects_with_confs is a list of ([x1, y1, x2, y2], conf)
        if len(rects_with_confs) == 0:
            for label in list(self.disappeared.keys()):
                self.disappeared[label] += 1
                if self.disappeared[label] > self.max_disappeared:
                    self.deregister(label)
            return self.bboxes

        # Extract rects and confs
        rects = [item[0] for item in rects_with_confs]
        confs = [item[1] for item in rects_with_confs]

        # Compute centroids
        input_centroids = []
        for (x1, y1, x2, y2) in rects:
            cX = int((x1 + x2) / 2.0)
            cY = int((y1 + y2) / 2.0)
            input_centroids.append((cX, cY))

        if len(self.candidates) == 0:
            for i in range(len(input_centroids)):
                self.register(input_centroids[i], rects[i], confs[i])
        else:
            labels = list(self.candidates.keys())
            centroids = list(self.candidates.values())

            # Compute Euclidean distances between existing centroids and input centroids
            distances = []
            for c in centroids:
                row = []
                for ic in input_centroids:
                    d = math.sqrt((c[0] - ic[0])**2 + (c[1] - ic[1])**2)
                    row.append(d)
                distances.append(row)

            matched_inputs = set()
            matched_labels = set()

            # Greedy match based on minimum distance
            for _ in range(min(len(labels), len(input_centroids))):
                min_val = float('inf')
                min_l_idx = -1
                min_i_idx = -1
                for l_idx in range(len(labels)):
                    if l_idx in matched_labels:
                        continue
                    for i_idx in range(len(input_centroids)):
                        if i_idx in matched_inputs:
                            continue
                        if distances[l_idx][i_idx] < min_val:
                            min_val = distances[l_idx][i_idx]
                            min_l_idx = l_idx
                            min_i_idx = i_idx

                if min_val < self.distance_threshold:
                    lbl = labels[min_l_idx]
                    self.candidates[lbl] = input_centroids[min_i_idx]
                    self.bboxes[lbl] = rects[min_i_idx]
                    self.confs[lbl] = confs[min_i_idx]
                    self.disappeared[lbl] = 0
                    matched_labels.add(min_l_idx)
                    matched_inputs.add(min_i_idx)

            # Deregister or increment disappeared count for unmatched candidates
            for l_idx, lbl in enumerate(labels):
                if l_idx not in matched_labels:
                    self.disappeared[lbl] += 1
                    if self.disappeared[lbl] > self.max_disappeared:
                        self.deregister(lbl)

            # Register new candidates for unmatched inputs
            for i_idx in range(len(input_centroids)):
                if i_idx not in matched_inputs:
                    self.register(input_centroids[i_idx], rects[i_idx], confs[i_idx])

        return self.bboxes

# Global YOLO model variable
model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global model
    print("[STARTUP] Loading YOLOv8 model...")
    model = YOLO("yolov8n.pt")
    print("[STARTUP] YOLOv8 model loaded successfully.")
    yield
    # Shutdown
    print("[SHUTDOWN] Closing application...")

# Initialize FastAPI
app = FastAPI(
    title="AI Exam Proctoring System",
    description="Real-time exam room monitoring using YOLOv8 for human and phone detection",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """
    Renders the proctoring dashboard.
    """
    try:
        print("[ROUTE] Accessing dashboard...")
        template = templates.get_template("index.html")
        content = template.render(request=request)
        print("[ROUTE] Template rendered successfully")
        return content
    except Exception as e:
        print(f"[ROUTE ERROR] Error rendering template: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise

@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time video stream from the browser.
    Receives base64 encoded frames or binary image data, processes with YOLOv8,
    and returns detected objects, alerts, statistics, and the annotated frame.
    """
    await websocket.accept()
    print("[WEBSOCKET] Client connected for streaming.")
    
    tracker = CandidateTracker(max_disappeared=20, distance_threshold=200)
    session_active = False
    initial_candidates = {}
    
    try:
        while True:
            # Receive data from client
            message = await websocket.receive_text()
            data = json.loads(message)
            
            # Extract frame data (base64 string) and settings
            frame_data = data.get("image") # format: data:image/jpeg;base64,...
            conf_threshold = float(data.get("threshold", 0.35))
            exam_active = bool(data.get("exam_active", False))
            
            if not frame_data:
                continue
                
            # Decode base64 image
            header, encoded = frame_data.split(",", 1)
            image_bytes = base64.b64decode(encoded)
            img_np = np.frombuffer(image_bytes, dtype=np.uint8)
            frame = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
            
            if frame is None:
                continue
                
            h, w, _ = frame.shape
            
            # Run YOLOv8 detection
            # COCO classes: 0: person, 63: laptop, 67: cell phone, 73: book
            target_classes = [0, 63, 67, 73]
            results = model.predict(
                source=frame,
                classes=target_classes,
                conf=conf_threshold,
                verbose=False
            )
            
            # Analyze results
            boxes = results[0].boxes
            
            person_detections = []
            other_boxes = []
            
            for box in boxes:
                coords = box.xyxy[0].tolist() # [x1, y1, x2, y2]
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                if cls == 0:
                    person_detections.append((coords, conf))
                else:
                    other_boxes.append(box)
            
            # Update candidate tracker with person detections
            tracked_candidates = tracker.update(person_detections)
            
            # Handle exam session transitions
            if exam_active and not session_active:
                session_active = True
                initial_candidates = {
                    label: {
                        "centroid": tracker.candidates[label],
                        "bbox": tracker.bboxes[label]
                    }
                    for label in tracker.candidates
                }
                print(f"[EXAM] Session started. Locked {len(initial_candidates)} candidates: {list(initial_candidates.keys())}")
            elif not exam_active and session_active:
                session_active = False
                initial_candidates = {}
                print("[EXAM] Session ended.")
                
            num_persons = 0
            num_phones = 0
            num_laptops = 0
            num_books = 0
            
            violations = []
            detections_log = []
            
            # Bounding box drawing styles (BGR colors)
            COLOR_PERSON = (255, 120, 0)   # Electric Blue-ish
            COLOR_PHONE = (68, 68, 239)    # Crimson Red
            COLOR_VIOLATION = (0, 140, 255) # Warning Orange
            
            # Draw tracked candidates
            for label, coords in tracked_candidates.items():
                num_persons += 1
                conf = tracker.confs.get(label, 1.0)
                x1, y1, x2, y2 = map(int, coords)
                
                # Dynamic labels using tracked IDs
                display_label = f"Candidate {label}: {conf:.2f}"
                
                # Draw bounding box
                cv2.rectangle(frame, (x1, y1), (x2, y2), COLOR_PERSON, 2)
                
                # Draw custom label tag
                tf = max(1, int(1)) # font thickness
                label_size, base_line = cv2.getTextSize(display_label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, tf)
                ty1 = max(y1, label_size[1] + 10)
                cv2.rectangle(frame, (x1, ty1 - label_size[1] - 8), (x1 + label_size[0] + 10, ty1 + base_line - 4), COLOR_PERSON, -1)
                cv2.putText(frame, display_label, (x1 + 5, ty1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), tf, lineType=cv2.LINE_AA)
                
                detections_log.append({
                    "class": f"Person ({label})",
                    "confidence": conf,
                    "box": [x1, y1, x2, y2]
                })
                
            # Draw other non-person violations
            for box in other_boxes:
                coords = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                
                x1, y1, x2, y2 = map(int, coords)
                
                if cls == 67:
                    num_phones += 1
                    display_label = f"VIOLATION: PHONE {conf:.2f}"
                    color = COLOR_PHONE
                    violations.append("Phát hiện điện thoại!")
                elif cls == 63:
                    num_laptops += 1
                    display_label = f"VIOLATION: LAPTOP {conf:.2f}"
                    color = COLOR_VIOLATION
                    violations.append("Phát hiện laptop/màn hình!")
                elif cls == 73:
                    num_books += 1
                    display_label = f"VIOLATION: BOOK {conf:.2f}"
                    color = COLOR_VIOLATION
                    violations.append("Phát hiện tài liệu/sách!")
                
                # Draw bounding box
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                
                # Draw custom label tag
                tf = max(1, int(1))
                label_size, base_line = cv2.getTextSize(display_label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, tf)
                ty1 = max(y1, label_size[1] + 10)
                cv2.rectangle(frame, (x1, ty1 - label_size[1] - 8), (x1 + label_size[0] + 10, ty1 + base_line - 4), color, -1)
                cv2.putText(frame, display_label, (x1 + 5, ty1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), tf, lineType=cv2.LINE_AA)
                
                detections_log.append({
                    "class": model.names[cls],
                    "confidence": conf,
                    "box": [x1, y1, x2, y2]
                })
            
            # Rule engine for exam proctoring
            if session_active:
                # 1. Check if any initial candidate has disappeared/left position
                for init_lbl in initial_candidates:
                    if init_lbl not in tracker.bboxes:
                        violations.append(f"Thí sinh {init_lbl} đã rời khỏi vị trí!")
                
                # 2. Check if any candidate has moved significantly
                for init_lbl, init_data in initial_candidates.items():
                    if init_lbl in tracker.candidates:
                        curr_c = tracker.candidates[init_lbl]
                        init_c = init_data["centroid"]
                        dist = math.sqrt((curr_c[0] - init_c[0])**2 + (curr_c[1] - init_c[1])**2)
                        if dist > 100:
                            violations.append(f"Thí sinh {init_lbl} rời khỏi vị trí ({int(dist)}px)!")
                            
                # 3. Check if any new candidate appeared (intruder)
                for curr_lbl in tracker.bboxes:
                    if curr_lbl not in initial_candidates:
                        violations.append(f"Phát hiện người lạ/người khác xuất hiện: {curr_lbl}!")
            else:
                # Non-active session, standard warning if zero candidates
                if num_persons == 0:
                    violations.append("Không có thí sinh trong khung hình!")
                
            # Calculate Suspicion Index (0 - 100)
            suspicion_index = 0
            if num_phones > 0:
                suspicion_index = 100
            elif any("rời khỏi vị trí" in v or "người lạ" in v or "người khác" in v for v in violations):
                suspicion_index = 90
            elif num_laptops > 0 or num_books > 0:
                suspicion_index = 60
            elif num_persons == 0:
                suspicion_index = 40
            else:
                suspicion_index = 0
                
            # Encode annotated frame back to base64
            _, buffer = cv2.imencode(".jpg", frame)
            processed_base64 = "data:image/jpeg;base64," + base64.b64encode(buffer).decode("utf-8")
            
            # Prepare response payload
            response_payload = {
                "image": processed_base64,
                "metrics": {
                    "num_persons": num_persons,
                    "num_phones": num_phones,
                    "num_laptops": num_laptops,
                    "num_books": num_books,
                    "suspicion_index": suspicion_index,
                    "violations": violations,
                    "detections": detections_log
                }
            }
            
            # Send back to client
            await websocket.send_text(json.dumps(response_payload))
            
    except WebSocketDisconnect:
        print("[WEBSOCKET] Client disconnected.")
    except Exception as e:
        print(f"[WEBSOCKET ERROR] Error: {e}")
        try:
            await websocket.close()
        except:
            pass

@app.get("/video_feed")
def get_video_feed():
    """
    Fallback MJPEG streaming using local webcam connected to server.
    Useful for local machine testing.
    """
    def generate_frames():
        # Setup local video capture
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            print("[CAMERA ERROR] Local camera could not be opened.")
            return
            
        try:
            while True:
                success, frame = camera.read()
                if not success:
                    break
                    
                # Run YOLOv8
                if model is not None:
                    target_classes = [0, 63, 67, 73]
                    results = model.predict(source=frame, classes=target_classes, conf=0.35, verbose=False)
                    
                    # Manual draw for parity
                    boxes = results[0].boxes
                    for box in boxes:
                        coords = box.xyxy[0].tolist()
                        conf = float(box.conf[0])
                        cls = int(box.cls[0])
                        
                        x1, y1, x2, y2 = map(int, coords)
                        
                        if cls == 0:
                            color = (255, 120, 0)
                            label = f"Candidate: {conf:.2f}"
                        elif cls == 67:
                            color = (68, 68, 239)
                            label = f"PHONE: {conf:.2f}"
                        else:
                            color = (0, 140, 255)
                            label = f"VIOLATION: {model.names[cls]} {conf:.2f}"
                            
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                        cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                
                # Encode and yield
                ret, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        finally:
            camera.release()
            
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")
