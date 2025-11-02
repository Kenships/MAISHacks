import tkinter as tk
from pynput.keyboard import Key, Controller
import sys

class MediaControllerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Media Controller")
        self.root.geometry("400x200")
        self.root.configure(bg="#282828")

        # Initialize the pynput keyboard controller
        try:
            self.keyboard = Controller()
        except Exception as e:
            print(f"Error initializing keyboard controller: {e}")
            print("This may fail on some Linux systems without special permissions.")
            # We can still run the GUI, but buttons won't work
            self.keyboard = None 

        # Title
        title = tk.Label(root, text="🎵 Media Controller",
                         font=("Arial", 18, "bold"), bg="#282828", fg="#ffffff")
        title.pack(pady=20)

        # Button frame
        button_frame = tk.Frame(root, bg="#282828")
        button_frame.pack(pady=10)

        # Button styling
        button_config = {"font": ("Arial", 10), "width": 10, "height": 2,
                         "bg": "#ff0000", "fg": "white", "border": 0}

        # --- Create Buttons ---
        self.prev_btn = tk.Button(button_frame, text="⏮ Previous", 
                                  command=self.previous_track, **button_config)
        self.prev_btn.grid(row=0, column=0, padx=5)

        self.play_btn = tk.Button(button_frame, text="⏯ Play/Pause", 
                                  command=self.play_pause, **button_config)
        self.play_btn.grid(row=0, column=1, padx=5)

        self.next_btn = tk.Button(button_frame, text="⏭ Next", 
                                  command=self.next_track, **button_config)
        self.next_btn.grid(row=0, column=2, padx=5)

        self.status_label = tk.Label(root, text="Ready", font=("Arial", 9),
                                     bg="#282828", fg="#00ff00")
        self.status_label.pack(pady=10)

    def show_status(self, message):
        """Helper to show a status message for 2 seconds."""
        self.status_label.config(text=message)
        self.root.after(2000, lambda: self.status_label.config(text="Ready"))

    def send_key(self, key):
        """Safely sends a key press."""
        if self.keyboard:
            try:
                self.keyboard.press(key)
                self.keyboard.release(key)
            except Exception as e:
                self.show_status(f"Error: {e}")
        else:
            self.show_status("Keyboard controller not initialized.")

    # --- Media Control Functions ---
    def play_pause(self):
        self.send_key(Key.media_play_pause)
        self.show_status("⏯ Play/Pause")

    def next_track(self):
        self.send_key(Key.media_next)
        self.show_status("⏭ Next")

    def previous_track(self):
        self.send_key(Key.media_previous)
        self.show_status("⏮ Previous")

# The main block goes *after* the class
if __name__ == "__main__":
    root = tk.Tk()
    app = MediaControllerApp(root)
    root.mainloop()

    