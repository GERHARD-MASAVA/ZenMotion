# Install dependencies
!pip install mediapipe opencv-python ipywidgets

import cv2
import mediapipe as mp
import numpy as np
from google.colab.output import eval_js
from base64 import b64decode, b64encode
from IPython.display import Javascript, display
from google.colab import output
import io
from PIL import Image
import ipywidgets as widgets

# --- Webcam helpers ---
def js_to_image(js_reply):
    image_bytes = b64decode(js_reply.split(',')[1])
    jpg_as_np = np.frombuffer(image_bytes, dtype=np.uint8)
    return cv2.imdecode(jpg_as_np, cv2.IMREAD_COLOR)

def bbox_to_bytes(bbox_array):
    bbox_PIL = Image.fromarray(bbox_array, 'RGB')
    iobuf = io.BytesIO()
    bbox_PIL.save(iobuf, format='JPEG')
    return 'data:image/jpeg;base64,' + b64encode(iobuf.getvalue()).decode('utf-8')

def video_stream():
    js = Javascript('''
      async function stream_frame() {
        const video = document.createElement('video');
        document.body.appendChild(video);
        const stream = await navigator.mediaDevices.getUserMedia({video: true});
        video.srcObject = stream;
        await video.play();

        const canvas = document.createElement('canvas');
        canvas.width = 640;
        canvas.height = 480;
        const context = canvas.getContext('2d');

        document.body.appendChild(canvas);

        while (true) {
          context.drawImage(video, 0, 0, 640, 480);
          const image = canvas.toDataURL('image/jpeg', 0.8);
          google.colab.kernel.invokeFunction('notebook.run_frame', [image], {});
          await new Promise(r => setTimeout(r, 100));
        }
      }
      stream_frame();
    ''')
    display(js)

# --- Pose + logic ---
mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose

def calculate_angle(a, b, c):
    a, b, c = np.array(a), np.array(b), np.array(c)
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians*180.0/np.pi)
    return 360 - angle if angle > 180.0 else angle

# --- State ---
exercise = "squat"  # default
counter = 0
stage = None
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

def process_frame(image):
    global counter, stage, exercise
    results = pose.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    feedback = ""

    if results.pose_landmarks:
        lm = results.pose_landmarks.landmark

        if exercise == "squat":
            hip = [lm[mp_pose.PoseLandmark.LEFT_HIP.value].x, lm[mp_pose.PoseLandmark.LEFT_HIP.value].y]
            knee = [lm[mp_pose.PoseLandmark.LEFT_KNEE.value].x, lm[mp_pose.PoseLandmark.LEFT_KNEE.value].y]
            ankle = [lm[mp_pose.PoseLandmark.LEFT_ANKLE.value].x, lm[mp_pose.PoseLandmark.LEFT_ANKLE.value].y]
            angle = calculate_angle(hip, knee, ankle)
            if angle > 160: stage = "up"
            if angle < 70 and stage == "up": stage, counter = "down", counter + 1
            feedback = "Stand straight" if angle > 170 else ("Go lower" if angle < 50 else "")

        elif exercise == "pushup":
            shoulder = [lm[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x, lm[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
            elbow = [lm[mp_pose.PoseLandmark.LEFT_ELBOW.value].x, lm[mp_pose.PoseLandmark.LEFT_ELBOW.value].y]
            wrist = [lm[mp_pose.PoseLandmark.LEFT_WRIST.value].x, lm[mp_pose.PoseLandmark.LEFT_WRIST.value].y]
            angle = calculate_angle(shoulder, elbow, wrist)
            if angle > 160: stage = "up"
            if angle < 90 and stage == "up": stage, counter = "down", counter + 1
            feedback = "Locking out too much" if angle > 170 else ("Too low" if angle < 80 else "")

        elif exercise == "curl":
            shoulder = [lm[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x, lm[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
            elbow = [lm[mp_pose.PoseLandmark.LEFT_ELBOW.value].x, lm[mp_pose.PoseLandmark.LEFT_ELBOW.value].y]
            wrist = [lm[mp_pose.PoseLandmark.LEFT_WRIST.value].x, lm[mp_pose.PoseLandmark.LEFT_WRIST.value].y]
            angle = calculate_angle(shoulder, elbow, wrist)
            if angle > 160: stage = "down"
            if angle < 50 and stage == "down": stage, counter = "up", counter + 1
            feedback = "Arm too straight" if angle > 170 else ("Curl complete" if angle < 40 else "")

        mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

    cv2.putText(image, f"{exercise.upper()} REPS: {counter}", (10,30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2, cv2.LINE_AA)
    cv2.putText(image, feedback, (10,70),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2, cv2.LINE_AA)
    return image

def handle_frame(js_reply):
    image = js_to_image(js_reply)
    image = cv2.resize(image, (640,480))
    processed = process_frame(image)
    return bbox_to_bytes(processed)

output.register_callback('notebook.run_frame', handle_frame)

# --- UI Buttons ---
def set_exercise(change):
    global exercise, counter, stage
    exercise = change['new']
    counter, stage = 0, None
    print(f"Switched to: {exercise}")

exercise_selector = widgets.ToggleButtons(
    options=['squat', 'pushup', 'curl'],
    description='Exercise:',
    disabled=False,
    button_style='info'
)
exercise_selector.observe(set_exercise, names='value')
display(exercise_selector)

# --- Start video stream ---
video_stream()
