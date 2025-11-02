import tkinter as tk
from tkinter import ttk
from pynput.keyboard import Key, Controller
import numpy as np
import cv2
import time
import threading
from PIL import Image, ImageTk

from main_controller import MainController
from utils import Drawer, Event, targets


class MediaMusicController:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Music Controller with Gestures")
        self.root.geometry("400x400")
        self.root.configure(bg="#282828")
        
        self.keyboard = Controller()
        self.is_gesture_active = False
        self.gesture_thread = None
        self.stop_flag = False
        
        # Initialize controller (will be created when gesture control starts)
        self.controller = None
        self.drawer = None
        self.cap = None
        
        # Title
        title = tk.Label(
            root,
            text="🎵 YouTube Music Controller",
            font=("Arial", 18, "bold"),
            bg="#282828",
            fg="#ffffff"
        )
        title.pack(pady=10)
        
        # Gesture control button
        self.gesture_btn = tk.Button(
            root,
            text="📷 Start Gesture Control",
            command=self.toggle_gesture_control,
            font=("Arial", 10, "bold"),
            width=25,
            height=2,
            bg="#0066cc",
            fg="white",
            activebackground="#0044aa",
            activeforeground="white",
            border=0,
            cursor="hand2"
        )
        self.gesture_btn.pack(pady=10)
        
        # Button frame
        button_frame = tk.Frame(root, bg="#282828")
        button_frame.pack(pady=10)
        
        # Style for buttons
        button_config = {
            "font": ("Arial", 10),
            "width": 10,
            "height": 2,
            "bg": "#ff0000",
            "fg": "white",
            "activebackground": "#cc0000",
            "activeforeground": "white",
            "border": 0,
            "cursor": "hand2"
        }
        
        # Previous button
        self.prev_btn = tk.Button(
            button_frame,
            text="⏮ Previous",
            command=self.previous_track,
            **button_config
        )
        self.prev_btn.grid(row=0, column=0, padx=3, pady=5)
        
        # Play/Pause button
        self.play_btn = tk.Button(
            button_frame,
            text="⏯ Play/Pause",
            command=self.play_pause,
            **button_config
        )
        self.play_btn.grid(row=0, column=1, padx=3, pady=5)
        
        # Next button
        self.next_btn = tk.Button(
            button_frame,
            text="⏭ Next",
            command=self.next_track,
            **button_config
        )
        self.next_btn.grid(row=0, column=2, padx=3, pady=5)
        
        # Volume controls
        volume_frame = tk.Frame(root, bg="#282828")
        volume_frame.pack(pady=5)
        
        self.vol_down_btn = tk.Button(
            volume_frame,
            text="🔉 Vol Down",
            command=self.volume_down,
            **button_config
        )
        self.vol_down_btn.grid(row=0, column=0, padx=3)
        
        self.vol_up_btn = tk.Button(
            volume_frame,
            text="🔊 Vol Up",
            command=self.volume_up,
            **button_config
        )
        self.vol_up_btn.grid(row=0, column=1, padx=3)
        
        # Status label
        self.status_label = tk.Label(
            root,
            text="Ready - Click 'Start Gesture Control' to begin",
            font=("Arial", 9),
            bg="#282828",
            fg="#00ff00"
        )
        self.status_label.pack(pady=10)
        
        # Gesture info
        info_text = "Gestures: Swipe Left/Right = Prev/Next | Swipe Up/Down = Vol"
        self.info_label = tk.Label(
            root,
            text=info_text,
            font=("Arial", 8),
            bg="#282828",
            fg="#aaaaaa"
        )
        self.info_label.pack(pady=5)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def toggle_gesture_control(self):
        if not self.is_gesture_active:
            self.start_gesture_control()
        else:
            self.stop_gesture_control()
    
    def start_gesture_control(self):
        """Start the gesture recognition system"""
        self.is_gesture_active = True
        self.stop_flag = False
        self.gesture_btn.config(text="⏸ Stop Gesture Control", bg="#cc0000")
        self.show_status("📷 Gesture control started")
        
        # Start gesture recognition in a separate thread
        self.gesture_thread = threading.Thread(target=self.run_gesture_recognition, daemon=True)
        self.gesture_thread.start()
    
    def stop_gesture_control(self):
        """Stop the gesture recognition system"""
        self.stop_flag = True
        self.is_gesture_active = False
        
        if self.cap is not None:
            self.cap.release()
        cv2.destroyAllWindows()
        
        self.gesture_btn.config(text="📷 Start Gesture Control", bg="#0066cc")
        self.show_status("⏸ Gesture control stopped")
    
    def run_gesture_recognition(self):
        """Main gesture recognition loop (from document 1)"""
        # Initialize video capture
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        # Initialize controller and drawer
        self.controller = MainController('models/hand_detector.onnx', 'models/crops_classifier.onnx')
        self.drawer = Drawer()
        debug_mode = True  # Set to False to hide debug info
        
        while self.cap.isOpened() and not self.stop_flag:
            ret, frame = self.cap.read()
            frame = cv2.flip(frame, 1)
            
            if ret:
                start_time = time.time()
                bboxes, ids, labels = self.controller(frame)
                
                if debug_mode:
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
                    
                    fps = 1.0 / (time.time() - start_time)
                    cv2.putText(frame, f"fps {fps:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                
                # Process tracks and handle gestures
                if len(self.controller.tracks) > 0:
                    count_of_zoom = 0
                    thumb_boxes = []
                    
                    for trk in self.controller.tracks:
                        if trk["tracker"].time_since_update < 1:
                            if len(trk['hands']):
                                count_of_zoom += (trk['hands'][-1].gesture == 3)
                                thumb_boxes.append(trk['hands'][-1].bbox)
                                
                                # Blur effect for gesture 23
                                if len(trk['hands']) > 3 and [trk['hands'][-1].gesture, trk['hands'][-2].gesture, trk['hands'][-3].gesture] == [23, 23, 23]:
                                    x, y, x2, y2 = map(int, trk['hands'][-1].bbox)
                                    x, y, x2, y2 = max(x, 0), max(y, 0), max(x2, 0), max(y2, 0)
                                    bbox_area = frame[y:y2, x:x2]
                                    blurred_bbox = cv2.GaussianBlur(bbox_area, (51, 51), 10)
                                    frame[y:y2, x:x2] = blurred_bbox
                            
                            # Handle actions/gestures
                            if trk["hands"].action is not None:
                                self.handle_gesture_action(trk["hands"].action)
                                self.drawer.set_action(trk["hands"].action)
                                
                                # Reset action for non-continuous actions
                                if trk["hands"].action not in [Event.DRAG, Event.DRAG2, Event.DRAG3]:
                                    trk["hands"].action = None
                    
                    if count_of_zoom == 2:
                        self.drawer.draw_two_hands(frame, thumb_boxes)
                
                
                frame = self.drawer.draw(frame)
                cv2.imshow("Gesture Control", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    self.stop_flag = True
                    break
        
        if self.cap is not None:
            self.cap.release()
        cv2.destroyAllWindows()
    
    def handle_gesture_action(self, action):
        """Map gesture actions to music controls"""
        if action in [Event.SWIPE_LEFT, Event.SWIPE_LEFT2, Event.SWIPE_LEFT3]:
            print("Gesture: Swipe Left - Previous Track")
            self.next_track()
        
        elif action in [Event.SWIPE_RIGHT, Event.SWIPE_RIGHT2, Event.SWIPE_RIGHT3]:
            print("Gesture: Swipe Right - Next Track")
            self.previous_track()
        
        elif action in [Event.SWIPE_UP, Event.SWIPE_UP2, Event.SWIPE_UP3]:
            print("Gesture: Swipe Up - Volume Up")
            self.volume_up()
        
        elif action in [Event.SWIPE_DOWN, Event.SWIPE_DOWN2, Event.SWIPE_DOWN3]:
            print("Gesture: Swipe Down - Volume Down")
            self.volume_down()
        
        elif action == Event.TAP or action == Event.DOUBLE_TAP:
            print("Gesture: Tap - Play/Pause")
            self.play_pause()
        
        elif action == Event.FAST_SWIPE_UP:
            print("Gesture: Fast Swipe Up")
            self.volume_up()
        
        elif action == Event.FAST_SWIPE_DOWN:
            print("Gesture: Fast Swipe Down")
            self.volume_down()
    
    def show_status(self, message):
        self.status_label.config(text=message)
        self.root.after(2000, lambda: self.status_label.config(text="Ready"))
    
    def play_pause(self):
        self.keyboard.press(Key.media_play_pause)
        self.keyboard.release(Key.media_play_pause)
        print("Play/Pause toggled")
        self.show_status("⏯ Play/Pause toggled")
    
    def next_track(self):
        self.keyboard.press(Key.media_next)
        self.keyboard.release(Key.media_next)
        self.show_status("⏭ Skipped to next track")
    
    def previous_track(self):
        self.keyboard.press(Key.media_previous)
        self.keyboard.release(Key.media_previous)
        self.show_status("⏮ Previous track")
    
    def volume_up(self):
        self.keyboard.press(Key.media_volume_up)
        self.keyboard.release(Key.media_volume_up)
        self.show_status("🔊 Volume increased")
    
    def volume_down(self):
        self.keyboard.press(Key.media_volume_down)
        self.keyboard.release(Key.media_volume_down)
        self.show_status("🔉 Volume decreased")
    
    def on_closing(self):
        if self.is_gesture_active:
            self.stop_gesture_control()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = MediaMusicController(root)
    root.mainloop()


if __name__ == "__main__":
    main()