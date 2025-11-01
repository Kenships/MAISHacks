import mediapipe as mp
import cv2
import threading
import time

class GestureController:
    def __init__(self, callback):
        self.callback = callback
        self.is_running = False
        self.cap = None
        self.recognizer = None
        self.frame_count = 0
        self.last_gesture = None
        self.last_gesture_time = 0
        self.gesture_cooldown = 1.0  # 1 second cooldown between gestures
        
    def start(self):
        if self.is_running:
            return
            
        try:
            # Initialize MediaPipe Gesture Recognizer
            BaseOptions = mp.tasks.BaseOptions
            GestureRecognizer = mp.tasks.vision.GestureRecognizer
            GestureRecognizerOptions = mp.tasks.vision.GestureRecognizerOptions
            VisionRunningMode = mp.tasks.vision.RunningMode
            
            options = GestureRecognizerOptions(
                base_options=BaseOptions(model_asset_path='gesture_recognizer.task'),
                running_mode=VisionRunningMode.VIDEO,
                num_hands=2
            )
            self.recognizer = GestureRecognizer.create_from_options(options)
            
            # Open webcam
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                raise Exception("Could not open webcam")
                
            self.is_running = True
            self.thread = threading.Thread(target=self._process_video, daemon=True)
            self.thread.start()
            
        except Exception as e:
            raise Exception(f"Failed to start gesture recognition: {str(e)}")
    
    def stop(self):
        self.is_running = False
        if self.cap:
            self.cap.release()
        if self.recognizer:
            self.recognizer.close()
    
    def _process_video(self):
        while self.is_running:
            ret, frame = self.cap.read()
            if not ret:
                continue
            
            frame = cv2.flip(frame, 1)  # Mirror the frame
            self.frame_count += 1
            
            # Convert frame to MediaPipe Image format
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
            
            # Get timestamp in milliseconds
            timestamp_ms = int(self.cap.get(cv2.CAP_PROP_POS_MSEC))
            if timestamp_ms == 0:
                timestamp_ms = self.frame_count * 33  # Approximate 30 fps
            
            # Recognize gestures
            recognition_result = self.recognizer.recognize_for_video(mp_image, timestamp_ms)
            
            # Process results
            detected_gesture = None
            confidence = 0
            
            if recognition_result.gestures:
                for i, gesture_list in enumerate(recognition_result.gestures):
                    if gesture_list:
                        # Get the top gesture
                        top_gesture = gesture_list[0]
                        gesture_name = top_gesture.category_name
                        confidence = top_gesture.score
                        
                        if confidence > 0.5:  # Only consider high confidence gestures
                            detected_gesture = gesture_name
                        
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
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Display instructions
            cv2.putText(frame, "Thumbs_Up: Play/Pause | Victory: Next | Closed_Fist: Prev", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            
            # Handle gesture commands with cooldown
            current_time = time.time()
            if detected_gesture and (detected_gesture != self.last_gesture or current_time - self.last_gesture_time > self.gesture_cooldown):
                # if detected_gesture != self.last_gesture:
                self.callback('gesture', detected_gesture, confidence)
                self.last_gesture = detected_gesture
                self.last_gesture_time = current_time
            
            # Send frame to display
            self.callback('frame', frame, None)
            
            time.sleep(0.03)  # ~30 fps