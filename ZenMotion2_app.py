# Install dependencies
!pip install mediapipe opencv-python

# Import libraries
import cv2
import mediapipe as mp
import numpy as np
from google.colab.output import eval_js
from base64 import b64decode, b64encode
from IPython.display import Javascript, HTML
from google.colab import output
import io
from PIL import Image

# JS code to access webcam
def js_to_image(js_reply):
    image_bytes = b64decode(js_reply.split(',')[1])
    jpg_as_np = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(jpg_as_np, cv2.IMREAD_COLOR)
    return img

def bbox_to_bytes(bbox_array):
    bbox_PIL = Image.fromarray(bbox_array, 'RGB')
    iobuf = io.BytesIO()
    bbox_PIL.save(iobuf, format='JPEG')
    bbox_bytes = 'data:image/jpeg;base64,' + b64encode(iobuf.getvalue()).decode('utf-8')
    return bbox_bytes

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

# Pose detection setup
mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose

def calculate_angle(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians*180.0/np.pi)
    if angle > 180.0:
        angle = 360 - angle
    return angle

# Exercise selector: "squat", "pushup", "curl"
exercise = "squat"
counter = 0
stage = None

pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

def process_frame(image):
    global counter, stage
    results = pose.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    feedback = ""

    if results.pose_landmarks:
        landmarks = results.pose_landmarks.landmark
        
        if exercise == "squat":
            hip = [landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x,
                   landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y]
            knee = [landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].x,
                    landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].y]
            ankle = [landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].x,
                     landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y]
            angle = calculate_angle(hip, knee, ankle)
            
            if angle > 160:
                stage = "up"
            if angle < 70 and stage == "up":
                stage = "down"
                counter += 1

            if angle > 170:
                feedback = "Stand straight"
            elif angle < 50:
                feedback = "Go lower"

        elif exercise == "pushup":
            shoulder = [landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x,
                        landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
            elbow = [landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].x,
                     landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].y]
            wrist = [landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].x,
                     landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].y]
            angle = calculate_angle(shoulder, elbow, wrist)

            if angle > 160:
                stage = "up"
            if angle < 90 and stage == "up":
                stage = "down"
                counter += 1

            if angle > 170:
                feedback = "Locking out too much"
            elif angle < 80:
                feedback = "Too low"

        elif exercise == "curl":
            shoulder = [landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x,
                        landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
            elbow = [landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].x,
                     landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].y]
            wrist = [landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].x,
                     landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].y]
            angle = calculate_angle(shoulder, elbow, wrist)

            if angle > 160:
                stage = "down"
            if angle < 50 and stage == "down":
                stage = "up"
                counter += 1

            if angle > 170:
                feedback = "Arm too straight"
            elif angle < 40:
                feedback = "Curl complete"

        mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

    cv2.putText(image, f"{exercise.upper()} REPS: {counter}", (10,30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2, cv2.LINE_AA)
    cv2.putText(image, feedback, (10,70),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2, cv2.LINE_AA)
    
    return image

# Bridge: Receive frames from JS and process
def handle_frame(js_reply):
    image = js_to_image(js_reply)
    image = cv2.resize(image, (640,480))
    processed = process_frame(image)
    return bbox_to_bytes(processed)

output.register_callback('notebook.run_frame', handle_frame)

# Start the video stream
video_stream()
