import tkinter as tk
import cv2
from PIL import Image, ImageTk
import threading
import queue
import time
import io
import requests
from media_info import MediaInfo
from circle_visualizer import AudioRingVisualizer  # Your visualizer file

class HandGestureApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gesture Control Media Player")
        self.root.geometry("800x700")
        self.root.configure(bg="#181818")

        self.pixel_img = tk.PhotoImage(width=1, height=1)

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
        self.current_track_id = None 
        
        # --- FIX: Threading Lock for Polling ---
        self.polling_enabled = threading.Event()  # This is the "pause button"
        self.polling_enabled.set()                # Set to "on" by default

        # --- Top frame (camera/visualizer container) ---
        self.camera_frame = tk.Frame(self.root, width=self.CAM_WIDTH, height=self.CAM_HEIGHT, bg="black")
        self.camera_frame.pack(pady=20, padx=20)
        self.camera_frame.pack_propagate(False)

        # --- Two-Label Fix ---
        self.camera_feed_label = tk.Label(self.camera_frame, bg="black")
        self.camera_placeholder_label = tk.Label(self.camera_frame, text="",
                                                  font=("Arial", 12),
                                                  bg="black", fg="white")
        
        viz_size = min(self.CAM_WIDTH, self.CAM_HEIGHT)
        self.visualizer = AudioRingVisualizer(self.camera_frame, size=viz_size, fps=60)
        self.visualizer.hide() 

        self.set_camera_placeholder("Press 'Start Camera' to begin")

        # --- Bottom Frame (controls + song info) ---
        self.bottom_frame = tk.Frame(self.root, bg="#282828", bd=1, relief="solid")
        self.bottom_frame.pack(fill=tk.X, side=tk.BOTTOM, ipady=10, padx=10, pady=10)

        media_info_frame = tk.Frame(self.bottom_frame, bg="#282828")
        media_info_frame.pack(pady=(10, 0), padx=10, fill=tk.X)

        pil_placeholder = Image.new("RGB", (120, 120), color="#282828")
        self.placeholder_img = ImageTk.PhotoImage(pil_placeholder)

        self.album_art_label = tk.Label(media_info_frame, image=self.placeholder_img,
                                         bg="#282828", bd=0)
        self.album_art_label.pack(side=tk.LEFT, padx=(0, 10))
        self.album_art_label.image = self.placeholder_img

        text_info_frame = tk.Frame(media_info_frame, bg="#282828")
        text_info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self.song_title_label = tk.Label(text_info_frame, text="No Song Playing",
                                             font=("Arial", 16, "bold"), 
                                             bg="#282828", fg="#ffffff", anchor="w")
        self.song_title_label.pack(fill=tk.X)

        self.artist_label = tk.Label(text_info_frame, text="---",
                                         font=("Arial", 12), 
                                         bg="#282828", fg="#aaaaaa", anchor="w")
        self.artist_label.pack(fill=tk.X)

        # --- Like Button ---
        self.like_btn = tk.Button(media_info_frame, text="♡", # Empty heart
                                  font=("Arial", 20),
                                  fg="white", bg="#282828",
                                  activebackground="#1DB954", # Green click
                                  width=2, height=1, # Size in text units
                                  bd=0,
                                  relief=tk.FLAT, # Flat style
                                  command=self.on_like_button_press, # <-- Updated command
                                  state=tk.DISABLED) # Disabled by default
        self.like_btn.pack(side=tk.RIGHT, padx=5)
        
        self.like_btn.bind("<Enter>", self.on_like_enter)
        self.like_btn.bind("<Leave>", self.on_like_leave)


        # Controls
        self.controls_frame = tk.Frame(self.bottom_frame, bg="#282828")
        self.controls_frame.pack(pady=10)

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

    # ---------- Camera / Visualizer switching (FIXED) ----------
    def set_camera_placeholder(self, text):
        """Shows the text label and hides ALL other widgets in the frame."""
        self.visualizer.hide()
        self.camera_feed_label.pack_forget()
        
        self.camera_placeholder_label.config(text=text)
        self.camera_placeholder_label.pack(expand=True)

    def start_camera(self):
        if self.camera_on:
            return
        try:
            self.visualizer.stop()
            self.visualizer.hide()
            self.camera_placeholder_label.pack_forget()

            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                raise Exception("Cannot open webcam")

            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.CAM_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.CAM_HEIGHT)

            self.camera_on = True
            self.camera_visible = True
            
            self.camera_feed_label.pack(expand=True)

            self.start_cam_btn.grid_forget() 
            self.simulate_btn.grid(row=0, column=2, padx=5)
            self.stop_cam_btn.grid(row=0, column=0, padx=5)
            self.toggle_view_btn.grid(row=0, column=1, padx=5)
            self.toggle_view_btn.config(text="🙈 Hide Feed")

            self.show_status("Camera started. Looking for gestures...")
            self.update_camera_feed()
            self.start_media_polling()

        except Exception as e:
            self.show_status(f"Error: {e}", is_error=True)
            self.camera_on = False
            self.camera_visible = False
            self.camera_feed_label.pack_forget()
            self.camera_placeholder_label.pack_forget()
            self.visualizer.show()
            self.visualizer.start()

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

        self.camera_feed_label.pack_forget()
        self.camera_placeholder_label.pack_forget()

        self.visualizer.show()
        self.visualizer.start()

        self.show_status("Camera stopped. Visualizer active.")
        self.update_media_ui(None)

    def toggle_camera_view(self):
        if not self.camera_on:
            return 

        self.camera_visible = not self.camera_visible
        if self.camera_visible:
            try:
                self.visualizer.stop()
                self.visualizer.hide()
            except Exception:
                pass
            self.toggle_view_btn.config(text="🙈 Hide Feed")
            self.camera_placeholder_label.pack_forget()
            self.camera_feed_label.pack(expand=True)
        else:
            self.camera_feed_label.pack_forget()
            self.camera_placeholder_label.pack_forget()
            
            self.visualizer.show()
            self.visualizer.start()
            self.toggle_view_btn.config(text="🙉 Show Feed")

    def update_camera_feed(self):
        if not self.camera_on:
            return

        self.check_media_queue()
        ret, frame = self.cap.read()

        if ret and self.camera_visible:
            frame = cv2.resize(frame, (self.CAM_WIDTH, self.CAM_HEIGHT))
            frame_flipped = cv2.flip(frame, 1)
            cv_rgb = cv2.cvtColor(frame_flipped, cv2.COLOR_BGR2RGB)
            
            pil_img = Image.fromarray(cv_rgb)
            img_tk = ImageTk.PhotoImage(image=pil_img)
            self.camera_feed_label.config(image=img_tk, text="")
            self.camera_feed_label.image = img_tk 

        self.root.after(10, self.update_camera_feed)

    def on_hand_symbol_detected(self, gesture):
        self.show_status(f"Gesture Detected: {gesture}")
        self.artist_label.config(text=f"Last Gesture: {gesture}")

    # ---------- Media polling ----------
    def start_media_polling(self):
        if self.polling_media:
            return
        self.polling_media = True
        self.polling_enabled.set() # Make sure polling is "unpaused"
        self.media_poll_thread = threading.Thread(target=self._run_media_polling_loop, daemon=True)
        self.media_poll_thread.start()

    def stop_media_polling(self):
        if not self.polling_media:
            return
        self.polling_media = False
        self.polling_enabled.set() # Un-pause if it was paused
        if self.media_poll_thread:
            self.media_poll_thread.join(timeout=1.0)
            self.media_poll_thread = None

    def _run_media_polling_loop(self):
        while self.polling_media:
            # --- FIX: This line waits if the "pause" is set ---
            self.polling_enabled.wait()
            
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
            
            # --- Update Like button state ---
            self.current_track_id = info.get('track_id')
            if info.get('is_liked'):
                self.like_btn.config(text="❤️", fg="#1DB954", state=tk.DISABLED)
            else:
                self.like_btn.config(text="#", fg="white", state=tk.NORMAL)
                
        else:
            self.song_title_label.config(text="No Media Playing")
            self.artist_label.config(text="---")
            self.like_btn.config(text="♡", state=tk.DISABLED)
            self.current_track_id = None

        # 2) Album Art
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

    # --- FIX: Two-part "Like" function to prevent flicker ---
    def on_like_button_press(self):
        """Called when the user clicks the 'Like' button. Pauses polling and starts the worker."""
        if not self.current_track_id:
            self.show_status("No track to like!", is_error=True)
            return
            
        self.show_status("Liking song...")
        # Optimistically update UI to show it's liked
        self.like_btn.config(state=tk.DISABLED, text="❤️", fg="#1DB954")
        
        # 1. "Press the pause button" on the main poller
        self.polling_enabled.clear() 
        
        # 2. Run the actual work in a new thread
        worker_thread = threading.Thread(target=self._like_song_worker, daemon=True)
        worker_thread.start()

    def _like_song_worker(self):
        """
        This runs in the background. It likes the song, forces a refresh,
        and then "un-pauses" the main polling thread.
        """
        try:
            # 1. Like the song
            self.media_info.like_current_song()
            
            # 2. Force a re-poll to get new "is_liked": True status
            new_info = self.media_info.get()
            
            # 3. Put the new, correct info on the queue
            if new_info:
                self.media_queue.put(new_info)
            
        except Exception as e:
            print(f"Error re-fetching media info after like: {e}")
        finally:
            # 4. "Un-pause" the main polling thread
            self.polling_enabled.set() 

    # ---------- Helpers ----------
    def on_like_enter(self, event):
        """Called when the mouse enters the like button."""
        if self.like_btn['state'] == tk.NORMAL:
            self.like_btn.config(bg="#404040") # Darker hover color

    def on_like_leave(self, event):
        """Called when the mouse leaves the like button."""
        self.like_btn.config(bg="#282828") # Back to original color
            
    def show_status(self, message, is_error=False):
        color = "#ff0000" if is_error else "#00ff00"
        self.status_label.config(text=message, fg=color)

    def on_closing(self):
        self.stop_media_polling()
        try:
            self.visualizer.stop()
        except Exception:
            pass
            
        if self.camera_on:
            try:
                self.cap.release()
            except Exception:
                pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = HandGestureApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()