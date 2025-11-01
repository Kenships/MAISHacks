import tkinter as tk
import sys
from pynput.keyboard import Key, Controller  # --- NEW IMPORT ---
import cv2                                   # --- NEW IMPORT ---
from PIL import Image, ImageTk               # --- NEW IMPORT ---

class HandGestureApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gesture Hand UI")
        self.root.geometry("800x700")
        self.root.configure(bg="#181818")

        # --- 1. Initialize Keyboard Controller ---
        try:
            self.keyboard = Controller()
        except Exception as e:
            print(f"Error: {e}. Media keys may not work.")
            self.keyboard = None
        
        # --- 2. Camera State ---
        self.camera_on = False
        self.cap = None # Will hold the cv2.VideoCapture object
        self.CAM_WIDTH = 640
        self.CAM_HEIGHT = 480

        # --- UI Layout (Same as before) ---
        self.camera_frame = tk.Frame(root, bg="black", 
                                      width=self.CAM_WIDTH, height=self.CAM_HEIGHT)
        self.camera_frame.pack(pady=20, padx=20)
        self.camera_frame.pack_propagate(False) 

        self.camera_label = tk.Label(self.camera_frame, bg="black")
        self.camera_label.pack()
        
        self.set_camera_placeholder("Press 'Start Camera' to begin")

        self.bottom_frame = tk.Frame(root, bg="#282828", borderwidth=1, relief=tk.SOLID)
        self.bottom_frame.pack(fill=tk.X, side=tk.BOTTOM, ipady=10)

        self.song_title_label = tk.Label(self.bottom_frame, text="No Song Playing",
                                          font=("Arial", 16, "bold"), 
                                          bg="#282828", fg="#ffffff")
        self.song_title_label.pack(pady=(10, 0))

        self.artist_label = tk.Label(self.bottom_frame, text="---",
                                      font=("Arial", 12), 
                                      bg="#282828", fg="#aaaaaa")
        self.artist_label.pack()

        self.controls_frame = tk.Frame(self.bottom_frame, bg="#282828")
        self.controls_frame.pack(pady=10)
        
        button_config = {"font": ("Arial", 10), "width": 20, "height": 2,
                         "fg": "white", "border": 0, "cursor": "hand2"}

        # --- 3. Link Start Button ---
        self.start_cam_btn = tk.Button(self.controls_frame, 
                                       text="📷 Start Camera", 
                                       command=self.start_camera, # Added command
                                       bg="#00aa00", activebackground="#008800", **button_config)
        self.start_cam_btn.grid(row=0, column=0, padx=5)
        
        # --- 4. Link Simulate Button ---
        self.simulate_btn = tk.Button(self.controls_frame, 
                                      text="✋ Simulate Play/Pause", 
                                      # Added lambda to pass argument
                                      command=lambda: self.on_hand_symbol_detected("PLAY_PAUSE"), 
                                      bg="#5a0099", activebackground="#4a0088", **button_config)
        self.simulate_btn.grid(row=0, column=1, padx=5)
        
        self.status_label = tk.Label(self.bottom_frame, text="Ready",
                                     font=("Arial", 10), 
                                     bg="#282828", fg="#00ff00")
        self.status_label.pack(pady=(0, 10))

    def set_camera_placeholder(self, text):
        self.camera_label.config(image='', text=text, font=("Arial", 12),
                                 fg="white", bg="black",
                                 width=self.CAM_WIDTH, height=self.CAM_HEIGHT)

    # --- 5. New Function: Start Camera ---
    def start_camera(self):
        if self.camera_on: return # Already running

        try:
            self.cap = cv2.VideoCapture(0) # Open webcam
            if not self.cap.isOpened():
                raise Exception("Cannot open webcam")
            
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.CAM_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.CAM_HEIGHT)
            
            self.camera_on = True
            self.show_status("Camera started.")
            self.start_cam_btn.config(text="Camera Active", state=tk.DISABLED)
            self.update_camera_feed() # Start the loop

        except Exception as e:
            self.set_camera_placeholder(f"Error: {e}")
            self.show_status(f"Error: {e}", is_error=True)

    # --- 6. New Function: The Main Loop ---
    def update_camera_feed(self):
        if not self.camera_on: return

        ret, frame = self.cap.read()
        
        if ret:
            # --- AI INTEGRATION POINT ---
            # Your team's AI code will go here.
            # gesture = ai_model.detect(frame)
            # if gesture:
            #     self.on_hand_symbol_detected(gesture)
            # -----------------------------

            # Convert for Tkinter display
            frame_flipped = cv2.flip(frame, 1) # Mirror view
            cv_rgb = cv2.cvtColor(frame_flipped, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(cv_rgb)
            img_tk = ImageTk.PhotoImage(image=pil_img)

            # Update the label
            self.camera_label.config(image=img_tk, text="")
            self.camera_label.image = img_tk
        
        # Rerun this function after 10ms
        self.root.after(10, self.update_camera_feed)

    # --- 7. New Functions: Media Key Logic ---
    def on_hand_symbol_detected(self, gesture):
        if gesture == "PLAY_PAUSE":
            self.show_status("Symbol Detected: Play/Pause!")
            self.send_key(Key.media_play_pause)
            self.song_title_label.config(text="Toggled Play/Pause")
            self.artist_label.config(text=f"Gesture: {gesture}")
        # Add other gestures like "NEXT_TRACK" here
        
    def send_key(self, key):
        if self.keyboard:
            try:
                self.keyboard.press(key)
                self.keyboard.release(key)
            except Exception as e:
                self.show_status(f"Error: {e}", is_error=True)
        else:
            self.show_status("Keyboard controller not initialized.", is_error=True)
            
    def show_status(self, message, is_error=False):
        color = "#ff0000" if is_error else "#00ff00"
        self.status_label.config(text=message, fg=color)

    # --- 8. Modified Function: Cleanup ---
    def on_closing(self):
        if self.camera_on:
            print("Stopping camera...")
            self.camera_on = False # Stop the loop
            self.cap.release() # Release hardware
        print("Closing application...")
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = HandGestureApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()