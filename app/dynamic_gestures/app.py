import tkinter as tk
from tkinter import ttk
from pynput.keyboard import Key, Controller
import numpy as np
import cv2
import time
import threading
import queue
from PIL import Image, ImageTk
import io
import requests

from main_controller import MainController
from utils import Drawer, Event, targets
import warnings
from circle_visualizer import AudioRingVisualizer
from media_info import MediaInfo
warnings.filterwarnings("ignore", category=RuntimeWarning, module="soundcard")


class MediaMusicController:
    def __init__(self, root):
        self.root = root
        self.root.title("Gesture Control Media Player")
        # --- Smaller window to fit new elements ---
        self.root.geometry("800x700")
        self.root.configure(bg="#181818")

        self.pixel_img = tk.PhotoImage(width=1, height=1)

        # --- Camera State ---
        self.camera_on = False
        self.camera_visible = False
        self.cap = None
        # --- Smaller camera feed ---
        self.CAM_WIDTH = 640
        self.CAM_HEIGHT = 480
        self.keyboard = Controller()
        self.is_gesture_active = False
        self.gesture_thread = None
        self.stop_flag = False

        # --- Media Info State ---
        self.media_info = MediaInfo()
        self.media_queue = queue.Queue()
        self.media_poll_thread = None
        self.polling_media = False

        # --- Top frame (camera/visualizer container) ---
        self.camera_frame = tk.Frame(self.root, width=self.CAM_WIDTH, height=self.CAM_HEIGHT, bg="#282828")
        self.camera_frame.pack(pady=20, padx=20)
        self.camera_frame.pack_propagate(False)

        # --- Two-Label Fix ---
        self.camera_feed_label = tk.Label(self.camera_frame, bg="black")
        self.camera_placeholder_label = tk.Label(self.camera_frame, text="",
                                                 font=("Arial", 12),
                                                 bg="black", fg="white")
        self.camera_placeholder_label.pack(expand=True)
        # self.set_camera_placeholder("Press 'Start Camera' to begin")

        # --- Visualizer instance in the SAME area ---
        viz_size = min(self.CAM_WIDTH, self.CAM_HEIGHT)
        self.visualizer = AudioRingVisualizer(self.camera_frame, size=viz_size, fps=60)
        self.visualizer.show()
        self.visualizer.start()
        # Initially hidden; will be shown when camera is off

        # --- Bottom Frame (controls + song info) ---
        self.bottom_frame = tk.Frame(self.root, bg="#282828", bd=1, relief="solid")
        self.bottom_frame.pack(fill=tk.X, side=tk.BOTTOM, ipady=10, padx=10, pady=10)

        media_info_frame = tk.Frame(self.bottom_frame, bg="#282828")
        media_info_frame.pack(pady=(10, 0), padx=10, fill=tk.X) # <-- Re-added fill=tk.X

        # --- Larger placeholder ---
        pil_placeholder = Image.new("RGB", (120, 120), color="#282828")
        self.placeholder_img = ImageTk.PhotoImage(pil_placeholder)

        self.album_art_label = tk.Label(media_info_frame, image=self.placeholder_img,
                                         bg="#282828", bd=0)
        self.album_art_label.pack(side=tk.LEFT, padx=(0, 10)) # <-- Re-added side=tk.LEFT
        self.album_art_label.image = self.placeholder_img # Anchor the placeholder

        # Text info
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

        # Controls
        self.controls_frame = tk.Frame(self.bottom_frame, bg="#282828")
        self.controls_frame.pack(pady=10)

        # --- Bigger buttons/font ---
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

        self.gesture_btn = tk.Button(self.controls_frame,
                                       text="📷 Start Camera",
                                       command=self.toggle_gesture_control,
                                       bg="#00aa00", activebackground="#008800", **button_config)
        self.gesture_btn.grid(row=0, column=0, padx=5)
        self.update_camera_feed()
        self.start_media_polling()
        # self.stop_cam_btn = tk.Button(self.controls_frame,
        #                               text="⏹ Stop Camera",
        #                               command=self.stop_camera,
        #                               bg="#cc0000", activebackground="#aa0000", **button_config)

        # self.toggle_view_btn = tk.Button(self.controls_frame,
        #                                  text="🙈 Hide Feed",
        #                                  command=self.toggle_camera_view,
        #                                  bg="#ff8c00", activebackground="#dd7700", **button_config)

        # self.simulate_btn = tk.Button(self.controls_frame,
        #                               text="✋ Simulate Gesture",
        #                               command=lambda: self.on_hand_symbol_detected("SIMULATED"),
        #                               bg="#5a0099", activebackground="#4a0088", **button_config)
        # self.simulate_btn.grid(row=0, column=1, padx=5)

        self.status_label = tk.Label(self.bottom_frame, text="Ready",
                                     font=("Arial", 10),
                                     bg="#282828", fg="#00ff00")
        self.status_label.pack(pady=(0, 10))

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
                            gesture_id = trk['hands'][-1].gesture
                            gesture_name = targets[gesture_id] if gesture_id is not None else None
                            if gesture_name in ["part_hand_heart", "part_hand_heart2"]:
                                self.handle_gesture_action(-1000,gesture_name)
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

    def handle_gesture_action(self, action, gesture="None"):
        print("gesture", gesture)
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
        elif gesture == "part_hand_heart" or  gesture == "part_hand_heart2":
            self.media_info.like_current_song() 

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

    # ---------- Media polling ----------
    def start_media_polling(self):
        if self.polling_media:
            return
        self.polling_media = True
        self.media_poll_thread = threading.Thread(target=self._run_media_polling_loop, daemon=True)
        self.media_poll_thread.start()

    def stop_media_polling(self):
        if not self.polling_media:
            return
        self.polling_media = False
        if self.media_poll_thread:
            self.media_poll_thread.join(timeout=1.0)
            self.media_poll_thread = None

    def _run_media_polling_loop(self):
        while self.polling_media:
            try:
                info = self.media_info.get()
                self.media_queue.put(info)
            except Exception as e:
                print(f"Error in media info thread: {e}")
                self.media_queue.put(None)
            time.sleep(2)

    def check_media_queue(self):
        try:
            while not self.media_queue.empty():
                info = self.media_queue.get_nowait()
                self.update_media_ui(info)
        except queue.Empty:
            pass

    def update_media_ui(self, info):
        # 1) Text labels
        if info and info.get('title'):
            title = info.get('title', 'Unknown Title')
            artist = info.get('artist', 'Unknown Artist')
            if len(title) > 40:
                title = title[:40] + "..."
            self.song_title_label.config(text=title)
            self.artist_label.config(text=artist)
        else:
            self.song_title_label.config(text="No Media Playing")
            self.artist_label.config(text="---")

        # --- 2. Update Album Art (Spotipy URL Method) ---
        
        album_art_url = info.get("album_art_url") if info else None
        
        
        if album_art_url:
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(album_art_url, headers=headers, stream=True)
                
                if response.status_code != 200:
                    raise Exception(f"Failed to download image: {response.status_code}")

                image_bytes = response.raw.read()
                image_stream = io.BytesIO(image_bytes)
                pil_img = Image.open(image_stream)
                
                # --- Resize to new 120x120 size ---
                pil_img = pil_img.resize((120, 120), Image.LANCZOS)
                
                img_tk = ImageTk.PhotoImage(image=pil_img)
                
                self.album_art_label.config(image=img_tk)
                self.album_art_label.image = img_tk 
                
            except Exception as e:
                print(f"Error processing thumbnail URL: {e}")
                self.album_art_label.config(image=self.placeholder_img)
                self.album_art_label.image = self.placeholder_img
        else:
            self.album_art_label.config(image=self.placeholder_img)
            self.album_art_label.image = self.placeholder_img 


    # ---------- Helpers ----------
    def show_status(self, message, is_error=False):
        color = "#ff0000" if is_error else "#00ff00"
        self.status_label.config(text=message, fg=color)

    def on_closing(self):
        # Always clean up both camera and visualizer

        self.stop_media_polling()
        if self.camera_on:
            try:
                self.cap.release()
            except Exception:
                pass
        self.root.destroy()

    def update_camera_feed(self):
            # if not self.camera_on:
            #     return
        self.check_media_queue()
        self.root.after(10, self.update_camera_feed)  # Loop

    # i

def main():
    root = tk.Tk()
    app = MediaMusicController(root)
    root.mainloop()


if __name__ == "__main__":
    main()
