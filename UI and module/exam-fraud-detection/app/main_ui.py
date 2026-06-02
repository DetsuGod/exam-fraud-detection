import os
import json
import base64
import random
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

# Get current directory path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

print(f"[UI-ONLY] BASE_DIR: {BASE_DIR}")


print(f"[UI-ONLY] TEMPLATES_DIR: {TEMPLATES_DIR}")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("[UI-ONLY] Starting UI-only server. YOLO models are NOT loaded.")
    yield
    # Shutdown
    print("[UI-ONLY] Closing UI-only server...")

# Initialize FastAPI
app = FastAPI(
    title="AI Exam Proctoring System - UI Server",
    description="Lightweight Admin & Candidate UI without YOLOv8 dependencies",
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
    Renders the main Admin Dashboard by default.
    """
    try:
        return templates.TemplateResponse("dashboard.html", {"request": request})
    except Exception as e:
        print(f"[ROUTE ERROR] Error rendering dashboard: {e}")
        raise

@app.get("/student", response_class=HTMLResponse)
async def get_student_view(request: Request):
    """
    Renders the candidate proctoring view (original index.html).
    """
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        print(f"[ROUTE ERROR] Error rendering index: {e}")
        raise

@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """
    Mock WebSocket endpoint for streaming.
    Receives camera frame and sends back simulated YOLO detections.
    This allows the student page (index.html) to work without running the model.
    """
    await websocket.accept()
    print("[MOCK WEBSOCKET] Candidate connected.")
    
    frame_counter = 0
    try:
        while True:
            # Receive data from client
            message = await websocket.receive_text()
            data = json.loads(message)
            
            frame_data = data.get("image")
            exam_active = bool(data.get("exam_active", False))
            
            if not frame_data:
                continue
                
            frame_counter += 1
            
            # Simulate metrics
            num_persons = 1
            num_phones = 0
            num_laptops = 0
            num_books = 0
            violations = []
            suspicion_index = 0
            
            # Every once in a while, simulate a mock violation to test UI updates
            if exam_active:
                if frame_counter % 80 in range(10, 20):
                    num_phones = 1
                    violations.append("Phát hiện điện thoại!")
                    suspicion_index = 100
                elif frame_counter % 80 in range(30, 40):
                    num_persons = 0
                    violations.append("Thí sinh đã rời khỏi vị trí!")
                    suspicion_index = 90
                elif frame_counter % 80 in range(50, 58):
                    num_books = 1
                    violations.append("Phát hiện tài liệu/sách!")
                    suspicion_index = 60
            else:
                # Active proctoring but not exam
                if frame_counter % 120 in range(15, 25):
                    num_persons = 0
                    violations.append("Không có thí sinh trong khung hình!")
                    suspicion_index = 40
            
            # Build list of mock detections
            detections_log = []
            if num_persons > 0:
                detections_log.append({
                    "class": "Person (id01)",
                    "confidence": 0.88,
                    "box": [100, 80, 540, 450]
                })
            if num_phones > 0:
                detections_log.append({
                    "class": "cell phone",
                    "confidence": 0.76,
                    "box": [320, 240, 400, 360]
                })
            if num_books > 0:
                detections_log.append({
                    "class": "book",
                    "confidence": 0.65,
                    "box": [50, 350, 180, 440]
                })
            if num_laptops > 0:
                detections_log.append({
                    "class": "laptop",
                    "confidence": 0.72,
                    "box": [120, 200, 380, 400]
                })

            response_payload = {
                # Simply echo back the same frame so candidate sees their camera
                "image": frame_data,
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
            
            await websocket.send_text(json.dumps(response_payload))
            
    except WebSocketDisconnect:
        print("[MOCK WEBSOCKET] Candidate disconnected.")
    except Exception as e:
        print(f"[MOCK WEBSOCKET ERROR] {e}")
        try:
            await websocket.close()
        except:
            pass
