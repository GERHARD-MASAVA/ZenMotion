import streamlit as st
import cv2
import mediapipe as mp
import numpy as np

# --- Streamlit UI setup ---
st.set_page_config(page_title="ZenMotion AI", layout="wide")
st.title("🏋️ ZenMotion AI – Your Smart Fitness & Wellness Coach")

# Sidebar controls
exercise = st.sidebar.radio("Choose Exercise", ["Squat", "Pushup", "Curl"])
st.sidebar.write("Selected Exercise:", exercise)

# --- Mediapipe setup ---
mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

# --- Exercise logic helpers ---
def calculate_angle(a, b, c):
    a, b, c = np.array(a), np.array(b), np.array(c)
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians * 180.0 / np.pi)
    return 360 - angle if angle > 180.0 else angle

# State variables
if "counter" not in st.session_state: st.session_state.counter = 0
if "stage" not in st.session_state: st.session_state.stage = None

def process_exercise(image, exercise):
    global feedback
    results = pose.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    feedback = ""

    if results.pose_landmarks:
        lm = results.pose_landmarks.landmark

        if exercise == "Squat":
            hip = [lm[mp_pose.PoseLandmark.LEFT_HIP.value].x, lm[mp_pose.PoseLandmark.LEFT_HIP.value].y]
            knee = [lm[mp_pose.PoseLandmark.LEFT_KNEE.value].x, lm[mp_pose.PoseLandmark.LEFT_KNEE.value].y]
            ankle = [lm[mp_pose.PoseLandmark.LEFT_ANKLE.value].x, lm[mp_pose.PoseLandmark.LEFT_ANKLE.value].y]
            angle = calculate_angle(hip, knee, ankle)

            if angle > 160: st.session_state.stage = "up"
            if angle < 70 and st.session_state.stage == "up":
                st.session_state.stage = "down"
                st.session_state.counter += 1
            feedback = "Stand tall" if angle > 170 else ("Go deeper" if angle < 50 else "")

        elif exercise == "Pushup":
            shoulder = [lm[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x, lm[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
            elbow = [lm[mp_pose.PoseLandmark.LEFT_ELBOW.value].x, lm[mp_pose.PoseLandmark.LEFT_ELBOW.value].y]
            wrist = [lm[mp_pose.PoseLandmark.LEFT_WRIST.value].x, lm[mp_pose.PoseLandmark.LEFT_WRIST.value].y]
            angle = calculate_angle(shoulder, elbow, wrist)

            if angle > 160: st.session_state.stage = "up"
            if angle < 90 and st.session_state.stage == "up":
                st.session_state.stage = "down"
                st.session_state.counter += 1
            feedback = "Lockout" if angle > 170 else ("Too low" if angle < 80 else "")

        elif exercise == "Curl":
            shoulder = [lm[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x, lm[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
            elbow = [lm[mp_pose.PoseLandmark.LEFT_ELBOW.value].x, lm[mp_pose.PoseLandmark.LEFT_ELBOW.value].y]
            wrist = [lm[mp_pose.PoseLandmark.LEFT_WRIST.value].x, lm[mp_pose.PoseLandmark.LEFT_WRIST.value].y]
            angle = calculate_angle(shoulder, elbow, wrist)

            if angle > 160: st.session_state.stage = "down"
            if angle < 50 and st.session_state.stage == "down":
                st.session_state.stage = "up"
                st.session_state.counter += 1
            feedback = "Arm too straight" if angle > 170 else ("Good curl!" if angle < 40 else "")

        # Draw landmarks
        mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

    return image, feedback

# --- Webcam input ---
st.write("### 🎥 Camera Feed")
camera_input = st.camera_input("Show me your form")

if camera_input:
    file_bytes = np.asarray(bytearray(camera_input.getbuffer()), dtype=np.uint8)
    image = cv2.imdecode(file_bytes, 1)

    processed, feedback = process_exercise(image, exercise)

    # Show metrics
    st.metric(label="Reps Completed", value=st.session_state.counter)
    st.metric(label="Form Feedback", value=feedback if feedback else "Looks good!")

    # Show annotated image
    st.image(cv2.cvtColor(processed, cv2.COLOR_BGR2RGB), channels="RGB")

# Reset button
if st.button("🔄 Reset Counter"):
    st.session_state.counter = 0
    st.session_state.stage = None
    st.success("Counter reset!")
