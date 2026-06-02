import os
import cv2
import time
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

import threading
session_lock = threading.Lock()

def get_student_classroom(student_id: str) -> str:
    if not student_id:
        return "B202"
    student_id = student_id.lower()
    # 1. Format: id<room>_<index>, e.g. idb202_1
    if student_id.startswith("id") and "_" in student_id:
        room_part = student_id.split("_")[0][2:]
        if room_part:
            return room_part.upper()
    # 2. Mock student IDs to their respective classrooms as per dashboard
    if "22520005" in student_id:
        return "B202"
    if "22520001" in student_id:
        return "A101"
    # 3. Format: <room>_<index>, e.g. b202_1
    if "_" in student_id:
        return student_id.split("_")[0].upper()
    if "-" in student_id:
        return student_id.split("-")[0].upper()
    # Fallback default
    return "B202"

def get_or_create_session_dir() -> str:
    global current_session_dir
    if current_session_dir is not None:
        return current_session_dir
        
    with session_lock:
        if current_session_dir is not None:
            return current_session_dir
            
        import datetime
        now = datetime.datetime.now()
        day_str = now.strftime("%d")
        month_str = now.strftime("%m")
        year_str = now.strftime("%Y")
        
        log_base_dir = r"D:\tài liệu\ie101\model\LOG phiên"
        os.makedirs(log_base_dir, exist_ok=True)
        
        prefix = f"ngày {day_str} tháng {month_str} năm {year_str} phiên "
        existing_folders = [d for d in os.listdir(log_base_dir) if os.path.isdir(os.path.join(log_base_dir, d)) and d.startswith(prefix)]
        
        n = len(existing_folders) + 1
        session_folder_name = f"{prefix}{n}"
        current_session_dir = os.path.join(log_base_dir, session_folder_name)
        os.makedirs(current_session_dir, exist_ok=True)
        print(f"[SESSION] Auto-initialized session folder: {current_session_dir}")
        return current_session_dir

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
        i = 1
        while f"id{i:02d}" in self.candidates:
            i += 1
        label = f"id{i:02d}"
        self.candidates[label] = centroid
        self.bboxes[label] = bbox
        self.confs[label] = conf
        self.disappeared[label] = 0
        return label

    def defragment(self):
        """
        Re-indexes the active candidates sequentially from 1 to N, sorted by their
        leftmost coordinate (x1) for a clean, professional proctoring layout.
        """
        if len(self.candidates) == 0:
            return

        # Get all current candidate labels
        labels = list(self.candidates.keys())
        
        # Sort labels by the x1 coordinate of their bounding box
        sorted_labels = sorted(labels, key=lambda l: self.bboxes[l][0])
        
        # Create temporary copies of dicts
        old_candidates = dict(self.candidates)
        old_bboxes = dict(self.bboxes)
        old_confs = dict(self.confs)
        old_disappeared = dict(self.disappeared)
        
        # Clear original dicts
        self.candidates.clear()
        self.bboxes.clear()
        self.confs.clear()
        self.disappeared.clear()
        
        # Re-register with sequential IDs 1 to N
        for idx, old_lbl in enumerate(sorted_labels):
            new_lbl = f"id{idx + 1:02d}"
            self.candidates[new_lbl] = old_candidates[old_lbl]
            self.bboxes[new_lbl] = old_bboxes[old_lbl]
            self.confs[new_lbl] = old_confs[old_lbl]
            self.disappeared[new_lbl] = old_disappeared[old_lbl]

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

class ViolationTracker:
    def __init__(self, max_disappeared=25, min_hits=5, iou_threshold=0.10, distance_threshold=350):
        self.next_id = 1
        self.objects = {}       # id (int) -> { "bbox": [x1, y1, x2, y2], "conf": float, "cls": int, "disappeared": int, "hits": int }
        self.max_disappeared = max_disappeared
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.distance_threshold = distance_threshold

    def compute_iou(self, boxA, boxB):
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])
        interArea = max(0, xB - xA) * max(0, yB - yA)
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        return interArea / float(boxAArea + boxBArea - interArea + 1e-6)

    def update(self, rects_with_confs_and_classes):
        # rects_with_confs_and_classes: list of ([x1, y1, x2, y2], conf, cls)
        if len(rects_with_confs_and_classes) == 0:
            for obj_id in list(self.objects.keys()):
                self.objects[obj_id]["disappeared"] += 1
                if self.objects[obj_id]["disappeared"] > self.max_disappeared:
                    del self.objects[obj_id]
            return self.get_tracked_objects()

        # Compute centroids for new detections
        input_centroids = []
        for (bbox, conf, cls) in rects_with_confs_and_classes:
            cX = int((bbox[0] + bbox[2]) / 2.0)
            cY = int((bbox[1] + bbox[3]) / 2.0)
            input_centroids.append((cX, cY))

        # Generate centroids for existing objects
        existing_centroids = {}
        for obj_id, obj in self.objects.items():
            bbox = obj["bbox"]
            cX = int((bbox[0] + bbox[2]) / 2.0)
            cY = int((bbox[1] + bbox[3]) / 2.0)
            existing_centroids[obj_id] = (cX, cY)

        matched_detections = set()
        matched_objects = set()

        # 1. Match greedily by IoU first
        for obj_id, obj in self.objects.items():
            best_iou = 0
            best_idx = -1
            for idx, (bbox, conf, cls) in enumerate(rects_with_confs_and_classes):
                if idx in matched_detections:
                    continue
                if cls != obj["cls"]:
                    continue
                iou = self.compute_iou(obj["bbox"], bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_idx = idx
            
            if best_iou > self.iou_threshold:
                self.update_object(obj_id, rects_with_confs_and_classes[best_idx])
                matched_detections.add(best_idx)
                matched_objects.add(obj_id)

        # 2. For unmatched objects, try matching by Centroid Distance
        for obj_id, obj in self.objects.items():
            if obj_id in matched_objects:
                continue
            
            best_dist = float("inf")
            best_idx = -1
            c_old = existing_centroids[obj_id]
            
            for idx, (bbox, conf, cls) in enumerate(rects_with_confs_and_classes):
                if idx in matched_detections:
                    continue
                if cls != obj["cls"]:
                    continue
                c_new = input_centroids[idx]
                dist = math.sqrt((c_old[0] - c_new[0])**2 + (c_old[1] - c_new[1])**2)
                if dist < best_dist:
                    best_dist = dist
                    best_idx = idx
            
            # Match if centroid distance is within pixel radius (increased threshold to handle fast movements)
            if best_dist < self.distance_threshold:
                self.update_object(obj_id, rects_with_confs_and_classes[best_idx])
                matched_detections.add(best_idx)
                matched_objects.add(obj_id)

        # Increment disappeared for unmatched existing objects
        for obj_id in list(self.objects.keys()):
            if obj_id not in matched_objects:
                self.objects[obj_id]["disappeared"] += 1
                if self.objects[obj_id]["disappeared"] > self.max_disappeared:
                    del self.objects[obj_id]

        # Register new objects for unmatched detections
        for idx, (bbox, conf, cls) in enumerate(rects_with_confs_and_classes):
            if idx not in matched_detections:
                self.objects[self.next_id] = {
                    "bbox": bbox,
                    "conf": conf,
                    "cls": cls,
                    "disappeared": 0,
                    "hits": 1
                }
                self.next_id += 1

        return self.get_tracked_objects()

    def update_object(self, obj_id, detection):
        bbox, conf, cls = detection
        prev_bbox = self.objects[obj_id]["bbox"]
        
        # Calculate centroid distance between previous box and new detection
        c_old = (int((prev_bbox[0] + prev_bbox[2]) / 2.0), int((prev_bbox[1] + prev_bbox[3]) / 2.0))
        c_new = (int((bbox[0] + bbox[2]) / 2.0), int((bbox[1] + bbox[3]) / 2.0))
        dist = math.sqrt((c_old[0] - c_new[0])**2 + (c_old[1] - c_new[1])**2)
        
        # Adaptive smoothing factor: instant snap on rapid movement (>80px), smooth on stationary jitter
        if dist > 80:
            alpha = 1.0
        else:
            alpha = 0.8
            
        smoothed_bbox = [
            alpha * bbox[0] + (1 - alpha) * prev_bbox[0],
            alpha * bbox[1] + (1 - alpha) * prev_bbox[1],
            alpha * bbox[2] + (1 - alpha) * prev_bbox[2],
            alpha * bbox[3] + (1 - alpha) * prev_bbox[3]
        ]
        self.objects[obj_id]["bbox"] = smoothed_bbox
        self.objects[obj_id]["conf"] = max(self.objects[obj_id]["conf"] * 0.2 + conf * 0.8, conf)
        self.objects[obj_id]["disappeared"] = 0
        self.objects[obj_id]["hits"] += 1

    def get_tracked_objects(self, active_only=True):
        return [
            {
                "coords": obj["bbox"],
                "conf": obj["conf"],
                "cls": obj["cls"],
                "id": obj_id
            }
            for obj_id, obj in self.objects.items()
            if (not active_only or obj["disappeared"] <= 8) and obj["hits"] >= self.min_hits
        ]

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

def apply_violation_nms(violations, iou_threshold=0.35, containment_threshold=0.55):
    """
    Applies Non-Maximum Suppression (NMS) to violation detections of the same class.
    violations: list of tuples (coords, conf, cls)
    """
    if len(violations) < 2:
        return violations

    # Sort violations by confidence descending
    violations = sorted(violations, key=lambda x: x[1], reverse=True)
    keep = []

    def compute_iou(boxA, boxB):
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])
        interArea = max(0, xB - xA) * max(0, yB - yA)
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        iou = interArea / float(boxAArea + boxBArea - interArea + 1e-6)
        containmentA = interArea / float(boxAArea + 1e-6)
        containmentB = interArea / float(boxBArea + 1e-6)
        return iou, max(containmentA, containmentB)

    while len(violations) > 0:
        curr = violations.pop(0)
        keep.append(curr)
        
        remaining = []
        for item in violations:
            if item[2] == curr[2]:  # same class
                iou, max_contain = compute_iou(curr[0], item[0])
                if iou > iou_threshold or max_contain > containment_threshold:
                    continue
            remaining.append(item)
        violations = remaining

    return keep

def resolve_cross_class_overlaps(violations, iou_threshold=0.55, containment_threshold=0.80):
    """
    Resolves overlapping boxes between different violation classes (e.g. Phone vs Laptop).
    If a phone and a laptop box have a high IoU (e.g. > 0.55), they are likely a duplicate detection 
    of the same object. We keep the one with the higher confidence score.
    Also, if a laptop is completely contained within a phone box, it is a false detection of the phone.
    """
    if len(violations) < 2:
        return violations

    # Sort violations to prioritize class 2 (casio) over class 67/63/73
    # We can do this by adding 10.0 to the sorting key of class 2 so it is evaluated first
    violations = sorted(violations, key=lambda x: x[1] + 10.0 if x[2] == 2 else x[1], reverse=True)
    keep = []

    def compute_iou_and_containment(boxA, boxB):
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])
        interArea = max(0, xB - xA) * max(0, yB - yA)
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        iou = interArea / float(boxAArea + boxBArea - interArea + 1e-6)
        containmentA = interArea / float(boxAArea + 1e-6)
        containmentB = interArea / float(boxBArea + 1e-6)
        return iou, containmentA, containmentB

    while len(violations) > 0:
        curr = violations.pop(0)
        curr_box, curr_conf, curr_cls = curr
        should_suppress = False

        for kept_box, kept_conf, kept_cls in keep:
            if curr_cls != kept_cls:
                iou, cont_curr, cont_kept = compute_iou_and_containment(curr_box, kept_box)

                # 1. High IoU overlap between different classes -> keep the one with higher confidence
                if iou > iou_threshold:
                    should_suppress = True
                    break

                # 2. Geometric containment anomaly: laptop (63) inside a phone (67) box is impossible,
                # so if the laptop is inside the phone box, suppress the phone box.
                if curr_cls == 67 and kept_cls == 63 and cont_kept > containment_threshold:
                    should_suppress = True
                    break
                if curr_cls == 63 and kept_cls == 67 and cont_curr > containment_threshold:
                    should_suppress = True
                    break

        if not should_suppress:
            keep.append(curr)

    return keep

# Global YOLO model and Haar Cascade variables
model = None
custom_model = None
face_cascade = None
eye_cascade = None
profile_cascade = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global model, custom_model, face_cascade, eye_cascade, profile_cascade
    
    # 1. Load base model (yolov8n.pt) - Normal, lightweight CPU model
    print("[STARTUP] Loading normal base model (yolov8n.pt)...")
    model = YOLO("yolov8n.pt")
        
    # 2. Load custom trained model (best.pt)
    custom_pt_path = os.path.join(os.path.dirname(BASE_DIR), "best.pt")
    
    if os.path.exists(custom_pt_path):
        print(f"[STARTUP] Found custom trained PyTorch model at: {custom_pt_path}. Loading PyTorch...")
        custom_model = YOLO(custom_pt_path)
    else:
        print("[STARTUP] Custom trained model ('best.pt') not found. Using base model only.")
        custom_model = None
        
    # 3. Load Haar Cascade files from a safe ASCII directory (to prevent OpenCV Unicode path bug on Windows)
    try:
        import tempfile
        import shutil
        
        src_dir = cv2.data.haarcascades
        temp_dir = os.path.join(tempfile.gettempdir(), "ai_exam_proctoring_cascades")
        os.makedirs(temp_dir, exist_ok=True)
        
        files_to_copy = [
            "haarcascade_frontalface_default.xml",
            "haarcascade_eye.xml",
            "haarcascade_profileface.xml"
        ]
        
        loaded_paths = {}
        for filename in files_to_copy:
            src_path = os.path.join(src_dir, filename)
            dest_path = os.path.join(temp_dir, filename)
            
            # Copy file using Python's built-in file support (handles unicode perfectly)
            if os.path.exists(src_path):
                shutil.copy2(src_path, dest_path)
                loaded_paths[filename] = dest_path
            else:
                # If not found in cv2.data.haarcascades, fall back to dest_path if it already exists
                loaded_paths[filename] = dest_path if os.path.exists(dest_path) else src_path
                
        face_cascade = cv2.CascadeClassifier(loaded_paths.get("haarcascade_frontalface_default.xml"))
        eye_cascade = cv2.CascadeClassifier(loaded_paths.get("haarcascade_eye.xml"))
        profile_cascade = cv2.CascadeClassifier(loaded_paths.get("haarcascade_profileface.xml"))
        
        if face_cascade.empty() or eye_cascade.empty() or profile_cascade.empty():
            print("[STARTUP WARNING] One or more Haar Cascades failed to load (empty). Falling back to direct load...")
            # Fallback to direct load
            face_cascade = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml"))
            eye_cascade = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_eye.xml"))
            profile_cascade = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_profileface.xml"))
        else:
            print("[STARTUP] Haar Cascades loaded successfully from safe temp path.")
    except Exception as e:
        print(f"[STARTUP ERROR] Failed to copy/load Haar Cascades safely: {e}")
        # Final fallback
        try:
            face_cascade = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml"))
            eye_cascade = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_eye.xml"))
            profile_cascade = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_profileface.xml"))
            print("[STARTUP] Haar Cascades loaded via fallback direct path.")
        except Exception as fallback_err:
            print(f"[STARTUP CRITICAL] Haar Cascade direct fallback failed: {fallback_err}")
        
    print("[STARTUP] Models loaded successfully.")
    
    # Print LAN access links dynamically
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # We use a dummy UDP connection to google DNS to find the machine's primary local IP address
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"
        
    print("\n" + "="*58)
    print("                [LAN MODE IS ACTIVE]")
    print("="*58)
    print(" Other devices in the same LAN can access via:")
    print(f" 1. Dashboard Admin:  https://{local_ip}:8001/")
    print(f" 2. Exam Page:        https://{local_ip}:8001/exam")
    print("="*58 + "\n")

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

# Mount static assets for the React Exam Screen
EXAM_ASSETS_DIR = "D:/tài liệu/ie101/model/UI and module/Exam screen/dist/assets"
if os.path.exists(EXAM_ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=EXAM_ASSETS_DIR), name="exam_assets")
    print(f"[INIT] Mounted React Exam Screen assets from: {EXAM_ASSETS_DIR}")
else:
    print(f"[WARN] React Exam Screen assets directory not found: {EXAM_ASSETS_DIR}")

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """
    Renders the multi-candidate admin proctoring dashboard.
    """
    try:
        print("[ROUTE] Accessing Admin Dashboard...")
        template = templates.get_template("dashboard.html")
        content = template.render(request=request)
        print("[ROUTE] Admin Dashboard rendered successfully")
        return content
    except Exception as e:
        print(f"[ROUTE ERROR] Error rendering admin template: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise

@app.get("/dashboard", response_class=HTMLResponse)
async def get_admin_dashboard(request: Request):
    """
    Alternative route for multi-candidate admin proctoring dashboard.
    """
    return await get_dashboard(request)

@app.get("/exam", response_class=HTMLResponse)
async def get_exam_dashboard(request: Request):
    """
    Serves the newly integrated React Exam Screen application.
    """
    try:
        print("[ROUTE] Accessing Exam Page...")
        exam_html_path = "D:/tài liệu/ie101/model/UI and module/Exam screen/dist/index.html"
        if os.path.exists(exam_html_path):
            with open(exam_html_path, "r", encoding="utf-8") as f:
                content = f.read()
            print("[ROUTE] Exam HTML rendered successfully from React build")
            return HTMLResponse(content=content)
        else:
            return HTMLResponse(content="<h1>Error: Exam page build not found. Please run 'npm run build' inside 'UI and module/Exam screen'.</h1>", status_code=404)
    except Exception as e:
        print(f"[ROUTE ERROR] Error rendering exam page: {type(e).__name__}: {e}")
        return HTMLResponse(content=f"<h1>Internal Server Error: {e}</h1>", status_code=500)

from fastapi.responses import FileResponse

@app.get("/favicon.svg", include_in_schema=False)
async def get_favicon():
    favicon_path = "D:/tài liệu/ie101/model/UI and module/Exam screen/dist/favicon.svg"
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    return HTMLResponse(status_code=404)

@app.get("/icons.svg", include_in_schema=False)
async def get_icons():
    icons_path = "D:/tài liệu/ie101/model/UI and module/Exam screen/dist/icons.svg"
    if os.path.exists(icons_path):
        return FileResponse(icons_path)
    return HTMLResponse(status_code=404)

# React Exam Screen state storage
exam_student_connections = {}
exam_admin_connections = set()
student_screens = {}
current_session_dir = None
pending_exam_violations = {}

class StudentWebcamProctorState:
    def __init__(self):
        self.out_of_frame_frames = 0
        self.head_turn_frames = 0
        self.glance_frames = 0
        self.head_turn_start_time = None
        self.last_profile_detected_time = None
        self.glance_start_time = None
        self.out_of_frame_start_time = None
        self.last_glance_detected_time = None
        self.last_screenshot_time = 0

student_proctor_states = {}


@app.websocket("/ws/exam")
async def websocket_exam(websocket: WebSocket):
    global current_session_dir, pending_exam_violations
    role = websocket.query_params.get("role", "student")
    await websocket.accept()
    
    if role == "admin":
        exam_admin_connections.add(websocket)
        print("[WS EXAM] Admin connected")
    else:
        print("[WS EXAM] Student connected")
        
    student_id = None
    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            
            # Keep track of which student is connected
            if "student_id" in data and data["student_id"]:
                student_id = data["student_id"].lower()
                exam_student_connections[student_id] = websocket
                
            event_type = data.get("event_type")
            image = data.get("image")
            
            if event_type == "stream_frame" and student_id:
                if student_id not in student_proctor_states:
                    student_proctor_states[student_id] = StudentWebcamProctorState()
                
                state = student_proctor_states[student_id]
                webcam_img = data.get("image")
                screen_img = data.get("screen_image")
                
                annotated_base64 = ""
                metrics = {
                    "suspicion_index": 0,
                    "violations": [],
                    "num_persons": 0,
                    "num_phones": 0,
                    "num_laptops": 0,
                    "num_books": 0
                }
                
                if webcam_img:
                    try:
                        header, encoded = webcam_img.split(",", 1)
                        image_bytes = base64.b64decode(encoded)
                        img_np = np.frombuffer(image_bytes, dtype=np.uint8)
                        frame = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
                        
                        if frame is not None:
                            h, w, _ = frame.shape
                            current_time = time.time()
                            
                            violations = []
                            num_persons = 0
                            num_phones = 0
                            num_laptops = 0
                            num_books = 0
                            
                            # Grayscale for Haar Cascade detection
                            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                            gray = cv2.equalizeHist(gray)
                            
                            # Detect frontal faces
                            faces = []
                            profile_detected = False
                            
                            if face_cascade is not None:
                                faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60))
                                
                            if len(faces) == 0 and profile_cascade is not None:
                                profiles = profile_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60))
                                if len(profiles) > 0:
                                    profile_detected = True
                                    faces = profiles
                            
                            if len(faces) == 0:
                                state.out_of_frame_frames += 1
                                state.glance_frames = max(0, state.glance_frames - 1)
                                state.head_turn_frames = max(0, state.head_turn_frames - 1)
                                state.head_turn_start_time = None
                                state.last_profile_detected_time = None
                                state.glance_start_time = None
                                state.last_glance_detected_time = None
                                if state.out_of_frame_start_time is None:
                                    state.out_of_frame_start_time = current_time
                            else:
                                state.out_of_frame_frames = 0
                                state.out_of_frame_start_time = None
                                
                                fx, fy, fw, fh = faces[0]
                                
                                COLOR_FACE = (16, 185, 129) if not profile_detected else (0, 140, 255)
                                cv2.rectangle(frame, (fx, fy), (fx+fw, fy+fh), COLOR_FACE, 1)
                                
                                if profile_detected:
                                    state.head_turn_frames += 1
                                    state.glance_frames = max(0, state.glance_frames - 1)
                                    state.glance_start_time = None
                                    state.last_glance_detected_time = None
                                    
                                    state.last_profile_detected_time = current_time
                                    if state.head_turn_start_time is None:
                                        state.head_turn_start_time = current_time
                                    
                                    elapsed = current_time - state.head_turn_start_time
                                    if elapsed > 3.0:
                                        violations.append("Thí sinh quay đầu sang hai bên!")
                                else:
                                    state.head_turn_frames = max(0, state.head_turn_frames - 1)
                                    if state.head_turn_start_time is not None:
                                        if state.last_profile_detected_time is not None and (current_time - state.last_profile_detected_time > 1.0):
                                            state.head_turn_start_time = None
                                            state.last_profile_detected_time = None
                                    
                                    roi_gray = gray[fy:fy+fh, fx:fx+fw]
                                    eyes = []
                                    if eye_cascade is not None:
                                        eyes = eye_cascade.detectMultiScale(roi_gray, scaleFactor=1.1, minNeighbors=4, minSize=(15, 15))
                                    
                                    for (ex, ey, ew, eh) in eyes:
                                        ecX = fx + ex + ew // 2
                                        ecY = fy + ey + eh // 2
                                        cv2.circle(frame, (ecX, ecY), min(ew, eh) // 2, (241, 102, 99), 1)
                                        cv2.circle(frame, (ecX, ecY), 2, (255, 255, 255), -1)
                                    
                                    if len(eyes) < 2:
                                        state.glance_frames += 1
                                        state.last_glance_detected_time = current_time
                                        if state.glance_start_time is None:
                                            state.glance_start_time = current_time
                                        
                                        elapsed = current_time - state.glance_start_time
                                        if elapsed > 3.0:
                                            violations.append("Thí sinh liếc mắt / nhìn ra ngoài!")
                                    else:
                                        state.glance_frames = max(0, state.glance_frames - 2)
                                        if state.glance_start_time is not None:
                                            if state.last_glance_detected_time is not None and (current_time - state.last_glance_detected_time > 1.0):
                                                state.glance_start_time = None
                                                state.last_glance_detected_time = None
                                                
                            # Run YOLOv8 for smart devices
                            raw_violations = []
                            if custom_model is not None:
                                results_base = model.predict(source=frame, classes=[67, 73], conf=0.35, verbose=False, imgsz=480)
                                for box in results_base[0].boxes:
                                    coords = box.xyxy[0].tolist()
                                    conf = float(box.conf[0])
                                    cls = int(box.cls[0])
                                    if cls == 67:
                                        if conf < 0.45: continue
                                        if (coords[2] - coords[0]) > 350 or (coords[3] - coords[1]) > 350: continue
                                    
                                    is_face_fp = False
                                    for (fx, fy, fw, fh) in faces:
                                        xA, yA = max(fx, coords[0]), max(fy, coords[1])
                                        xB, yB = min(fx + fw, coords[2]), min(fy + fh, coords[3])
                                        inter = max(0, xB - xA) * max(0, yB - yA)
                                        area = (coords[2] - coords[0]) * (coords[3] - coords[1])
                                        if inter / float(area + 1e-6) > 0.55:
                                            is_face_fp = True
                                            break
                                    if is_face_fp: continue
                                    raw_violations.append((coords, conf, cls))
                                    
                                results_custom = custom_model.predict(source=frame, classes=[0, 1, 2], conf=0.35, verbose=False, imgsz=512)
                                for box in results_custom[0].boxes:
                                    coords = box.xyxy[0].tolist()
                                    conf = float(box.conf[0])
                                    cls = int(box.cls[0])
                                    mapped_cls = 67 if cls == 0 else (73 if cls == 1 else 2)
                                    if mapped_cls == 67:
                                        if conf < 0.45: continue
                                        if (coords[2] - coords[0]) > 350 or (coords[3] - coords[1]) > 350: continue
                                    
                                    is_face_fp = False
                                    for (fx, fy, fw, fh) in faces:
                                        xA, yA = max(fx, coords[0]), max(fy, coords[1])
                                        xB, yB = min(fx + fw, coords[2]), min(fy + fh, coords[3])
                                        inter = max(0, xB - xA) * max(0, yB - yA)
                                        area = (coords[2] - coords[0]) * (coords[3] - coords[1])
                                        if inter / float(area + 1e-6) > 0.55:
                                            is_face_fp = True
                                            break
                                    if is_face_fp: continue
                                    raw_violations.append((coords, conf, mapped_cls))
                            
                            kept_violations = resolve_cross_class_overlaps(raw_violations)
                            for coords, conf, cls in kept_violations:
                                if cls == 67:
                                    num_phones += 1
                                    violations.append("Phát hiện sử dụng thiết bị cấm (Điện thoại).")
                                    color = (68, 68, 239)
                                elif cls == 73:
                                    num_books += 1
                                    violations.append("Phát hiện sử dụng tài liệu / sách giấy.")
                                    color = (68, 68, 239)
                                elif cls == 2:
                                    # Still detect Casio but no warning alert added to violations
                                    color = (16, 185, 129)
                                else:
                                    color = (68, 68, 239)
                                
                                cv2.rectangle(frame, (int(coords[0]), int(coords[1])), (int(coords[2]), int(coords[3])), color, 2)
                            
                            suspicion_index = 0
                            if num_phones > 0:
                                suspicion_index = 95
                            elif state.out_of_frame_frames > 25:
                                suspicion_index = 85
                                violations.append("Thí sinh rời khỏi vị trí làm bài!")
                            elif state.head_turn_frames > 15:
                                suspicion_index = 75
                            elif state.glance_frames > 15:
                                suspicion_index = 50
                            elif num_books > 0:
                                suspicion_index = 45
                            
                            sid_low = student_id.lower()
                            if sid_low in pending_exam_violations and pending_exam_violations[sid_low]:
                                for v_item in pending_exam_violations[sid_low]:
                                    violations.append(f"EXAM_ALERT: {v_item['message']}")
                                pending_exam_violations[sid_low] = []
                            
                            _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 55])
                            annotated_base64 = "data:image/jpeg;base64," + base64.b64encode(buffer).decode("utf-8")
                            
                            metrics = {
                                "suspicion_index": int(suspicion_index),
                                "violations": list(set(violations)),
                                "num_persons": int(len(faces)),
                                "num_phones": int(num_phones),
                                "num_laptops": int(num_laptops),
                                "num_books": int(num_books)
                            }
                            
                            # Save webcam screenshot for camera violations
                            camera_violations = [v for v in violations if not v.startswith("EXAM_ALERT:")]
                            if len(camera_violations) > 0 and current_time - state.last_screenshot_time > 5.0:
                                try:
                                    session_dir = get_or_create_session_dir()
                                    classroom = get_student_classroom(student_id)
                                    camera_save_dir = os.path.join(session_dir, classroom, student_id, "Camera")
                                    os.makedirs(camera_save_dir, exist_ok=True)
                                    
                                    import datetime
                                    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                                    filename = f"{student_id}_{now_str}.jpg"
                                    save_path = os.path.join(camera_save_dir, filename)
                                    
                                    ret_val, img_encoded = cv2.imencode('.jpg', frame)
                                    if ret_val:
                                        with open(save_path, "wb") as f_img:
                                            f_img.write(img_encoded.tobytes())
                                        print(f"[SCREENSHOT CAMERA] Saved webcam violation proof for {student_id}: {save_path}")
                                        state.last_screenshot_time = current_time
                                except Exception as e_save:
                                    print(f"[SCREENSHOT CAMERA ERROR] Failed to save webcam proof: {e_save}")
                    except Exception as ex_ai:
                        print(f"[WS EXAM AI ERROR] Failed to process webcam stream for {student_id}: {ex_ai}")
                        annotated_base64 = webcam_img
                
                admin_payload = {
                    "event_type": "stream_frame",
                    "student_id": student_id,
                    "image": annotated_base64,
                    "screen_image": screen_img,
                    "metrics": metrics
                }
                admin_message = json.dumps(admin_payload)
                for admin_ws in list(exam_admin_connections):
                    try:
                        await admin_ws.send_text(admin_message)
                    except:
                        exam_admin_connections.discard(admin_ws)
                continue
            
            # If student is sharing their screen, save the screenshot frame
            if image and student_id:
                student_screens[student_id] = image
                
            # Log and handle exam violations
            if event_type in ["BLUR", "VISIBILITY_CHANGE", "COPY_DETECTED", "SCREEN_SHARE_STOPPED"]:
                msg = ""
                if event_type == "BLUR":
                    msg = "Thí sinh chuyển tab hoặc rời khỏi trang làm bài!"
                elif event_type == "VISIBILITY_CHANGE":
                    msg = "Thí sinh ẩn màn hình bài thi!"
                elif event_type == "COPY_DETECTED":
                    msg = "Thí sinh sao chép nội dung bài thi!"
                elif event_type == "SCREEN_SHARE_STOPPED":
                    msg = "CẢNH BÁO: Thí sinh dừng chia sẻ màn hình làm bài!"
                
                if student_id and msg:
                    sid = student_id.lower()
                    if sid not in pending_exam_violations:
                        pending_exam_violations[sid] = []
                    pending_exam_violations[sid].append({
                        "event_type": event_type,
                        "message": msg
                    })
                    
                    other_sid = sid[2:] if sid.startswith("id") else f"id{sid}"
                    if other_sid not in pending_exam_violations:
                        pending_exam_violations[other_sid] = []
                    pending_exam_violations[other_sid].append({
                        "event_type": event_type,
                        "message": msg
                    })
                    print(f"[WS EXAM VIOLATION] Queued exam violation for {student_id}: {msg}")
                    
                    # Save screenshot of exam violation to D:\tài liệu\ie101\model\LOG phiên\<session_folder>\<classroom>\<student_id>\Exam
                    if image:
                        try:
                            session_dir = get_or_create_session_dir()
                            classroom = get_student_classroom(student_id)
                            exam_save_dir = os.path.join(session_dir, classroom, student_id, "Exam")
                            os.makedirs(exam_save_dir, exist_ok=True)
                            
                            import datetime
                            now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"{student_id}_{event_type}_{now_str}.jpg"
                            exam_save_path = os.path.join(exam_save_dir, filename)
                            
                            if "," in image:
                                _, encoded = image.split(",", 1)
                            else:
                                encoded = image
                            
                            img_bytes = base64.b64decode(encoded)
                            with open(exam_save_path, "wb") as f_img:
                                f_img.write(img_bytes)
                            print(f"[SCREENSHOT EXAM] Saved exam violation proof for {student_id}: {exam_save_path}")
                        except Exception as e:
                            print(f"[SCREENSHOT EXAM ERROR] Failed to save exam violation proof: {e}")
            
            # Broadcast to all connected admins of the React Exam app
            for admin_ws in list(exam_admin_connections):
                try:
                    await admin_ws.send_text(message)
                except:
                    exam_admin_connections.discard(admin_ws)
                    
    except WebSocketDisconnect:
        print(f"[WS EXAM] Disconnected role={role}, student_id={student_id}")
    finally:
        if role == "admin":
            exam_admin_connections.discard(websocket)
        elif student_id:
            exam_student_connections.pop(student_id, None)

@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time video stream from the browser.
    Receives base64 encoded frames or binary image data, processes with YOLOv8,
    and returns detected objects, alerts, statistics, and the annotated frame.
    """
    global current_session_dir, pending_exam_violations
    await websocket.accept()
    print("[WEBSOCKET] Client connected for streaming.")
    
    tracker = CandidateTracker(max_disappeared=20, distance_threshold=200)
    violation_tracker = ViolationTracker(max_disappeared=5)
    session_active = False
    initial_candidates = {}
    
    # State counters for Webcam Mode (cumulative temporal filters to avoid jitter)
    out_of_frame_frames = 0
    head_turn_frames = 0
    glance_frames = 0
    
    # Time trackers for head turning
    head_turn_start_time = None
    last_profile_detected_time = None
    
    # Time trackers for eye glancing
    glance_start_time = None
    
    # Time trackers for out of frame
    out_of_frame_start_time = None
    last_glance_detected_time = None
    
    # Cooldown tracking for saving violation screenshots during exam sessions
    last_screenshot_time = 0
    exam_session_active = False
    
    try:
        while True:
            # Receive data from client
            message = await websocket.receive_text()
            data = json.loads(message)
            
            # Extract frame data (base64 string) and settings
            frame_data = data.get("image") # format: data:image/jpeg;base64,...
            conf_threshold = float(data.get("threshold") or 0.35)
            max_disappeared_time = float(data.get("max_disappeared_time") or 3.0)
            look_away_time = float(data.get("look_away_time") or 3.0)
            gaze_ratio = float(data.get("gaze_ratio") or 0.85)
            face_conf = float(data.get("face_conf") or 0.70)
            exam_active = bool(data.get("exam_active", False))
            monitoring_mode = data.get("monitoring_mode", "cctv")
            student_id = data.get("student_id")
            
            # Track exam session state transition to create new session directory
            if exam_active:
                if not exam_session_active:
                    exam_session_active = True
                    try:
                        get_or_create_session_dir()
                    except Exception as e:
                        print(f"[SESSION ERROR] Failed to create session folder: {e}")
            else:
                exam_session_active = False
                current_session_dir = None
            
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
            current_time = time.time()
            
            violations = []
            detections_log = []
            num_persons = 0
            num_phones = 0
            num_laptops = 0
            num_books = 0
            
            # Bounding box drawing styles (BGR colors)
            COLOR_PERSON = (255, 120, 0)    # Electric Blue-ish
            COLOR_PHONE = (68, 68, 239)     # Crimson Red
            COLOR_VIOLATION = (0, 140, 255)  # Warning Orange
            
            if monitoring_mode == "webcam":
                # ==========================================
                # DIRECTION 2: WEBCAM MODE (Personal Proctoring)
                # ==========================================
                
                # Grayscale for Haar Cascade detection
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.equalizeHist(gray) # Improve contrast dynamically
                
                # Detect frontal faces
                faces = []
                profile_detected = False
                
                if face_cascade is not None:
                    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(60, 60))
                    
                if len(faces) == 0 and profile_cascade is not None:
                    # No frontal face found, try profile face (sideways head turning)
                    profiles = profile_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(60, 60))
                    if len(profiles) > 0:
                        profile_detected = True
                        faces = profiles
                
                if len(faces) == 0:
                    # No candidate visible in frame
                    out_of_frame_frames += 1
                    glance_frames = max(0, glance_frames - 1)
                    head_turn_frames = max(0, head_turn_frames - 1)
                    head_turn_start_time = None
                    last_profile_detected_time = None
                    glance_start_time = None
                    last_glance_detected_time = None
                    if out_of_frame_start_time is None:
                        out_of_frame_start_time = current_time
                else:
                    out_of_frame_frames = 0
                    out_of_frame_start_time = None
                    
                    # We have a candidate, focus on the primary face
                    fx, fy, fw, fh = faces[0]
                    
                    # Sci-fi corner-only reticle overlay for a premium tech feel
                    COLOR_FACE = (16, 185, 129) if not profile_detected else (0, 140, 255) # Green vs Orange
                    length = 15
                    cv2.rectangle(frame, (fx, fy), (fx+fw, fy+fh), COLOR_FACE, 1)
                    # Top-Left corner
                    cv2.line(frame, (fx, fy), (fx + length, fy), COLOR_FACE, 2)
                    cv2.line(frame, (fx, fy), (fx, fy + length), COLOR_FACE, 2)
                    # Top-Right corner
                    cv2.line(frame, (fx+fw, fy), (fx+fw - length, fy), COLOR_FACE, 2)
                    cv2.line(frame, (fx+fw, fy), (fx+fw, fy + length), COLOR_FACE, 2)
                    # Bottom-Left corner
                    cv2.line(frame, (fx, fy+fh), (fx + length, fy+fh), COLOR_FACE, 2)
                    cv2.line(frame, (fx, fy+fh), (fx, fy+fh - length), COLOR_FACE, 2)
                    # Bottom-Right corner
                    cv2.line(frame, (fx+fw, fy+fh), (fx+fw - length, fy+fh), COLOR_FACE, 2)
                    cv2.line(frame, (fx+fw, fy+fh), (fx+fw, fy+fh - length), COLOR_FACE, 2)
                    
                    current_time = time.time()
                    if profile_detected:
                        # Sideways head turn registered
                        head_turn_frames += 1
                        glance_frames = max(0, glance_frames - 1) # Slowly decay glance frames when head is turned
                        
                        # Reset glance timers when head is turned sideways
                        glance_start_time = None
                        last_glance_detected_time = None
                        
                        last_profile_detected_time = current_time
                        if head_turn_start_time is None:
                            head_turn_start_time = current_time
                        
                        elapsed_time = current_time - head_turn_start_time
                        if elapsed_time > look_away_time:
                            violations.append("Thí sinh quay đầu sang hai bên!")
                    else:
                        head_turn_frames = max(0, head_turn_frames - 1) # Slowly decay head turn
                        
                        # Grace period of 1.0 second: only reset if no profile is detected for > 1.0s
                        if head_turn_start_time is not None:
                            if last_profile_detected_time is not None and (current_time - last_profile_detected_time > 1.0):
                                head_turn_start_time = None
                                last_profile_detected_time = None
                        
                        # Frontal face -> Check eye presence to detect glances
                        roi_gray = gray[fy:fy+fh, fx:fx+fw]
                        eyes = []
                        if eye_cascade is not None:
                            eyes = eye_cascade.detectMultiScale(roi_gray, scaleFactor=1.1, minNeighbors=3, minSize=(15, 15))
                        
                        # Draw blue sci-fi target circles on eyes
                        for (ex, ey, ew, eh) in eyes:
                            ecX = fx + ex + ew // 2
                            ecY = fy + ey + eh // 2
                            cv2.circle(frame, (ecX, ecY), min(ew, eh) // 2, (241, 102, 99), 1) # Indigo outer circle
                            cv2.circle(frame, (ecX, ecY), 2, (255, 255, 255), -1) # White center pupil
                        
                        if len(eyes) < 2:
                            # Glancing away or eyes obscured
                            glance_frames += 1
                            
                            last_glance_detected_time = current_time
                            if glance_start_time is None:
                                glance_start_time = current_time
                            
                            elapsed_time = current_time - glance_start_time
                            if elapsed_time > look_away_time:
                                violations.append("Thí sinh liếc mắt / nhìn ra ngoài!")
                        else:
                            glance_frames = max(0, glance_frames - 2) # Slowly recover
                            
                            # Grace period of 1.0 second: only reset if eyes are detected (not glancing) for > 1.0s
                            if glance_start_time is not None:
                                if last_glance_detected_time is not None and (current_time - last_glance_detected_time > 1.0):
                                    glance_start_time = None
                                    last_glance_detected_time = None
                            
                # Run YOLOv8 for violations (smart devices, laptops, books)
                raw_violations = []
                if custom_model is not None:
                    # Base model for Cell Phone (67), Book (73)
                    results_base = model.predict(source=frame, classes=[67, 73], conf=conf_threshold, verbose=False, imgsz=480)
                    for box in results_base[0].boxes:
                        coords = box.xyxy[0].tolist()
                        conf = float(box.conf[0])
                        cls = int(box.cls[0])
                        if cls == 63:
                            continue
                        print(f"[WEBCAM BASE DETECT] cls: {cls}, conf: {conf:.2f}, size: {int(coords[2]-coords[0])}x{int(coords[3]-coords[1])}")
                        if cls == 67:
                            # Double-shield filter: Cell phones must have higher confidence to prevent false alarms in Webcam mode
                            min_phone_conf = max(conf_threshold + 0.10, 0.45)
                            if conf < min_phone_conf:
                                continue
                            p_w = coords[2] - coords[0]
                            p_h = coords[3] - coords[1]
                            if p_w > 350 or p_h > 350:
                                continue
                        
                        # Suppress face misdetection as a phone/violation in Webcam mode
                        is_face_fp = False
                        for (fx, fy, fw, fh) in faces:
                            xA = max(fx, coords[0])
                            yA = max(fy, coords[1])
                            xB = min(fx + fw, coords[2])
                            yB = min(fy + fh, coords[3])
                            interArea = max(0, xB - xA) * max(0, yB - yA)
                            boxArea = (coords[2] - coords[0]) * (coords[3] - coords[1])
                            containment = interArea / float(boxArea + 1e-6)
                            if containment > 0.55:
                                is_face_fp = True
                                break
                        if is_face_fp:
                            print(f"[SUPPRESSION] Suppressed face FP base detection as violation: class {cls}, conf {conf:.2f}")
                            continue
                                
                        raw_violations.append((coords, conf, cls))
                    
                    # Custom model for Phone (0), Book (1), and Casio (2)
                    results_custom = custom_model.predict(source=frame, classes=[0, 1, 2], conf=conf_threshold, verbose=False, imgsz=512)
                    for box in results_custom[0].boxes:
                        coords = box.xyxy[0].tolist()
                        conf = float(box.conf[0])
                        cls = int(box.cls[0])
                        print(f"[WEBCAM CUSTOM DETECT] cls: {cls}, conf: {conf:.2f}, size: {int(coords[2]-coords[0])}x{int(coords[3]-coords[1])}")
                        if cls == 0:
                            mapped_cls = 67
                            # Double-shield filter: Cell phones must have higher confidence to prevent false alarms in Webcam mode
                            min_phone_conf = max(conf_threshold + 0.10, 0.45)
                            if conf < min_phone_conf:
                                continue
                            p_w = coords[2] - coords[0]
                            p_h = coords[3] - coords[1]
                            if p_w > 350 or p_h > 350:
                                continue
                        elif cls == 1:
                            mapped_cls = 73
                        elif cls == 2:
                            mapped_cls = 2
                        else:
                            continue
                        
                        # Suppress face misdetection as a phone/violation in Webcam mode
                        is_face_fp = False
                        for (fx, fy, fw, fh) in faces:
                            xA = max(fx, coords[0])
                            yA = max(fy, coords[1])
                            xB = min(fx + fw, coords[2])
                            yB = min(fy + fh, coords[3])
                            interArea = max(0, xB - xA) * max(0, yB - yA)
                            boxArea = (coords[2] - coords[0]) * (coords[3] - coords[1])
                            containment = interArea / float(boxArea + 1e-6)
                            if containment > 0.55:
                                is_face_fp = True
                                break
                        if is_face_fp:
                            print(f"[SUPPRESSION] Suppressed face FP custom detection as violation: class {mapped_cls}, conf {conf:.2f}")
                            continue
                                
                        raw_violations.append((coords, conf, mapped_cls))
                else:
                    # Fallback to standard base model
                    results = model.predict(source=frame, classes=[67, 73], conf=conf_threshold, verbose=False, imgsz=512)
                    for box in results[0].boxes:
                        coords = box.xyxy[0].tolist()
                        conf = float(box.conf[0])
                        cls = int(box.cls[0])
                        if cls == 63:
                            continue
                        if cls == 67:
                            min_phone_conf = conf_threshold
                            if conf < min_phone_conf:
                                continue
                            p_w = coords[2] - coords[0]
                            p_h = coords[3] - coords[1]
                            if p_w > 350 or p_h > 350:
                                continue
                        
                        # Suppress face misdetection as a phone/violation in Webcam mode
                        is_face_fp = False
                        for (fx, fy, fw, fh) in faces:
                            xA = max(fx, coords[0])
                            yA = max(fy, coords[1])
                            xB = min(fx + fw, coords[2])
                            yB = min(fy + fh, coords[3])
                            interArea = max(0, xB - xA) * max(0, yB - yA)
                            boxArea = (coords[2] - coords[0]) * (coords[3] - coords[1])
                            containment = interArea / float(boxArea + 1e-6)
                            if containment > 0.55:
                                is_face_fp = True
                                break
                        if is_face_fp:
                            print(f"[SUPPRESSION] Suppressed face FP fallback detection as violation: class {cls}, conf {conf:.2f}")
                            continue
                                
                        raw_violations.append((coords, conf, cls))
                
                # Reset out-of-frame count and timer if there is any active violation (phone, laptop, book) 
                # to prevent face-occlusion false alarms (e.g. candidate blocking their face with a phone).
                if len(raw_violations) > 0:
                    out_of_frame_frames = 0
                    out_of_frame_start_time = None
                    
                # Time-based out-of-frame alert: triggers after exactly max_disappeared_time seconds of absence.
                if out_of_frame_start_time is not None:
                    out_of_frame_elapsed = current_time - out_of_frame_start_time
                    if out_of_frame_elapsed > max_disappeared_time:
                        violations.append("Thí sinh rời khỏi khung hình!")
                
                # Post-processing violations (NMS and overlaps)
                raw_violations = apply_violation_nms(raw_violations)
                raw_violations = resolve_cross_class_overlaps(raw_violations)
                other_boxes = violation_tracker.update(raw_violations)
                
                # Draw Webcam violations
                for item in other_boxes:
                    coords = item["coords"]
                    conf = item["conf"]
                    cls = item["cls"]
                    x1, y1, x2, y2 = map(int, coords)
                    
                    if cls == 67:
                        num_phones += 1
                        display_label = f"VIOLATION: SMART DEVICE {conf:.2f}"
                        color = COLOR_PHONE
                        violations.append("Phát hiện điện thoại!")
                    elif cls == 63:
                        num_laptops += 1
                        display_label = f"VIOLATION: SMART DEVICE {conf:.2f}"
                        color = COLOR_PHONE
                        violations.append("Phát hiện laptop/màn hình!")
                    elif cls == 73:
                        num_books += 1
                        display_label = f"VIOLATION: BOOK {conf:.2f}"
                        color = COLOR_VIOLATION
                        violations.append("Phát hiện tài liệu/sách!")
                    elif cls == 2:
                        display_label = f"CASIO CALCULATOR {conf:.2f}"
                        color = (16, 185, 129)
                    
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    tf = max(1, int(1))
                    label_size, base_line = cv2.getTextSize(display_label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, tf)
                    ty1 = max(y1, label_size[1] + 10)
                    cv2.rectangle(frame, (x1, ty1 - label_size[1] - 8), (x1 + label_size[0] + 10, ty1 + base_line - 4), color, -1)
                    cv2.putText(frame, display_label, (x1 + 5, ty1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), tf, lineType=cv2.LINE_AA)
                    
                    detections_log.append({
                        "class": model.names[cls] if cls in model.names else f"Class {cls}",
                        "confidence": conf,
                        "box": [x1, y1, x2, y2]
                    })
                
                # Calculate Webcam Suspicion Index
                suspicion_index = 0
                if num_phones > 0:
                    suspicion_index = 100
                elif any("quay đầu" in v or "liếc mắt" in v for v in violations):
                    suspicion_index = 75
                elif num_laptops > 0 or num_books > 0 or any("Casio" in v for v in violations):
                    suspicion_index = 60
                elif any("rời khỏi khung hình" in v for v in violations):
                    suspicion_index = 40
                else:
                    suspicion_index = 0
                    
            else:
                # ==========================================
                # DIRECTION 1: CCTV MODE (Room Proctoring)
                # ==========================================
                person_detections = []
                raw_violations = []
                if custom_model is not None:
                    # 1. Base model for Person (0), Cell Phone (67), Book (73)
                    results_base = model.predict(source=frame, classes=[0, 67, 73], conf=conf_threshold, verbose=False, imgsz=480)
                    for box in results_base[0].boxes:
                        coords = box.xyxy[0].tolist()
                        conf = float(box.conf[0])
                        cls = int(box.cls[0])
                        if cls == 63:
                            continue
                        print(f"[CCTV BASE DETECT] cls: {cls}, conf: {conf:.2f}, size: {int(coords[2]-coords[0])}x{int(coords[3]-coords[1])}")
                        if cls == 0:
                            person_detections.append((coords, conf))
                        else:
                            if cls == 67:
                                min_phone_conf = conf_threshold
                                if conf < min_phone_conf:
                                    continue
                                p_w = coords[2] - coords[0]
                                p_h = coords[3] - coords[1]
                                if p_w > 350 or p_h > 350:
                                    continue
                            raw_violations.append((coords, conf, cls))
                    
                    # 2. Custom model for Phone (0), Book (1), and Casio (2)
                    results_custom = custom_model.predict(source=frame, classes=[0, 1, 2], conf=conf_threshold, verbose=False, imgsz=512)
                    for box in results_custom[0].boxes:
                        coords = box.xyxy[0].tolist()
                        conf = float(box.conf[0])
                        cls = int(box.cls[0])
                        print(f"[CCTV CUSTOM DETECT] cls: {cls}, conf: {conf:.2f}, size: {int(coords[2]-coords[0])}x{int(coords[3]-coords[1])}")
                        if cls == 0:
                            mapped_cls = 67
                            min_phone_conf = conf_threshold
                            if conf < min_phone_conf:
                                continue
                            p_w = coords[2] - coords[0]
                            p_h = coords[3] - coords[1]
                            if p_w > 350 or p_h > 350:
                                continue
                        elif cls == 1:
                            mapped_cls = 73
                        elif cls == 2:
                            mapped_cls = 2
                        else:
                            continue
                            
                        # Prevent false positives with person boxes
                        is_false_positive = False
                        for p_box, _ in person_detections:
                            xA = max(p_box[0], coords[0])
                            yA = max(p_box[1], coords[1])
                            xB = min(p_box[2], coords[2])
                            yB = min(p_box[3], coords[3])
                            
                            interArea = max(0, xB - xA) * max(0, yB - yA)
                            p_area = (p_box[2] - p_box[0]) * (p_box[3] - p_box[1])
                            c_area = (coords[2] - coords[0]) * (coords[3] - coords[1])
                            
                            iou = interArea / float(p_area + c_area - interArea + 1e-6)
                            area_ratio = c_area / float(p_area + 1e-6)
                            
                            if iou > 0.80 or area_ratio > 0.80:
                                is_false_positive = True
                                break
                                
                        if is_false_positive:
                            continue
                        raw_violations.append((coords, conf, mapped_cls))
                else:
                    # Fallback to standard base model only
                    results = model.predict(source=frame, classes=[0, 67, 73], conf=conf_threshold, verbose=False, imgsz=512)
                    for box in results[0].boxes:
                        coords = box.xyxy[0].tolist()
                        conf = float(box.conf[0])
                        cls = int(box.cls[0])
                        if cls == 63:
                            continue
                        if cls == 0:
                            person_detections.append((coords, conf))
                        else:
                            if cls == 67:
                                min_phone_conf = conf_threshold
                                if conf < min_phone_conf:
                                    continue
                                p_w = coords[2] - coords[0]
                                p_h = coords[3] - coords[1]
                                if p_w > 350 or p_h > 350:
                                    continue
                            raw_violations.append((coords, conf, cls))
                
                # Merge fragmented/split person detections before tracking
                person_detections = merge_person_detections(person_detections)
                
                # Update candidate tracker with person detections
                tracked_candidates = tracker.update(person_detections)
                
                # Continuous defragmentation before starting the exam session
                if not session_active:
                    tracker.defragment()
                    tracked_candidates = tracker.bboxes
                
                # Post-processing violations (NMS and overlaps)
                raw_violations = apply_violation_nms(raw_violations)
                raw_violations = resolve_cross_class_overlaps(raw_violations)
                other_boxes = violation_tracker.update(raw_violations)
                
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
                
                # Draw tracked candidates
                for label, coords in tracked_candidates.items():
                    num_persons += 1
                    conf = tracker.confs.get(label, 1.0)
                    x1, y1, x2, y2 = map(int, coords)
                    display_label = f"Candidate {label}: {conf:.2f}"
                    
                    cv2.rectangle(frame, (x1, y1), (x2, y2), COLOR_PERSON, 2)
                    tf = max(1, int(1))
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
                        display_label = f"VIOLATION: SMART DEVICE {conf:.2f}"
                        color = COLOR_PHONE
                        violations.append("Phát hiện điện thoại!")
                    elif cls == 63:
                        num_laptops += 1
                        display_label = f"VIOLATION: SMART DEVICE {conf:.2f}"
                        color = COLOR_PHONE
                        violations.append("Phát hiện laptop/màn hình!")
                    elif cls == 73:
                        num_books += 1
                        display_label = f"VIOLATION: BOOK {conf:.2f}"
                        color = COLOR_VIOLATION
                        violations.append("Phát hiện tài liệu/sách!")
                    elif cls == 2:
                        display_label = f"CASIO CALCULATOR {conf:.2f}"
                        color = (16, 185, 129)
                    
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    tf = max(1, int(1))
                    label_size, base_line = cv2.getTextSize(display_label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, tf)
                    ty1 = max(y1, label_size[1] + 10)
                    cv2.rectangle(frame, (x1, ty1 - label_size[1] - 8), (x1 + label_size[0] + 10, ty1 + base_line - 4), color, -1)
                    cv2.putText(frame, display_label, (x1 + 5, ty1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), tf, lineType=cv2.LINE_AA)
                    
                    detections_log.append({
                        "class": model.names[cls] if cls in model.names else f"Class {cls}",
                        "confidence": conf,
                        "box": [x1, y1, x2, y2]
                    })
                    
                # Rule engine for exam proctoring
                if session_active:
                    for init_lbl in initial_candidates:
                        if init_lbl not in tracker.bboxes:
                            violations.append(f"Thí sinh {init_lbl} đã rời khỏi vị trí!")
                    for init_lbl, init_data in initial_candidates.items():
                        if init_lbl in tracker.candidates:
                            curr_c = tracker.candidates[init_lbl]
                            init_c = init_data["centroid"]
                            dist = math.sqrt((curr_c[0] - init_c[0])**2 + (curr_c[1] - init_c[1])**2)
                            if dist > 100:
                                violations.append(f"Thí sinh {init_lbl} rời khỏi vị trí ({int(dist)}px)!")
                    for curr_lbl in tracker.bboxes:
                        if curr_lbl not in initial_candidates:
                            violations.append(f"Phát hiện người lạ/người khác xuất hiện: {curr_lbl}!")
                else:
                    if num_persons == 0:
                        violations.append("Không có thí sinh trong khung hình!")
                
                # Calculate Suspicion Index
                suspicion_index = 0
                if num_phones > 0:
                    suspicion_index = 100
                elif any("rời khỏi vị trí" in v or "người lạ" in v or "người khác" in v for v in violations):
                    suspicion_index = 90
                elif num_laptops > 0 or num_books > 0 or any("Casio" in v for v in violations):
                    suspicion_index = 60
                elif num_persons == 0:
                    suspicion_index = 40
                else:
                    suspicion_index = 0
            
            # Check for pending exam violations
            exam_alerts = []
            if student_id:
                sid = student_id.lower()
                if sid in pending_exam_violations and pending_exam_violations[sid]:
                    for alert in pending_exam_violations[sid]:
                        exam_alerts.append(f"EXAM_ALERT: {alert['message']}")
                    pending_exam_violations[sid] = []
                
                other_sid = sid[2:] if sid.startswith("id") else f"id{sid}"
                if other_sid in pending_exam_violations and pending_exam_violations[other_sid]:
                    for alert in pending_exam_violations[other_sid]:
                        alert_msg = f"EXAM_ALERT: {alert['message']}"
                        if alert_msg not in exam_alerts:
                            exam_alerts.append(alert_msg)
                    pending_exam_violations[other_sid] = []
            violations.extend(exam_alerts)
            
            # Suppress all proctoring violations and suspicion index if session is inactive (CCTV mode only)
            if monitoring_mode == "cctv" and (not exam_active or current_session_dir is None):
                violations = []
                suspicion_index = 0
                num_phones = 0
                num_laptops = 0
                num_books = 0
                out_of_frame_frames = 0
                head_turn_frames = 0
                glance_frames = 0
                head_turn_start_time = None
                glance_start_time = None
                out_of_frame_start_time = None
            
            # Encode annotated frame back to base64
            _, buffer = cv2.imencode(".jpg", frame)
            processed_base64 = "data:image/jpeg;base64," + base64.b64encode(buffer).decode("utf-8")
            
            # Prepare response payload
            screen_img = None
            if student_id:
                sid = student_id.lower()
                screen_img = student_screens.get(sid)
                if not screen_img:
                    other_sid = sid[2:] if sid.startswith("id") else f"id{sid}"
                    screen_img = student_screens.get(other_sid)
                
            response_payload = {
                "image": processed_base64,
                "screen_image": screen_img,
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
            
            # Save screenshot proof if the exam session is active and a camera violation is detected
            if exam_active and len(violations) > 0:
                camera_violations = [v for v in violations if not v.startswith("EXAM_ALERT:")]
                if len(camera_violations) > 0 and current_time - last_screenshot_time > 5.0:
                    import datetime
                    try:
                        session_dir = get_or_create_session_dir()
                        student_label = student_id if student_id else "id01"
                        classroom = get_student_classroom(student_label)
                        camera_save_dir = os.path.join(session_dir, classroom, student_label, "Camera")
                        os.makedirs(camera_save_dir, exist_ok=True)
                        
                        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"{student_label}_{now_str}.jpg"
                        save_path = os.path.join(camera_save_dir, filename)
                        
                        # Encode and write safely using Python standard open to bypass OpenCV's Windows unicode path bug
                        ret_val, img_encoded = cv2.imencode('.jpg', frame)
                        if ret_val:
                            with open(save_path, "wb") as f_img:
                                f_img.write(img_encoded.tobytes())
                            print(f"[SCREENSHOT] Saved webcam violation proof for {student_label}: {save_path}")
                            last_screenshot_time = current_time
                    except Exception as e:
                        print(f"[SCREENSHOT ERROR] Failed to save webcam violation proof: {e}")
            
            # Send back to client
            await websocket.send_text(json.dumps(response_payload))
            
    except WebSocketDisconnect:
        print("[WEBSOCKET] Client disconnected.")
    except Exception as e:
        print(f"[WEBSOCKET ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        try:
            await websocket.close()
        except:
            pass

@app.get("/video_feed")
def get_video_feed(camera_idx: int = 0):
    """
    Fallback MJPEG streaming using local webcam connected to server.
    Useful for local machine testing.
    """
    def generate_frames():
        # Setup local video capture
        # Try DirectShow first on Windows to avoid backend delays or failure
        import platform
        if platform.system() == "Windows":
            camera = cv2.VideoCapture(camera_idx, cv2.CAP_DSHOW)
        else:
            camera = cv2.VideoCapture(camera_idx)
            
        if not camera.isOpened():
            # Fallback to default backend if CAP_DSHOW fails
            camera = cv2.VideoCapture(camera_idx)
            
        if not camera.isOpened():
            print(f"[CAMERA ERROR] Local camera index {camera_idx} could not be opened.")
            return
            
        violation_tracker = ViolationTracker(max_disappeared=5)
        
        try:
            while True:
                success, frame = camera.read()
                if not success:
                    break
                    
                # Run YOLOv8
                if model is not None:
                    person_detections = []
                    raw_violations = []
                    
                    if custom_model is not None:
                        # 1. Base model for Person (0)
                        results_base = model.predict(source=frame, classes=[0], conf=0.35, verbose=False, imgsz=480)
                        for box in results_base[0].boxes:
                            coords = box.xyxy[0].tolist()
                            conf = float(box.conf[0])
                            cls = int(box.cls[0])
                            if cls == 0:
                                person_detections.append((coords, conf))
                            elif cls == 63:
                                continue
                                
                        # 2. Custom model for Mobile phone (0), Book (1), and Casio (2)
                        results_custom = custom_model.predict(source=frame, classes=[0, 1, 2], conf=0.35, verbose=False, imgsz=512)
                        for box in results_custom[0].boxes:
                            coords = box.xyxy[0].tolist()
                            conf = float(box.conf[0])
                            cls = int(box.cls[0])
                            if cls == 0:
                                mapped_cls = 67
                                # Apply double-shield filter for cell phones
                                min_phone_conf = max(0.35 + 0.08, 0.43)
                                if conf < min_phone_conf:
                                    continue
                                p_w = coords[2] - coords[0]
                                p_h = coords[3] - coords[1]
                                if p_w > 350 or p_h > 350:
                                    continue
                            elif cls == 1:
                                mapped_cls = 73
                            elif cls == 2:
                                mapped_cls = 2
                            else:
                                continue
                                
                            # Prevent false positives where the custom model misclassifies a person as a phone/book.
                            is_false_positive = False
                            for p_box, _ in person_detections:
                                xA = max(p_box[0], coords[0])
                                yA = max(p_box[1], coords[1])
                                xB = min(p_box[2], coords[2])
                                yB = min(p_box[3], coords[3])
                                
                                interArea = max(0, xB - xA) * max(0, yB - yA)
                                p_area = (p_box[2] - p_box[0]) * (p_box[3] - p_box[1])
                                c_area = (coords[2] - coords[0]) * (coords[3] - coords[1])
                                
                                iou = interArea / float(p_area + c_area - interArea + 1e-6)
                                area_ratio = c_area / float(p_area + 1e-6)
                                
                                if iou > 0.80 or area_ratio > 0.80:
                                    is_false_positive = True
                                    break
                                    
                            if is_false_positive:
                                continue
                                
                            raw_violations.append((coords, conf, mapped_cls))
                    else:
                        # Fallback to standard base model only
                        results = model.predict(source=frame, classes=[0, 67, 73], conf=0.35, verbose=False, imgsz=512)
                        for box in results[0].boxes:
                            coords = box.xyxy[0].tolist()
                            conf = float(box.conf[0])
                            cls = int(box.cls[0])
                            if cls == 63:
                                continue
                            if cls == 0:
                                person_detections.append((coords, conf))
                            else:
                                if cls == 67:
                                    # Apply double-shield filter for cell phones
                                    min_phone_conf = max(0.35 + 0.08, 0.43)
                                    if conf < min_phone_conf:
                                        continue
                                    p_w = coords[2] - coords[0]
                                    p_h = coords[3] - coords[1]
                                    if p_w > 350 or p_h > 350:
                                        continue
                                raw_violations.append((coords, conf, cls))
                    
                    # Merge split person boxes
                    person_detections = merge_person_detections(person_detections)
                    
                    # Draw merged person detections
                    for coords, conf in person_detections:
                        x1, y1, x2, y2 = map(int, coords)
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 120, 0), 2)
                        cv2.putText(frame, f"Candidate: {conf:.2f}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 120, 0), 1)
                        
                    # Apply Non-Maximum Suppression (NMS) to eliminate duplicate boxes (e.g. 1 phone showing 2 boxes)
                    raw_violations = apply_violation_nms(raw_violations)

                    # Resolve overlapping boxes between different violation classes (e.g. Phone vs Laptop)
                    raw_violations = resolve_cross_class_overlaps(raw_violations)

                    # Update violation tracker with raw violations to smooth and persist boxes
                    tracked_violations = violation_tracker.update(raw_violations)

                    # Draw non-person detections
                    for item in tracked_violations:
                        coords = item["coords"]
                        conf = item["conf"]
                        cls = item["cls"]
                        x1, y1, x2, y2 = map(int, coords)
                        if cls == 67:
                            color = (68, 68, 239)
                            label = f"VIOLATION: SMART DEVICE {conf:.2f}"
                        elif cls == 2:
                            color = (16, 185, 129)
                            label = f"CASIO CALCULATOR {conf:.2f}"
                        else:
                            color = (0, 140, 255)
                            label = f"VIOLATION: {model.names[cls] if cls in model.names else f'Class {cls}'} {conf:.2f}"
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
