import tkinter as tk
from tkinter import ttk
from pynput.keyboard import Key, Controller
import numpy as np
import cv2
from PIL import Image, ImageTk
from gesture_control_sidney import GestureController
from spotify_controller import auth_spotify, pause, playpause, next_track, previous_track, increase_volume, \
    decrease_volume


class YouTubeMusicController:
    def __init__(self, root):
        self.sp = auth_spotify()

        self.root = root
        self.root.title("YouTube Music Controller with Gestures")
        self.root.geometry("400x400")  # Smaller window since no video canvas
        self.root.configure(bg="#282828")
        
        self.keyboard = Controller()
        # show_video=True to display with OpenCV
        self.gesture_controller = GestureController(self.handle_gesture_callback, show_video=True)
        self.is_gesture_active = False
        
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
        info_text = "Gestures: Thumbs Up = Play/Pause | Victory = Next | Closed Fist = Previous"
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
            try:
                self.gesture_controller.run()
                self.is_gesture_active = True
                self.gesture_btn.config(text="⏸ Stop Gesture Control", bg="#cc0000")
                self.show_status("📷 Gesture control started")
            except Exception as e:
                self.show_status(f"❌ Error: {str(e)}")
        else:
            self.gesture_controller.stop()
            self.is_gesture_active = False
            self.gesture_btn.config(text="📷 Start Gesture Control", bg="#0066cc")
            self.show_status("⏸ Gesture control stopped")
    
    def handle_gesture_callback(self, callback_type, data, extra):
        """Handle callbacks from GestureController"""
        # We don't need to handle 'frame' anymore since OpenCV displays it
        if callback_type == 'gesture':
            # data is the gesture name, extra is the hand object
            self.handle_gesture(data)
        elif callback_type == 'action':
            # data is the action event
            self.handle_action(data)
        elif callback_type == 'combo':
            # data is the combo name
            self.handle_combo(data)
    
    # Remove update_video_feed method - no longer needed
    
    def handle_gesture(self, gesture_name):
        """Handle individual gestures"""
        # print(f"Gesture detected: {gesture_name}")
        
        # Map gesture names to actions
        if gesture_name == "Thumb_Up":
            self.play_pause()
        elif gesture_name == "Victory":
            self.next_track()
        elif gesture_name == "Closed_Fist":
            self.previous_track()
        elif gesture_name == "Open_Palm":
            self.volume_up()
        
        self.show_status(f"👋 Gesture: {gesture_name}")
    
    def handle_action(self, action):
        """Handle action events (swipes, taps, etc.)"""
        print(f"Action detected: {action}")
        self.show_status(f"🎬 Action: {action}")
    
    def handle_combo(self, combo_name):
        """Handle combo gestures"""
        print(f"Combo detected: {combo_name}")
        self.show_status(f"🎯 Combo: {combo_name}")
    
    def show_status(self, message):
        self.status_label.config(text=message)
        self.root.after(2000, lambda: self.status_label.config(text="Ready"))
    
    def play_pause(self):
        # playpause(self.sp)
        self.keyboard.press(Key.media_play_pause)
        self.keyboard.release(Key.media_play_pause)
        print("press pause")
        self.show_status("⏯ Play/Pause toggled")
    
    def next_track(self):
        # next_track(self.sp)
        self.keyboard.press(Key.media_next)
        self.keyboard.release(Key.media_next)
        self.show_status("⏭ Skipped to next track")
    
    def previous_track(self):
        # previous_track(self.sp)
        self.keyboard.press(Key.media_previous)
        self.keyboard.release(Key.media_previous)
        self.show_status("⏮ Previous track")
    
    def volume_up(self):
        # increase_volume(self.sp)
        self.keyboard.press(Key.media_volume_up)
        self.keyboard.release(Key.media_volume_up)
        self.show_status("🔊 Volume increased")
    
    def volume_down(self):
        # decrease_volume(self.sp)
        self.keyboard.press(Key.media_volume_down)
        self.keyboard.release(Key.media_volume_down)
        self.show_status("🔉 Volume decreased")
    
    def on_closing(self):
        if self.is_gesture_active:
            self.gesture_controller.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = YouTubeMusicController(root)
    root.mainloop()


if __name__ == "__main__":
    main()