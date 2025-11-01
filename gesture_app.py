import tkinter as tk
import cv2  # OpenCV
from PIL import Image, ImageTk  # Pillow
import sys

class HandGestureApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gesture Control Media Player")
        self.root.geometry("800x700")
        self.root.configure(bg="#181818") # Dark background
        
        # --- Camera State ---
        self.camera_on = False       # Is the hardware on?
        self.camera_visible = False  # Is the UI feed visible?
        self.cap = None
        self.CAM_WIDTH = 640
        self.CAM_HEIGHT = 480

        # --- Top Frame (for Camera) ---
        self.camera_frame = tk.Frame(root, bg="black", 
                                      width=self.CAM_WIDTH, height=self.CAM_HEIGHT)
        self.camera_frame.pack(pady=20, padx=20)
        self.camera_frame.pack_propagate(False) 

        self.camera_label = tk.Label(self.camera_frame, bg="black")
        self.camera_label.pack()
        
        self.set_camera_placeholder("Press 'Start Camera' to begin")

        # --- Bottom Frame (for Controls & Song Info) ---
        self.bottom_frame = tk.Frame(root, bg="#282828", borderwidth=1, relief=tk.SOLID)
        self.bottom_frame.pack(fill=tk.X, side=tk.BOTTOM, ipady=10)

        # --- Song Info ---
        self.song_title_label = tk.Label(self.bottom_frame, text="No Song Playing",
                                          font=("Arial", 16, "bold"), 
                                          bg="#282828", fg="#ffffff")
        self.song_title_label.pack(pady=(10, 0))

        self.artist_label = tk.Label(self.bottom_frame, text="---",
                                      font=("Arial", 12), 
                                      bg="#282828", fg="#aaaaaa")
        self.artist_label.pack()

        # --- Control Buttons (Dynamic) ---
        self.controls_frame = tk.Frame(self.bottom_frame, bg="#282828")
        self.controls_frame.pack(pady=10)
        
        button_config = {"font": ("Arial", 10), "width": 20, "height": 2,
                         "fg": "white", "border": 0, "cursor": "hand2"}

        self.start_cam_btn = tk.Button(self.controls_frame, 
                                       text="📷 Start Camera", 
                                       command=self.start_camera,
                                       bg="#00aa00", activebackground="#008800", **button_config)
        self.start_cam_btn.grid(row=0, column=0, padx=5)

        self.stop_cam_btn = tk.Button(self.controls_frame, 
                                      text="⏹ Stop Camera", 
                                      command=self.stop_camera,
                                      bg="#cc0000", activebackground="#aa0000", **button_config)
        # .grid() is called in start_camera()

        # THIS IS THE BUTTON YOU ASKED FOR
        self.toggle_view_btn = tk.Button(self.controls_frame, 
                                         text="🙈 Hide Feed", 
                                         command=self.toggle_camera_view,
                                         bg="#ff8c00", activebackground="#dd7700", **button_config)
        # .grid() is called in start_camera()
        
        # This button is for testing your AI team's hook
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
        """Shows text in the black camera box"""
        self.camera_label.config(image='', text=text, font=("Arial", 12),
                                 fg="white", bg="black",
                                 width=self.CAM_WIDTH, height=self.CAM_HEIGHT)

    def start_camera(self):
        """Turns on the camera hardware and shows all buttons"""
        if self.camera_on: return

        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                raise Exception("Cannot open webcam")
            
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.CAM_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.CAM_HEIGHT)
            
            self.camera_on = True
            self.camera_visible = True
            
            self.start_cam_btn.grid_remove()
            self.simulate_btn.grid(row=0, column=2, padx=5)
            self.stop_cam_btn.grid(row=0, column=0, padx=5)
            self.toggle_view_btn.grid(row=0, column=1, padx=5) # Show the toggle button
            self.toggle_view_btn.config(text="🙈 Hide Feed")
            
            self.show_status("Camera started. Looking for gestures...")
            self.update_camera_feed()

        except Exception as e:
            self.set_camera_placeholder(f"Error: {e}")
            self.show_status(f"Error: {e}", is_error=True)

    def stop_camera(self):
        """Turns off the camera hardware and resets buttons"""
        self.camera_on = False
        self.camera_visible = False
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.stop_cam_btn.grid_remove()
        self.toggle_view_btn.grid_remove()
        self.simulate_btn.grid(row=0, column=1, padx=5)
        self.start_cam_btn.grid(row=0, column=0, padx=5)
        
        self.set_camera_placeholder("Camera feed stopped.")
        self.show_status("Camera stopped.")

    def toggle_camera_view(self):
        """Manually hides or shows the camera feed"""
        self.camera_visible = not self.camera_visible
        
        if self.camera_visible:
            self.toggle_view_btn.config(text="🙈 Hide Feed")
            # The update_camera_feed loop will now show the images
        else:
            self.toggle_view_btn.config(text="🙉 Show Feed")
            self.set_camera_placeholder("Feed hidden. Gestures are still active.")

    def update_camera_feed(self):
        """THE MAIN LOOP: AI runs always, UI runs conditionally"""
        if not self.camera_on:
            return

        ret, frame = self.cap.read()
        
        if ret:
            
            # -----------------------------------------------------------------
            # AI INTEGRATION POINT 
            # -----------------------------------------------------------------
            # This part ALWAYS runs.
            # gesture = your_ai_model.detect_gesture(frame)
            # if gesture:
            #     self.on_hand_symbol_detected(gesture)
            # -----------------------------------------------------------------


            if self.camera_visible:
                # This block only runs if the user wants to see the feed
                frame_flipped = cv2.flip(frame, 1) # Mirror view
                cv_rgb = cv2.cvtColor(frame_flipped, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(cv_rgb)
                img_tk = ImageTk.PhotoImage(image=pil_img)

                self.camera_label.config(image=img_tk, text="")
                self.camera_label.image = img_tk
        
        self.root.after(10, self.update_camera_feed) # Loop

    def on_hand_symbol_detected(self, gesture):
        """
        This is the function your AI will call.
        It just updates the status text.
        """
        self.show_status(f"Gesture Detected: {gesture}")
        self.artist_label.config(text=f"Last Gesture: {gesture}")
        
        # --- NO MORE HIDING LOGIC HERE ---
        # The user will click the "Hide Feed" button manually.

    # --- Helper functions ---
            
    def show_status(self, message, is_error=False):
        color = "#ff0000" if is_error else "#00ff00"
        self.status_label.config(text=message, fg=color)
            
    def on_closing(self):
        """Called when the window 'X' is clicked."""
        if self.camera_on:
            self.stop_camera() # Use our new stop function
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = HandGestureApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()