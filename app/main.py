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
    def __init__(self, max_disappeared=20, distance_threshold=250):
        self.next_id = 1
        self.candidates = {}       # label (str) -> centroid (tuple)
        self.bboxes = {}           # label (str) -> bbox [x1, y1, x2, y2]
        self.confs = {}            # label (str) -> conf (float)
        self.disappeared = {}      # label (str) -> count (int)
        self.max_disappeared = max_disappeared
        self.distance_threshold = distance_threshold

    def compute_iou(self, boxA, boxB):
        # Determine the (x, y)-coordinates of the intersection rectangle
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        # Compute the area of intersection rectangle
        interArea = max(0, xB - xA) * max(0, yB - yA)

        # Compute the area of both bounding boxes
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

        # Compute the Intersection over Union
        return interArea / float(boxAArea + boxBArea - interArea + 1e-6)

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
            existing_bboxes = [self.bboxes[l] for l in labels]

            # Generate all match candidate pairs
            pairs = []
            for l_idx, lbl in enumerate(labels):
                for i_idx, input_rect in enumerate(rects):
                    iou_val = self.compute_iou(existing_bboxes[l_idx], input_rect)
                    
                    # Centroid distance
                    c_old = centroids[l_idx]
                    c_new = input_centroids[i_idx]
                    dist = math.sqrt((c_old[0] - c_new[0])**2 + (c_old[1] - c_new[1])**2)
                    
                    pairs.append({
                        "l_idx": l_idx,
                        "lbl": lbl,
                        "i_idx": i_idx,
                        "iou": iou_val,
                        "dist": dist
                    })

            # Sort pairs prioritizing IoU over distance
            def sort_key(p):
                if p["iou"] > 0.05:
                    return (-1000 - p["iou"], p["dist"])
                else:
                    return (p["dist"], -p["iou"])

            pairs.sort(key=sort_key)

            matched_inputs = set()
            matched_labels = set()

            for p in pairs:
                l_idx = p["l_idx"]
                i_idx = p["i_idx"]
                lbl = p["lbl"]
                
                if l_idx in matched_labels or i_idx in matched_inputs:
                    continue
                
                # Check matching criteria
                is_match = False
                if p["iou"] > 0.05:
                    is_match = True
                elif p["dist"] < self.distance_threshold:
                    is_match = True
                
                if is_match:
                    # Apply EMA Bounding Box smoothing
                    alpha = 0.6
                    prev_bbox = self.bboxes[lbl]
                    curr_bbox = rects[i_idx]
                    
                    smoothed_bbox = [
                        alpha * curr_bbox[0] + (1 - alpha) * prev_bbox[0],
                        alpha * curr_bbox[1] + (1 - alpha) * prev_bbox[1],
                        alpha * curr_bbox[2] + (1 - alpha) * prev_bbox[2],
                        alpha * curr_bbox[3] + (1 - alpha) * prev_bbox[3]
                    ]
                    
                    s_cX = int((smoothed_bbox[0] + smoothed_bbox[2]) / 2.0)
                    s_cY = int((smoothed_bbox[1] + smoothed_bbox[3]) / 2.0)
                    
                    self.candidates[lbl] = (s_cX, s_cY)
                    self.bboxes[lbl] = smoothed_bbox
                    self.confs[lbl] = confs[i_idx]
                    self.disappeared[lbl] = 0
                    
                    matched_labels.add(l_idx)
                    matched_inputs.add(i_idx)

            # Deregister unmatched candidates
            for l_idx, lbl in enumerate(labels):
                if l_idx not in matched_labels:
                    self.disappeared[lbl] += 1
                    if self.disappeared[lbl] > self.max_disappeared:
                        self.deregister(lbl)

            # Register new candidates
            for i_idx in range(len(input_centroids)):
                if i_idx not in matched_inputs:
                    self.register(input_centroids[i_idx], rects[i_idx], confs[i_idx])

        return self.bboxes

def merge_person_detections(person_detections, iou_threshold=0.15, containment_threshold=0.5, proximity_ratio=0.2):
    """
    Greedily merges fragmented/split person bounding boxes that belong to the same person
    due to physical occlusions (e.g. holding a phone in front of the body).
    """
    if len(person_detections) < 2:
        return person_detections
        
    merged = True
    current_dets = list(person_detections)
    
    while merged:
        merged = False
        new_dets = []
        skip_indices = set()
        
        for i in range(len(current_dets)):
            if i in skip_indices:
                continue
                
            boxA, confA = current_dets[i]
            x1_A, y1_A, x2_A, y2_A = boxA
            wA = x2_A - x1_A
            hA = y2_A - y1_A
            areaA = wA * hA
            
            merged_box = list(boxA)
            merged_conf = confA
            
            for j in range(i + 1, len(current_dets)):
                if j in skip_indices:
                    continue
                    
                boxB, confB = current_dets[j]
                x1_B, y1_B, x2_B, y2_B = boxB
                wB = x2_B - x1_B
                hB = y2_B - y1_B
                areaB = wB * hB
                
                # Compute intersection
                xA_int = max(x1_A, x1_B)
                yA_int = max(y1_A, y1_B)
                xB_int = min(x2_A, x2_B)
                yB_int = min(y2_A, y2_B)
                
                inter_w = max(0, xB_int - xA_int)
                inter_h = max(0, yB_int - yA_int)
                inter_area = inter_w * inter_h
                
                iou = inter_area / float(areaA + areaB - inter_area + 1e-6)
                containmentA = inter_area / float(areaA + 1e-6)
                containmentB = inter_area / float(areaB + 1e-6)
                
                # Check horizontal overlap for vertical splitting
                x_overlap = max(0, min(x2_A, x2_B) - max(x1_A, x1_B))
                h_overlap_ratio_A = x_overlap / float(wA + 1e-6)
                h_overlap_ratio_B = x_overlap / float(wB + 1e-6)
                
                # Check vertical gap
                if y2_A <= y1_B:
                    v_gap = y1_B - y2_A
                elif y2_B <= y1_A:
                    v_gap = y1_A - y2_B
                else:
                    v_gap = 0
                    
                max_h = max(hA, hB)
                is_vertically_split = (h_overlap_ratio_A > 0.6 and h_overlap_ratio_B > 0.6 and v_gap < proximity_ratio * max_h)
                
                # Check vertical overlap for horizontal splitting
                y_overlap = max(0, min(y2_A, y2_B) - max(y1_A, y1_B))
                v_overlap_ratio_A = y_overlap / float(hA + 1e-6)
                v_overlap_ratio_B = y_overlap / float(hB + 1e-6)
                
                # Check horizontal gap
                if x2_A <= x1_B:
                    h_gap = x1_B - x2_A
                elif x2_B <= x1_A:
                    h_gap = x1_A - x2_B
                else:
                    h_gap = 0
                    
                max_w = max(wA, wB)
                is_horizontally_split = (v_overlap_ratio_A > 0.6 and v_overlap_ratio_B > 0.6 and h_gap < proximity_ratio * max_w)
                
                # If any criteria are met, merge them
                if iou > iou_threshold or containmentA > containment_threshold or containmentB > containment_threshold or is_vertically_split or is_horizontally_split:
                    merged_box = [
                        min(merged_box[0], boxB[0]),
                        min(merged_box[1], boxB[1]),
                        max(merged_box[2], boxB[2]),
                        max(merged_box[3], boxB[3])
                    ]
                    merged_conf = max(merged_conf, confB)
                    skip_indices.add(j)
                    merged = True
                    # Update variables for next iterations in the j loop
                    x1_A, y1_A, x2_A, y2_A = merged_box
                    wA = x2_A - x1_A
                    hA = y2_A - y1_A
                    areaA = wA * hA
                    
            new_dets.append((merged_box, merged_conf))
            skip_indices.add(i)
            
        current_dets = new_dets
        
    return current_dets

# Global YOLO model variables
model = None
custom_model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global model, custom_model
    
    # 1. Load base model (yolov8s.pt)
    base_s_path = os.path.join(os.path.dirname(BASE_DIR), "yolov8s.pt")
    base_n_path = "yolov8n.pt"
    
    if os.path.exists(base_s_path):
        print(f"[STARTUP] Found yolov8s.pt in root. Loading as base model: {base_s_path}")
        model = YOLO(base_s_path)
    else:
        print("[STARTUP] yolov8s.pt not found in root. Falling back to yolov8n.pt...")
        model = YOLO(base_n_path)
        
    # 2. Load custom trained model (best.pt or best.onnx)
    custom_pt_path = os.path.join(os.path.dirname(BASE_DIR), "best.pt")
    custom_onnx_path = os.path.join(os.path.dirname(BASE_DIR), "best.onnx")
    
    if os.path.exists(custom_pt_path):
        print(f"[STARTUP] Found custom trained PyTorch model at: {custom_pt_path}. Loading...")
        custom_model = YOLO(custom_pt_path)
    elif os.path.exists(custom_onnx_path):
        print(f"[STARTUP] Found custom optimized ONNX model at: {custom_onnx_path}. Loading...")
        custom_model = YOLO(custom_onnx_path, task="detect")
    else:
        print("[STARTUP] Custom trained model (best.pt / best.onnx) not found. Using base model only.")
        custom_model = None
        
    print("[STARTUP] Models loaded successfully.")
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
            person_detections = []
            other_boxes = []
            
            if custom_model is not None:
                # 1. Base model for Person (0) and Laptop (63)
                results_base = model.predict(
                    source=frame,
                    classes=[0, 63],
                    conf=conf_threshold,
                    verbose=False
                )
                for box in results_base[0].boxes:
                    coords = box.xyxy[0].tolist()
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    if cls == 0:
                        person_detections.append((coords, conf))
                    elif cls == 63:
                        other_boxes.append({
                            "coords": coords,
                            "conf": conf,
                            "cls": 63
                        })
                
                # 2. Custom model for Mobile phone (0) and Book (1)
                # Slightly higher confidence threshold (min 0.40) to prevent false alerts
                results_custom = custom_model.predict(
                    source=frame,
                    classes=[0, 1],
                    conf=max(conf_threshold, 0.40),
                    verbose=False
                )
                for box in results_custom[0].boxes:
                    coords = box.xyxy[0].tolist()
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    # Map custom class IDs to standard COCO IDs:
                    # Custom 0 (Mobile phone) -> COCO 67 (cell phone)
                    # Custom 1 (Book) -> COCO 73 (book)
                    if cls == 0:
                        mapped_cls = 67
                    elif cls == 1:
                        mapped_cls = 73
                    else:
                        continue
                    
                    other_boxes.append({
                        "coords": coords,
                        "conf": conf,
                        "cls": mapped_cls
                    })
            else:
                # Fallback to standard base model only
                target_classes = [0, 63, 67, 73]
                results = model.predict(
                    source=frame,
                    classes=target_classes,
                    conf=conf_threshold,
                    verbose=False
                )
                for box in results[0].boxes:
                    coords = box.xyxy[0].tolist()
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    if cls == 0:
                        person_detections.append((coords, conf))
                    else:
                        other_boxes.append({
                            "coords": coords,
                            "conf": conf,
                            "cls": cls
                        })
            
            # Merge fragmented/split person detections before tracking
            person_detections = merge_person_detections(person_detections)
            
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
            for item in other_boxes:
                coords = item["coords"]
                conf = item["conf"]
                cls = item["cls"]
                
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
        # Try DirectShow first on Windows to avoid backend delays or failure
        import platform
        if platform.system() == "Windows":
            camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        else:
            camera = cv2.VideoCapture(0)
            
        if not camera.isOpened():
            # Fallback to default backend if CAP_DSHOW fails
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
                    
                    boxes = results[0].boxes
                    person_detections = []
                    other_detections = []
                    
                    for box in boxes:
                        coords = box.xyxy[0].tolist()
                        conf = float(box.conf[0])
                        cls = int(box.cls[0])
                        if cls == 0:
                            person_detections.append((coords, conf))
                        else:
                            other_detections.append((coords, conf, cls))
                    
                    # Merge split person boxes
                    person_detections = merge_person_detections(person_detections)
                    
                    # Draw merged person detections
                    for coords, conf in person_detections:
                        x1, y1, x2, y2 = map(int, coords)
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 120, 0), 2)
                        cv2.putText(frame, f"Candidate: {conf:.2f}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 120, 0), 1)
                        
                    # Draw non-person detections
                    for coords, conf, cls in other_detections:
                        x1, y1, x2, y2 = map(int, coords)
                        if cls == 67:
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
