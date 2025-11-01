import mediapipe as mp
import cv2
import numpy as np

# Initialize MediaPipe Gesture Recognizer
BaseOptions = mp.tasks.BaseOptions
GestureRecognizer = mp.tasks.vision.GestureRecognizer
GestureRecognizerOptions = mp.tasks.vision.GestureRecognizerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

# Create a gesture recognizer instance
options = GestureRecognizerOptions(
    base_options=BaseOptions(model_asset_path='gesture_recognizer.task'),
    running_mode=VisionRunningMode.VIDEO,
    num_hands=2)

recognizer = GestureRecognizer.create_from_options(options)

# Open webcam
cap = cv2.VideoCapture(0)

print("MediaPipe Gesture Recognition")
print("Built-in gestures: Thumbs_Up, Victory, Open_Palm, Closed_Fist, etc.")
print("Press 'q' to quit")

frame_count = 0

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        print("Failed to grab frame")
        break
    
    frame = cv2.flip(frame, 1)  # Mirror the frame
    frame_count += 1
    
    # Convert frame to MediaPipe Image format
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
    
    # Get timestamp in milliseconds
    timestamp_ms = int(cap.get(cv2.CAP_PROP_POS_MSEC))
    if timestamp_ms == 0:
        timestamp_ms = frame_count * 33  # Approximate 30 fps
    
    # Recognize gestures
    recognition_result = recognizer.recognize_for_video(mp_image, timestamp_ms)
    
    # Process results
    if recognition_result.gestures:
        for i, gesture_list in enumerate(recognition_result.gestures):
            if gesture_list:
                # Get the top gesture
                top_gesture = gesture_list[0]
                gesture_name = top_gesture.category_name
                confidence = top_gesture.score
                
                # Get hand landmarks for this hand
                if recognition_result.hand_landmarks and i < len(recognition_result.hand_landmarks):
                    hand_landmarks = recognition_result.hand_landmarks[i]
                    
                    # Draw hand landmarks
                    h, w, c = frame.shape
                    for landmark in hand_landmarks:
                        x = int(landmark.x * w)
                        y = int(landmark.y * h)
                        cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)
                    
                    # Get wrist position for label placement
                    wrist = hand_landmarks[0]
                    x_pos = int(wrist.x * w)
                    y_pos = int(wrist.y * h)
                    
                    # Display gesture name and confidence
                    label = f"{gesture_name}: {confidence:.2f}"
                    cv2.putText(frame, label, (x_pos, y_pos - 20),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    
                    print(f"Detected: {gesture_name} (confidence: {confidence:.2f})")
    
    # Display instructions
    cv2.putText(frame, "Show hand gestures", (10, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    cv2.imshow('Gesture Recognition', frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
recognizer.close()
print("Gesture recognition stopped.")