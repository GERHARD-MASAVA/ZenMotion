# prototype_alpr_gate.py
import cv2
import easyocr
import sqlite3
import time
import os
import torch

# If on a Raspberry Pi and using GPIO:
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    RELAY_PIN = 18
    GPIO.setup(RELAY_PIN, GPIO.OUT, initial=GPIO.LOW)
    HAVE_GPIO = True
except Exception:
    HAVE_GPIO = False

# config
CAMERA_SOURCE = 0  # 0 = default webcam, or replace with RTSP/USB path
DB_PATH = 'alpr.db'
OPEN_TIME_SEC = 5  # how long to keep gate open

# prepare OCR
reader = easyocr.Reader(['en'])  # language(s)

# DB helper
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS allowed_plates (
                        id INTEGER PRIMARY KEY,
                        plate_text TEXT UNIQUE)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS access_log (
                        id INTEGER PRIMARY KEY,
                        timestamp TEXT,
                        plate_text TEXT,
                        confidence REAL,
                        allowed INTEGER)''')
    conn.commit()
    return conn

def is_allowed(conn, plate):
    cur = conn.cursor()
    cur.execute("SELECT id FROM allowed_plates WHERE plate_text = ?", (plate,))
    r = cur.fetchone()
    return r[0] if r else None

def log_event(conn, plate, conf, allowed):
    cur = conn.cursor()
    cur.execute("INSERT INTO access_log (timestamp, plate_text, confidence, allowed) VALUES (datetime('now'),?,?,?)",
                (plate, conf, int(bool(allowed))))
    conn.commit()

# === YOLOv5 detector (inline) ===
class YOLOv5Detector:
    def __init__(self, model_name='yolov5s', device=None):
        # Load YOLOv5 model via Torch Hub
        self.model = torch.hub.load('ultralytics/yolov5', 'custom',
                                    path=model_name, force_reload=True)
        self.model.conf = 0.25  # confidence threshold
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)

    def detect(self, frame):
        results = self.model(frame)
        detections = []
        for *xyxy, conf, cls in results.xyxy[0].tolist():
            x1, y1, x2, y2 = map(int, xyxy)
            detections.append((x1, y1, x2, y2, conf))
        return detections

# create detector once (load weights)
detector = YOLOv5Detector(model_name='yolov5s.pt')  
# 👉 later swap with your trained weights: 'runs/train/exp/weights/best.pt'

def detect_plates(frame):
    """
    Run YOLOv5 on the frame and return boxes in (x,y,w,h) format.
    """
    detections = detector.detect(frame)  # [(x1,y1,x2,y2,conf), ...]
    boxes = []
    for (x1,y1,x2,y2,conf) in detections:
        w, h = x2 - x1, y2 - y1
        boxes.append((x1, y1, w, h))
    return boxes

def trigger_gate():
    if HAVE_GPIO:
        GPIO.output(RELAY_PIN, GPIO.HIGH)
        time.sleep(OPEN_TIME_SEC)
        GPIO.output(RELAY_PIN, GPIO.LOW)
    else:
        print("[DEBUG] Trigger gate (simulate)")

def main():
    conn = init_db()
    cap = cv2.VideoCapture(CAMERA_SOURCE)
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.5)
            continue

        boxes = detect_plates(frame)
        for (x, y, w, h) in boxes:
            crop = frame[y:y+h, x:x+w]

            # OCR
            result = reader.readtext(crop)
            plate_text = None
            best_conf = 0.0
            for (bbox, text, conf) in result:
                cleaned = ''.join(ch for ch in text if ch.isalnum())
                if len(cleaned) >= 4 and conf > best_conf:
                    plate_text = cleaned.upper()
                    best_conf = conf

            if plate_text:
                match_id = is_allowed(conn, plate_text)
                allowed = bool(match_id)
                log_event(conn, plate_text, best_conf, allowed)
                print(f"{time.ctime()} - Plate: {plate_text} conf={best_conf:.2f} allowed={allowed}")
                if allowed:
                    trigger_gate()
                # Save snapshot
                os.makedirs('snapshots', exist_ok=True)
                cv2.imwrite(f'snapshots/{int(time.time())}_{plate_text}.jpg', crop)

        # optional: show debug window
        for (x, y, w, h) in boxes:
            cv2.rectangle(frame, (x,y), (x+w, y+h), (0,255,0), 2)
        cv2.imshow('alpr', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    if HAVE_GPIO:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
