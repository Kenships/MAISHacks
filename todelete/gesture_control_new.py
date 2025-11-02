import time
import cv2
import numpy as np
import threading
from dynamic_gestures.main_controller import MainController
from dynamic_gestures.utils import Drawer, Event, targets


class GestureController:
    def __init__(self, callback, detector_path='dynamic_gestures/models/hand_detector.onnx', classifier_path='dynamic_gestures/models/crops_classifier.onnx', debug=True, show_video=True):
        self.callback = callback
        self.is_running = False
        self.cap = None
        self.controller = None
        self.drawer = None
        self.thread = None
        self.detector_path = detector_path
        self.classifier_path = classifier_path
        self.debug_mode = debug
        self.show_video = show_video  # Whether to display video with cv2.imshow
        
    def start(self):
        if self.is_running:
            return
            
        try:
            # Initialize camera
            self.cap = cv2.VideoCapture(0)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            
            if not self.cap.isOpened():
                raise Exception("Could not open webcam")
            
            # Initialize controller and drawer
            self.controller = MainController(self.detector_path, self.classifier_path)
            self.drawer = Drawer()
            
            self.is_running = True
            self.thread = threading.Thread(target=self._process_video, daemon=True)
            self.thread.start()
            
        except Exception as e:
            raise Exception(f"Failed to start gesture recognition: {str(e)}")
    
    def stop(self):
        self.is_running = False
        if self.cap:
            self.cap.release()
        if self.show_video:
            cv2.destroyAllWindows()
        if self.thread:
            self.thread.join(timeout=1.0)
    
    def _process_video(self):
        while self.is_running:
            ret, frame = self.cap.read()
            if not ret:
                continue
            
            frame = cv2.flip(frame, 1)
            start_time = time.time()
            
            # Get detections from controller
            bboxes, ids, labels = self.controller(frame)
            
            # Draw bounding boxes and labels in debug mode
            if self.debug_mode:
                if bboxes is not None:
                    bboxes = bboxes.astype(np.int32)
                    for i in range(bboxes.shape[0]):
                        box = bboxes[i, :]
                        gesture = targets[labels[i]] if labels[i] is not None else "None"
                        
                        cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), (255, 255, 0), 4)
                        cv2.putText(
                            frame,
                            f"ID {ids[i]} : {gesture}",
                            (box[0], box[1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1,
                            (0, 0, 255),
                            2,
                        )
                
                # Display FPS
                fps = 1.0 / (time.time() - start_time)
                cv2.putText(frame, f"fps {fps:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            # Process tracks and detect actions/combos
            if len(self.controller.tracks) > 0:
                print("self.controller.tracks")
                count_of_zoom = 0
                thumb_boxes = []
                
                for trk in self.controller.tracks:
                    if trk["tracker"].time_since_update < 1:
                        if len(trk['hands']):
                            # Get current gesture label
                            current_gesture = trk['hands'][-1].gesture
                            gesture_name = targets[current_gesture] if current_gesture is not None else "None"
                            
                            # Send individual gesture
                            # self.callback('gesture', gesture_name, trk['hands'][-1])
                            
                            # Check for zoom gesture (gesture 3)
                            count_of_zoom += (current_gesture == 3)
                            thumb_boxes.append(trk['hands'][-1].bbox)
                            
                            # Check for combo: three consecutive gesture 23s
                            if len(trk['hands']) > 3 and [trk['hands'][-1].gesture, trk['hands'][-2].gesture, trk['hands'][-3].gesture] == [23, 23, 23]:
                                self.callback('combo', 'triple_23', trk['hands'][-1])
                                
                                # Apply blur effect
                                x, y, x2, y2 = map(int, trk['hands'][-1].bbox)
                                x, y, x2, y2 = max(x, 0), max(y, 0), max(x2, 0), max(y2, 0)
                                bbox_area = frame[y:y2, x:x2]
                                blurred_bbox = cv2.GaussianBlur(bbox_area, (51, 51), 10)
                                frame[y:y2, x:x2] = blurred_bbox
                        
                        # Check for action events
                        if trk["hands"].action is not None:
                            action = trk["hands"].action
                            
                            # Send action event
                            self.callback('action', action, None)
                            
                            # Set drawer action
                            print(f"Setting drawer action: {action}")  # Debug
                            self.drawer.set_action(action)
                            
                            # Handle different actions
                            if action in [Event.SWIPE_LEFT, Event.SWIPE_LEFT2, Event.SWIPE_LEFT3]:
                                trk["hands"].action = None
                                
                            elif action in [Event.SWIPE_RIGHT, Event.SWIPE_RIGHT2, Event.SWIPE_RIGHT3]:
                                trk["hands"].action = None
                                
                            elif action in [Event.SWIPE_UP, Event.SWIPE_UP2, Event.SWIPE_UP3]:
                                trk["hands"].action = None
                                
                            elif action in [Event.SWIPE_DOWN, Event.SWIPE_DOWN2, Event.SWIPE_DOWN3]:
                                trk["hands"].action = None
                                
                            elif action == Event.DRAG or action == Event.DRAG2 or action == Event.DRAG3:
                                pass  # Keep action active during drag
                                
                            elif action == Event.DROP or action == Event.DROP2 or action == Event.DROP3:
                                trk["hands"].action = None
                                
                            elif action == Event.FAST_SWIPE_DOWN:
                                trk["hands"].action = None
                                
                            elif action == Event.FAST_SWIPE_UP:
                                trk["hands"].action = None
                                
                            elif action == Event.ZOOM_IN:
                                trk["hands"].action = None
                                
                            elif action == Event.ZOOM_OUT:
                                trk["hands"].action = None
                                
                            elif action == Event.DOUBLE_TAP:
                                trk["hands"].action = None
                                
                            elif action == Event.TAP:
                                trk["hands"].action = None
                                
                            # Catch any other actions
                            else:
                                trk["hands"].action = None
                
                # Check for two-hand zoom
                if count_of_zoom == 2:
                    self.drawer.draw_two_hands(frame, thumb_boxes)
                    self.callback('combo', 'two_hand_zoom', None)
            
            frame = self.drawer.draw(frame)
            print("action", self.drawer.action)
            if self.drawer.action is not None:
                print(f"Drawer has action: {self.drawer.action}, show_delay: {self.drawer.show_delay}")
            
            # Display frame with OpenCV if enabled
            if self.show_video:
                cv2.imshow("Gesture Control", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    self.stop()
            
            # Still send frame via callback for other uses
            self.callback('frame', frame, None)
            
            time.sleep(0.03)  # ~30 fps