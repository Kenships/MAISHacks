import tkinter as tk
from tkinter import ttk
from pynput.keyboard import Key, Controller
import numpy as np
import cv2
import time
import threading
import queue
from PIL import Image, ImageTk

from main_controller import MainController
from utils import Drawer, Event, targets
import warnings
from circle_visualizer import AudioRingVisualizer
from media_info import MediaInfo
warnings.filterwarnings("ignore", category=RuntimeWarning, module="soundcard")


class MediaMusicController:
    def __init__(self, root):
        self.root = root
        self.root.title("Media Music Controller with Gestures")
        self.root.geometry("800x700")
        self.root.configure(bg="#181818")

        self.keyboard = Controller()
        self.is_gesture_active = False
        self.gesture_thread = None
        self.stop_flag = False

        self.controller = None
        self.drawer = None
        self.cap = None
        self.pixel_img = tk.PhotoImage(width=1, height=1)

        self.bottom_frame = tk.Frame(self.root, bg="#282828", bd=1, relief="solid")
        self.bottom_frame.pack(fill=tk.X, side=tk.BOTTOM, ipady=10, padx=10, pady=10)

        media_info_frame = tk.Frame(self.bottom_frame, bg="#282828")
        self.controls_frame = tk.Frame(self.bottom_frame, bg="#282828")
        self.controls_frame.pack(pady=10)

        # ✅ --- Add visualizer area on top ---
        self.visualizer_frame = tk.Frame(self.root, width=300, height=200, bg="#181818")
        self.visualizer_frame.pack(pady=10)
        self.visualizer_frame.pack_propagate(False)

        viz_size = 200
        self.visualizer = AudioRingVisualizer(self.visualizer_frame, size=viz_size, fps=60)
        self.visualizer.show()
        self.visualizer.start()
        # --------------------------------------

        # Title
        title = tk.Label(
            root,
            text="🎵 Spotify Music Controller",
            font=("Arial", 18, "bold"),
            bg="#282828",
            fg="#ffffff"
        )
        title.pack(pady=10)
        button_config = {
            "font": ("Arial", 12, "bold"), 
            "fg": "white", 
            "bd": 0, 
            "cursor": "hand2",
            "image": self.pixel_img,
            "width": 180, 
            "height": 40,
            "compound": "c"
        }

        # Gesture control button
        self.gesture_btn = tk.Button(
            root,
            text="📷 Start Gesture Control",
            command=self.toggle_gesture_control,
            bg="#00aa00",
            activebackground="#008800",
            activeforeground="white",
            **button_config
        )
        self.gesture_btn.pack(pady=10)

        # --- Media Info State ---
        self.media_info = MediaInfo()
        self.media_queue = queue.Queue()
        self.media_poll_thread = None
        self.polling_media = False

        # --- Smaller camera feed ---
        self.CAM_WIDTH = 640
        self.CAM_HEIGHT = 480

        # --- Top frame (camera/visualizer container) ---
        self.camera_frame = tk.Frame(self.root, width=self.CAM_WIDTH, height=self.CAM_HEIGHT, bg="#282828")
        self.camera_frame.pack(pady=20, padx=20)
        self.camera_frame.pack_propagate(False)

        self.camera_feed_label = tk.Label(self.camera_frame, bg="black")
        self.camera_placeholder_label = tk.Label(self.camera_frame, text="",
                                                 font=("Arial", 12),
                                                 bg="black", fg="white")
        text_info_frame = tk.Frame(media_info_frame, bg="#282828")
        text_info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5) # <-- Re-added side=tk.LEFT
        self.song_title_label = tk.Label(text_info_frame, text="No Song Playing",
                                             font=("Arial", 16, "bold"), 
                                             bg="#282828", fg="#ffffff", anchor="w") # <-- Re-added anchor="w"
        self.song_title_label.pack(fill=tk.X) # <-- Re-added fill=tk.X

        self.artist_label = tk.Label(text_info_frame, text="---",
                                         font=("Arial", 12), 
                                         bg="#282828", fg="#aaaaaa", anchor="w") # <-- Re-added anchor="w"
        self.artist_label.pack(fill=tk.X) # <-- Re-added fill=tk.X

        # Buttons
        button_frame = tk.Frame(root, bg="#282828")
        button_frame.pack(pady=10)
        self.controls_frame = tk.Frame(self.bottom_frame, bg="#282828")

         # --- Bigger buttons/font ---
       

        # self.start_cam_btn = tk.Button(self.controls_frame,
        #                                text="📷 Start Camera",
        #                                command=self.toggle_gesture_control,
        #                                bg="#00aa00", activebackground="#008800", **button_config)
        # self.start_cam_btn.grid(row=0, column=0, padx=5)

        # self.stop_cam_btn = tk.Button(self.controls_frame,
        #                               text="⏹ Stop Camera",
        #                               command=self.toggle_gesture_control,
        #                               bg="#cc0000", activebackground="#aa0000", **button_config)


        self.status_label = tk.Label(self.bottom_frame, text="Ready",
                                     font=("Arial", 10),
                                     bg="#282828", fg="#00ff00")
        self.status_label.pack(pady=(0, 10))
######################## Sidney old code#########################
        # button_config = {
        #     "font": ("Arial", 10),
        #     "width": 10,
        #     "height": 2,
        #     "bg": "#ff0000",
        #     "fg": "white",
        #     "activebackground": "#cc0000",
        #     "activeforeground": "white",
        #     "border": 0,
        #     "cursor": "hand2"
        # }

        # self.prev_btn = tk.Button(button_frame, text="⏮ Previous", command=self.previous_track, **button_config)
        # self.prev_btn.grid(row=0, column=0, padx=3, pady=5)

        # self.play_btn = tk.Button(button_frame, text="⏯ Play/Pause", command=self.play_pause, **button_config)
        # self.play_btn.grid(row=0, column=1, padx=3, pady=5)

        # self.next_btn = tk.Button(button_frame, text="⏭ Next", command=self.next_track, **button_config)
        # self.next_btn.grid(row=0, column=2, padx=3, pady=5)

        # volume_frame = tk.Frame(root, bg="#282828")
        # volume_frame.pack(pady=5)

        # self.vol_down_btn = tk.Button(volume_frame, text="🔉 Vol Down", command=self.volume_down, **button_config)
        # self.vol_down_btn.grid(row=0, column=0, padx=3)

        # self.vol_up_btn = tk.Button(volume_frame, text="🔊 Vol Up", command=self.volume_up, **button_config)
        # self.vol_up_btn.grid(row=0, column=1, padx=3)

        # self.status_label = tk.Label(
        #     root,
        #     text="Ready - Click 'Start Gesture Control' to begin",
        #     font=("Arial", 9),
        #     bg="#282828",
        #     fg="#00ff00"
        # )
        # self.status_label.pack(pady=10)

        # info_text = "Gestures: Swipe Left/Right = Prev/Next | Swipe Up/Down = Vol"
        # self.info_label = tk.Label(
        #     root,
        #     text=info_text,
        #     font=("Arial", 8),
        #     bg="#282828",
        #     fg="#aaaaaa"
        # )
        # self.info_label.pack(pady=5)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # --- rest of your original methods unchanged ---
    def toggle_gesture_control(self):
        if not self.is_gesture_active:
            self.start_gesture_control()
        else:
            self.stop_gesture_control()

    def start_gesture_control(self):
        self.is_gesture_active = True
        self.stop_flag = False
        self.gesture_btn.config(text="⏸ Stop Gesture Control", bg="#cc0000")
        self.show_status("📷 Gesture control started")

        self.gesture_thread = threading.Thread(target=self.run_gesture_recognition, daemon=True)
        self.gesture_thread.start()

    def stop_gesture_control(self):
        self.stop_flag = True
        self.is_gesture_active = False
        if self.cap is not None:
            self.cap.release()
        cv2.destroyAllWindows()
        self.gesture_btn.config(text="📷 Start Gesture Control", bg="#0066cc")
        self.show_status("⏸ Gesture control stopped")

    def run_gesture_recognition(self):
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.controller = MainController('models/hand_detector.onnx', 'models/crops_classifier.onnx')
        self.drawer = Drawer()
        debug_mode = True
        while self.cap.isOpened() and not self.stop_flag:
            ret, frame = self.cap.read()
            frame = cv2.flip(frame, 1)
            if ret:
                start_time = time.time()
                bboxes, ids, labels = self.controller(frame)
                if debug_mode and bboxes is not None:
                    bboxes = bboxes.astype(np.int32)
                    for i in range(bboxes.shape[0]):
                        box = bboxes[i, :]
                        gesture = targets[labels[i]] if labels[i] is not None else "None"
                        cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), (255, 255, 0), 4)
                        cv2.putText(frame, f"ID {ids[i]} : {gesture}",
                                    (box[0], box[1] - 10), cv2.FONT_HERSHEY_SIMPLEX,
                                    1, (0, 0, 255), 2)
                    fps = 1.0 / ((time.time() - start_time) + 0.00001)
                    cv2.putText(frame, f"fps {fps:.2f}", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                if len(self.controller.tracks) > 0:
                    for trk in self.controller.tracks:
                        if trk["tracker"].time_since_update < 1 and len(trk['hands']):
                            if trk["hands"].action is not None:
                                self.handle_gesture_action(trk["hands"].action)
                                self.drawer.set_action(trk["hands"].action)
                                if trk["hands"].action not in [Event.DRAG, Event.DRAG2, Event.DRAG3]:
                                    trk["hands"].action = None
                frame = self.drawer.draw(frame)
                cv2.imshow("Gesture Control", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    self.stop_flag = True
                    break
        if self.cap is not None:
            self.cap.release()
        cv2.destroyAllWindows()

    def handle_gesture_action(self, action):
        if action in [Event.SWIPE_LEFT, Event.SWIPE_LEFT2, Event.SWIPE_LEFT3]:
            self.next_track()
        elif action in [Event.SWIPE_RIGHT, Event.SWIPE_RIGHT2, Event.SWIPE_RIGHT3]:
            self.previous_track()
        elif action in [Event.SWIPE_UP, Event.SWIPE_UP2, Event.SWIPE_UP3]:
            self.volume_up()
        elif action in [Event.SWIPE_DOWN, Event.SWIPE_DOWN2, Event.SWIPE_DOWN3]:
            self.volume_down()
        elif action == Event.TAP or action == Event.DOUBLE_TAP:
            self.play_pause()

    def show_status(self, message):
        self.status_label.config(text=message)
        self.root.after(2000, lambda: self.status_label.config(text="Ready"))

    def play_pause(self):
        self.keyboard.press(Key.media_play_pause)
        self.keyboard.release(Key.media_play_pause)
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
