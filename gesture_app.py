import tkinter as tk
import cv2
from PIL import Image, ImageTk # We need ImageTk
import threading
import queue
import time
import io
import requests
from media_info import MediaInfo

class HandGestureApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gesture Control Media Player")
        self.root.geometry("800x700")
        self.root.configure(bg="#181818") # Dark background

        # --- Camera State ---
        self.camera_on = False
        self.camera_visible = False
        self.cap = None
        self.CAM_WIDTH = 640
        self.CAM_HEIGHT = 480

        # --- Media Info State ---
        self.media_info = MediaInfo()
        self.media_queue = queue.Queue()
        self.media_poll_thread = None
        self.polling_media = False

        # --- Top Frame (for Camera) ---
        self.camera_frame = tk.Frame(root, width=self.CAM_WIDTH, height=self.CAM_HEIGHT,
                                      bg="black")
        self.camera_frame.pack(pady=20, padx=20)
        self.camera_frame.pack_propagate(False)

        # --- Two-Label Fix ---
        # Label for the video feed (initially hidden)
        self.camera_feed_label = tk.Label(self.camera_frame, bg="black")
        
        # Label for the placeholder text
        self.camera_placeholder_label = tk.Label(self.camera_frame, text="",
                                                  font=("Arial", 12),
                                                  bg="black", fg="white")
        self.camera_placeholder_label.pack(expand=True)
        
        self.set_camera_placeholder("Press 'Start Camera' to begin")

        # --- Bottom Frame (for Controls & Song Info) ---
        self.bottom_frame = tk.Frame(root, bg="#282828", bd=1, relief="solid")
        self.bottom_frame.pack(fill=tk.X, side=tk.BOTTOM, ipady=10, padx=10, pady=10)

        # --- Create a main frame for media info (art + text) ---
        media_info_frame = tk.Frame(self.bottom_frame, bg="#282828")
        media_info_frame.pack(pady=(10, 0), padx=10, fill=tk.X)

        # --- Create placeholder image ---
        pil_placeholder = Image.new("RGB", (100, 100), color="#282828")
        self.placeholder_img = ImageTk.PhotoImage(pil_placeholder)

        # --- Album Art Label ---
        self.album_art_label = tk.Label(media_info_frame, image=self.placeholder_img,
                                         bg="#282828", bd=0)
        self.album_art_label.pack(side=tk.LEFT, padx=(0, 10))
        self.album_art_label.image = self.placeholder_img # Anchor the placeholder

        # --- Frame for the text, to the right of the art ---
        text_info_frame = tk.Frame(media_info_frame, bg="#282828")
        text_info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # --- Song Info ---
        self.song_title_label = tk.Label(text_info_frame, text="No Song Playing",
                                             font=("Arial", 16, "bold"), 
                                             bg="#282828", fg="#ffffff", anchor="w")
        self.song_title_label.pack(fill=tk.X)

        self.artist_label = tk.Label(text_info_frame, text="---",
                                         font=("Arial", 12), 
                                         bg="#282828", fg="#aaaaaa", anchor="w")
        self.artist_label.pack(fill=tk.X)

        # --- Control Buttons ---
        self.controls_frame = tk.Frame(self.bottom_frame, bg="#282828")
        self.controls_frame.pack(pady=10)

        button_config = {"font": ("Arial", 10), "width": 20, "height": 2,
                         "fg": "white", "bd": 0, "cursor": "hand2"}

        self.start_cam_btn = tk.Button(self.controls_frame,
                                           text="📷 Start Camera",
                                           command=self.start_camera,
                                           bg="#00aa00", activebackground="#008800", **button_config)
        self.start_cam_btn.grid(row=0, column=0, padx=5)

        self.stop_cam_btn = tk.Button(self.controls_frame,
                                          text="⏹ Stop Camera",
                                          command=self.stop_camera,
                                          bg="#cc0000", activebackground="#aa0000", **button_config)

        self.toggle_view_btn = tk.Button(self.controls_frame,
                                             text="🙈 Hide Feed",
                                             command=self.toggle_camera_view,
                                             bg="#ff8c00", activebackground="#dd7700", **button_config)

        self.simulate_btn = tk.Button(self.controls_frame,
                                          text="✋ Simulate Gesture",
                                          command=lambda: self.on_hand_symbol_detected("SIMULATED"),
                                          bg="#5a0099", activebackground="#4a0088", **button_config)
        self.simulate_btn.grid(row=0, column=1, padx=5)

        self.status_label = tk.Label(self.bottom_frame, text="Ready",
                                         font=("Arial", 10), 
                                         bg="#282828", fg="#00ff00")
        self.status_label.pack(pady=(0, 10))

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def set_camera_placeholder(self, text):
        """Shows the text label and hides the video label."""
        self.camera_feed_label.pack_forget() # Hide video
        self.camera_placeholder_label.config(text=text)
        self.camera_placeholder_label.pack(expand=True) # Show text
        
    def start_camera(self):
        if self.camera_on: return

        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                raise Exception("Cannot open webcam")

            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.CAM_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.CAM_HEIGHT)

            self.camera_on = True
            self.camera_visible = True
            
            # Hide placeholder, show video label
            self.camera_placeholder_label.pack_forget()
            self.camera_feed_label.pack(expand=True)

            self.start_cam_btn.grid_forget() # Use grid_forget()
            self.simulate_btn.grid(row=0, column=2, padx=5)
            self.stop_cam_btn.grid(row=0, column=0, padx=5)
            self.toggle_view_btn.grid(row=0, column=1, padx=5)
            self.toggle_view_btn.config(text="🙈 Hide Feed")

            self.show_status("Camera started. Looking for gestures...")
            self.update_camera_feed()
            self.start_media_polling()

        except Exception as e:
            self.set_camera_placeholder(f"Error: {e}")
            self.show_status(f"Error: {e}", is_error=True)

    def stop_camera(self):
        self.stop_media_polling()
        self.camera_on = False
        self.camera_visible = False
        if self.cap:
            self.cap.release()
            self.cap = None

        self.stop_cam_btn.grid_forget()
        self.toggle_view_btn.grid_forget()
        self.simulate_btn.grid(row=0, column=1, padx=5)
        self.start_cam_btn.grid(row=0, column=0, padx=5)

        self.set_camera_placeholder("Camera feed stopped.")
        self.show_status("Camera stopped.")
        self.update_media_ui(None)

    def toggle_camera_view(self):
        self.camera_visible = not self.camera_visible

        if self.camera_visible:
            self.toggle_view_btn.config(text="🙈 Hide Feed")
            # Show video, hide text
            self.camera_placeholder_label.pack_forget()
            self.camera_feed_label.pack(expand=True)
        else:
            self.toggle_view_btn.config(text="🙉 Show Feed")
            self.set_camera_placeholder("Feed hidden. Gestures are still active.")

    def update_camera_feed(self):
        if not self.camera_on:
            return

        self.check_media_queue()

        ret, frame = self.cap.read()

        if ret:
            # -----------------------------------------------------------------
            # 🤖 AI INTEGRATION POINT 🤖
            # -----------------------------------------------------------------

            if self.camera_visible:
                frame_flipped = cv2.flip(frame, 1)
                cv_rgb = cv2.cvtColor(frame_flipped, cv2.COLOR_BGR2RGB)
                
                pil_img = Image.fromarray(cv_rgb)
                # Use standard ImageTk.PhotoImage
                img_tk = ImageTk.PhotoImage(image=pil_img)

                self.camera_feed_label.config(image=img_tk, text="")
                self.camera_feed_label.image = img_tk # Anchor image

        self.root.after(10, self.update_camera_feed)  # Loop

    def on_hand_symbol_detected(self, gesture):
        self.show_status(f"Gesture Detected: {gesture}")
        self.artist_label.config(text=f"Last Gesture: {gesture}")

    # --- Media Polling Functions (No changes) ---

    def start_media_polling(self):
        if self.polling_media: return
        print("Starting media polling thread...")
        self.polling_media = True
        self.media_poll_thread = threading.Thread(target=self._run_media_polling_loop, daemon=True)
        self.media_poll_thread.start()

    def stop_media_polling(self):
        if not self.polling_media: return
        print("Stopping media polling thread...")
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
        # --- 1. Update Text Labels ---
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
                pil_img = pil_img.resize((100, 100), Image.LANCZOS)
                
                # Use standard ImageTk.PhotoImage
                img_tk = ImageTk.PhotoImage(image=pil_img)
                
                self.album_art_label.config(image=img_tk)
                self.album_art_label.image = img_tk # Anchor image
                
            except Exception as e:
                print(f"Error processing thumbnail URL: {e}")
                self.album_art_label.config(image=self.placeholder_img)
                self.album_art_label.image = self.placeholder_img
        else:
            self.album_art_label.config(image=self.placeholder_img)
            self.album_art_label.image = self.placeholder_img # Anchor placeholder

    # --- Helper functions ---

    def show_status(self, message, is_error=False):
        color = "#ff0000" if is_error else "#00ff00"
        self.status_label.config(text=message, fg=color)

    def on_closing(self):
        self.stop_media_polling()
        if self.camera_on:
            self.stop_camera()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = HandGestureApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()