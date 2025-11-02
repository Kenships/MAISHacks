import customtkinter as ctk
import cv2
from PIL import Image, ImageTk
import threading
import queue
import time
import io
import requests
from media_info import MediaInfo


class HandGestureApp:
    def __init__(self, root):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.root = root
        self.root.title("Gesture Control Media Player")
        self.root.geometry("800x700")

        # --- Camera State ---
        self.camera_on = False
        self.camera_visible = False
        self.cap = None
        self.CAM_WIDTH = 640
        self.CAM_HEIGHT = 440

        # --- Media Info State ---
        self.media_info = MediaInfo()
        self.media_queue = queue.Queue()
        self.media_poll_thread = None
        self.polling_media = False

        # --- Top Frame (for Camera) ---
        self.camera_frame = ctk.CTkFrame(root, width=self.CAM_WIDTH, height=self.CAM_HEIGHT, fg_color="black")
        self.camera_frame.pack(pady=20, padx=20)
        self.camera_frame.pack_propagate(False)

        # Label for video feed
        self.camera_feed_label = ctk.CTkLabel(self.camera_frame, text="", fg_color="black")

        # Placeholder label
        self.camera_placeholder_label = ctk.CTkLabel(self.camera_frame, text="", font=("Arial", 12))
        self.camera_placeholder_label.pack(expand=True, fill="both")
        self.set_camera_placeholder("Press 'Start Camera' to begin")

        # --- Bottom Frame (Controls + Media Info) ---
        self.bottom_frame = ctk.CTkFrame(root, fg_color="#282828", corner_radius=10)
        self.bottom_frame.pack(fill="x", side="bottom", padx=10, pady=10)

        # --- Media Info Frame ---
        media_info_frame = ctk.CTkFrame(self.bottom_frame, fg_color="#282828", corner_radius=0)
        media_info_frame.pack(pady=(10, 0), padx=10, fill="x")

        # Placeholder album art
        pil_placeholder = Image.new("RGB", (100, 100), color="#282828")
        self.placeholder_img = ImageTk.PhotoImage(pil_placeholder)

        # Album art label
        self.album_art_label = ctk.CTkLabel(media_info_frame, image=self.placeholder_img, fg_color="#282828")
        self.album_art_label.pack(side="left", padx=(0, 10))
        self.album_art_label.image = self.placeholder_img

        # Text info frame
        text_info_frame = ctk.CTkFrame(media_info_frame, fg_color="#282828", corner_radius=5)
        text_info_frame.pack(side="left", fill="both", expand=True, padx=5)


        # Song info
        self.song_title_label = ctk.CTkLabel(text_info_frame, text="No Song Playing",
                                             font=("Arial", 16, "bold"), anchor="w", fg_color="#282828")
        self.song_title_label.pack(fill="x")
        self.artist_label = ctk.CTkLabel(text_info_frame, text="---",
                                         font=("Arial", 12), anchor="w", fg_color="#282828")
        self.artist_label.pack(fill="x")

        # --- Controls Frame ---
        self.controls_frame = ctk.CTkFrame(self.bottom_frame, fg_color="#282828", corner_radius=0)
        self.controls_frame.pack(pady=10)

        # Buttons
        self.start_cam_btn = ctk.CTkButton(self.controls_frame, text="📷 Start Camera",
                                           command=self.start_camera, corner_radius=15,
                                           fg_color="#00aa00", hover_color="#008800")
        self.start_cam_btn.grid(row=0, column=0, padx=5)

        self.stop_cam_btn = ctk.CTkButton(self.controls_frame, text="⏹ Stop Camera",
                                          command=self.stop_camera, corner_radius=15,
                                          fg_color="#cc0000", hover_color="#aa0000")

        self.toggle_view_btn = ctk.CTkButton(self.controls_frame, text="🙈 Hide Feed",
                                             command=self.toggle_camera_view, corner_radius=15,
                                             fg_color="#ff8c00", hover_color="#dd7700")

        self.simulate_btn = ctk.CTkButton(self.controls_frame, text="✋ Simulate Gesture",
                                          command=lambda: self.on_hand_symbol_detected("SIMULATED"),
                                          corner_radius=15, fg_color="#5a0099", hover_color="#4a0088")
        self.simulate_btn.grid(row=0, column=1, padx=5)

        # Status label
        self.status_label = ctk.CTkLabel(self.bottom_frame, text="Ready", font=("Arial", 10),
                                         fg_color="#282828", text_color="#00ff00")
        self.status_label.pack(pady=(0, 10))

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # --- Camera Placeholder ---
    def set_camera_placeholder(self, text):
        self.camera_feed_label.pack_forget()
        self.camera_placeholder_label.configure(text=text)
        self.camera_placeholder_label.pack(expand=True)

    # --- Camera Functions ---
    def start_camera(self):
        if self.camera_on: return
        try:
            self.cap = cv2.VideoCapture(1)
            if not self.cap.isOpened():
                raise Exception("Cannot open webcam")
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.CAM_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.CAM_HEIGHT)

            self.camera_on = True
            self.camera_visible = True

            self.camera_placeholder_label.pack_forget()
            self.camera_feed_label.pack(expand=True)

            self.start_cam_btn.grid_forget()
            self.simulate_btn.grid(row=0, column=2, padx=5)
            self.stop_cam_btn.grid(row=0, column=0, padx=5)
            self.toggle_view_btn.grid(row=0, column=1, padx=5)
            self.toggle_view_btn.configure(text="🙈 Hide Feed")

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
            self.toggle_view_btn.configure(text="🙈 Hide Feed")
            self.camera_placeholder_label.pack_forget()
            self.camera_feed_label.pack(expand=True)
        else:
            self.toggle_view_btn.configure(text="🙉 Show Feed")
            self.set_camera_placeholder("Feed hidden. Gestures are still active.")

    def update_camera_feed(self):
        if not self.camera_on:
            return

        self.check_media_queue()

        ret, frame = self.cap.read()
        if ret and self.camera_visible:
            frame_flipped = cv2.flip(frame, 1)
            cv_rgb = cv2.cvtColor(frame_flipped, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(cv_rgb)
            # Resize image to fit label
            label_width = self.camera_feed_label.winfo_width()
            label_height = self.camera_feed_label.winfo_height()

            if label_width > 0 and label_height > 0:
                pil_img = pil_img.resize((1440, 960), Image.LANCZOS)
            img_tk = ImageTk.PhotoImage(image=pil_img)
            self.camera_feed_label.configure(image=img_tk, text="")
            self.camera_feed_label.image = img_tk

        self.root.after(10, self.update_camera_feed)

    # --- Gesture ---
    def on_hand_symbol_detected(self, gesture):
        self.show_status(f"Gesture Detected: {gesture}")
        self.artist_label.configure(text=f"Last Gesture: {gesture}")

    # --- Media Polling ---
    def start_media_polling(self):
        if self.polling_media: return
        self.polling_media = True
        self.media_poll_thread = threading.Thread(target=self._run_media_polling_loop, daemon=True)
        self.media_poll_thread.start()

    def stop_media_polling(self):
        if not self.polling_media: return
        self.polling_media = False
        if self.media_poll_thread:
            self.media_poll_thread.join(timeout=1.0)
            self.media_poll_thread = None

    def _run_media_polling_loop(self):
        while self.polling_media:
            try:
                info = self.media_info.get()
                self.media_queue.put(info)
            except:
                self.media_queue.put(None)
            time.sleep(2)

    def check_media_queue(self):
        while not self.media_queue.empty():
            info = self.media_queue.get_nowait()
            self.update_media_ui(info)

    # --- Update UI ---
    def update_media_ui(self, info):
        if info and info.get('title'):
            title = info.get('title', 'Unknown Title')
            artist = info.get('artist', 'Unknown Artist')
            if len(title) > 40:
                title = title[:40] + "..."
            self.song_title_label.configure(text=title)
            self.artist_label.configure(text=artist)
        else:
            self.song_title_label.configure(text="No Media Playing")
            self.artist_label.configure(text="---")

        album_art_url = info.get("album_art_url") if info else None
        if album_art_url:
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(album_art_url, headers=headers, stream=True)
                if response.status_code != 200:
                    raise Exception(f"Failed to download image: {response.status_code}")
                image_bytes = response.raw.read()
                pil_img = Image.open(io.BytesIO(image_bytes)).resize((100, 100), Image.LANCZOS)
                img_tk = ImageTk.PhotoImage(pil_img)
                self.album_art_label.configure(image=img_tk)
                self.album_art_label.image = img_tk
            except:
                self.album_art_label.configure(image=self.placeholder_img)
                self.album_art_label.image = self.placeholder_img
        else:
            self.album_art_label.configure(image=self.placeholder_img)
            self.album_art_label.image = self.placeholder_img

    # --- Status Helper ---
    def show_status(self, message, is_error=False):
        color = "#ff0000" if is_error else "#00ff00"
        self.status_label.configure(text=message, text_color=color)

    # --- Closing ---
    def on_closing(self):
        self.stop_media_polling()
        if self.camera_on:
            self.stop_camera()
        self.root.destroy()


if __name__ == "__main__":
    root = ctk.CTk()
    app = HandGestureApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
