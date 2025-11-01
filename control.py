# import tkinter as tk
# from pynput.keyboard import Key, Controller
# import numpy as np
# import sounddevice as sd
# import threading
# import queue

# class AudioAnalyzer:
#     def __init__(self, chunk=2048):
#         self.CHUNK = chunk
#         self.RATE = 44100
#         self.CHANNELS = 2
#         self.running = False
#         self.data_queue = queue.Queue()
#         self.thread = None

#     def start(self):
#         if self.running:
#             return
#         self.running = True
#         self.thread = threading.Thread(target=self._run_loop, daemon=True)
#         self.thread.start()

#     def _run_loop(self):
#         try:
#             # Find loopback device (Windows WASAPI)
#             devices = sd.query_devices()
#             loopback_device = None
            
#             # Look for "Stereo Mix" or loopback device
#             for i, device in enumerate(devices):
#                 device_name = device['name'].lower()
#                 if ('stereo mix' in device_name or 
#                     'loopback' in device_name or 
#                     'what u hear' in device_name or
#                     'wave out mix' in device_name):
#                     if device['max_input_channels'] > 0:
#                         loopback_device = i
#                         break
            
#             # If no loopback found, try default input as fallback
#             if loopback_device is None:
#                 loopback_device = sd.default.device[0]
#                 print("Warning: No loopback device found. Using default input device.")
#                 print("To capture system audio on Windows:")
#                 print("1. Right-click speaker icon in taskbar")
#                 print("2. Select 'Sounds' > 'Recording' tab")
#                 print("3. Right-click empty space > 'Show Disabled Devices'")
#                 print("4. Enable 'Stereo Mix' if available")
            
#             device_info = sd.query_devices(loopback_device)
#             self.RATE = int(device_info['default_samplerate'])
#             self.CHANNELS = min(device_info['max_input_channels'], 2)
            
#             print(f"Using device: {device_info['name']}")
#             print(f"Sample rate: {self.RATE} Hz, Channels: {self.CHANNELS}")

#             with sd.InputStream(
#                 samplerate=self.RATE,
#                 blocksize=self.CHUNK,
#                 device=loopback_device,
#                 channels=self.CHANNELS,
#                 dtype='int16',
#                 latency='low',
#                 callback=self.audio_callback
#             ):
#                 while self.running:
#                     sd.sleep(100)
#         except Exception as e:
#             print(f"Error in audio loop: {e}")
#             import traceback
#             traceback.print_exc()

#     def audio_callback(self, indata, frames, time, status):
#         if status:
#             print(f"Audio callback status: {status}")
#         if self.running and indata is not None:
#             self.data_queue.put(indata.copy())

#     def get_audio_data(self):
#         if not self.data_queue.empty():
#             data = self.data_queue.get()
#             audio_data = np.array(data, dtype=np.int16)
#             if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
#                 # Convert stereo to mono
#                 audio_data = audio_data.mean(axis=1).astype(np.int16)
#             return audio_data
#         return None

#     def stop(self):
#         self.running = False
#         if self.thread:
#             self.thread.join(timeout=2)
#             self.thread = None


# class YouTubeMusicController:
#     def __init__(self, root):
#         self.root = root
#         self.root.title("YouTube Music Controller")
#         self.root.geometry("500x650")
#         self.root.configure(bg="#282828")

#         self.keyboard = Controller()
#         self.audio_analyzer = AudioAnalyzer()
#         self.is_analyzing = False

#         # Title
#         title = tk.Label(root, text="🎵 YouTube Music Controller",
#                          font=("Arial", 18, "bold"), bg="#282828", fg="#ffffff")
#         title.pack(pady=10)

#         # Audio visualizer canvas
#         viz_frame = tk.Frame(root, bg="#1a1a1a")
#         viz_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

#         # Volume meter
#         vol_label = tk.Label(viz_frame, text="Volume", font=("Arial", 10, "bold"),
#                              bg="#1a1a1a", fg="#ffffff")
#         vol_label.pack(pady=(5, 0))

#         self.volume_canvas = tk.Canvas(viz_frame, width=460, height=40,
#                                        bg="#000000", highlightthickness=0)
#         self.volume_canvas.pack(pady=5)

#         self.volume_text = tk.Label(viz_frame, text="0 dB", font=("Arial", 9),
#                                     bg="#1a1a1a", fg="#00ff00")
#         self.volume_text.pack()

#         # Frequency spectrum
#         freq_label = tk.Label(viz_frame, text="Frequency Spectrum",
#                               font=("Arial", 10, "bold"), bg="#1a1a1a", fg="#ffffff")
#         freq_label.pack(pady=(10, 0))

#         self.freq_canvas = tk.Canvas(viz_frame, width=460, height=150,
#                                      bg="#000000", highlightthickness=0)
#         self.freq_canvas.pack(pady=5)

#         # Dominant frequency display
#         self.freq_text = tk.Label(viz_frame, text="Dominant: 0 Hz",
#                                   font=("Arial", 9), bg="#1a1a1a", fg="#00ffff")
#         self.freq_text.pack(pady=5)

#         # Buttons
#         button_frame = tk.Frame(root, bg="#282828")
#         button_frame.pack(pady=10)

#         button_config = {"font": ("Arial", 10), "width": 10, "height": 2,
#                          "bg": "#ff0000", "fg": "white",
#                          "activebackground": "#cc0000", "activeforeground": "white",
#                          "border": 0, "cursor": "hand2"}

#         self.prev_btn = tk.Button(button_frame, text="⏮ Previous", command=self.previous_track, **button_config)
#         self.prev_btn.grid(row=0, column=0, padx=3, pady=5)

#         self.play_btn = tk.Button(button_frame, text="⏯ Play/Pause", command=self.play_pause, **button_config)
#         self.play_btn.grid(row=0, column=1, padx=3, pady=5)

#         self.next_btn = tk.Button(button_frame, text="⏭ Next", command=self.next_track, **button_config)
#         self.next_btn.grid(row=0, column=2, padx=3, pady=5)

#         # Volume controls
#         volume_frame = tk.Frame(root, bg="#282828")
#         volume_frame.pack(pady=5)

#         self.vol_down_btn = tk.Button(volume_frame, text="🔉 Vol Down", command=self.volume_down, **button_config)
#         self.vol_down_btn.grid(row=0, column=0, padx=3)

#         self.vol_up_btn = tk.Button(volume_frame, text="🔊 Vol Up", command=self.volume_up, **button_config)
#         self.vol_up_btn.grid(row=0, column=1, padx=3)

#         # Audio analyzer toggle
#         self.analyzer_btn = tk.Button(root, text="🎤 Start Audio Analysis", command=self.toggle_analyzer,
#                                       font=("Arial", 10, "bold"), width=20, height=1,
#                                       bg="#00aa00", fg="white",
#                                       activebackground="#008800", activeforeground="white",
#                                       border=0, cursor="hand2")
#         self.analyzer_btn.pack(pady=10)

#         # Info and status
#         self.info_label = tk.Label(root, text="Enable 'Stereo Mix' in Windows sound settings for loopback",
#                                    font=("Arial", 8), bg="#282828", fg="#aaaaaa")
#         self.info_label.pack(pady=5)

#         self.status_label = tk.Label(root, text="Ready", font=("Arial", 9),
#                                      bg="#282828", fg="#00ff00")
#         self.status_label.pack(pady=5)

#         self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

#     def toggle_analyzer(self):
#         if not self.is_analyzing:
#             try:
#                 self.audio_analyzer.start()
#                 self.is_analyzing = True
#                 self.analyzer_btn.config(text="⏸ Stop Audio Analysis", bg="#aa0000")
#                 self.update_visualizer()
#                 self.show_status("🎤 Audio analysis started")
#             except Exception as e:
#                 self.show_status(f"❌ Error: {e}")
#                 print(f"Error starting analyzer: {e}")
#         else:
#             self.audio_analyzer.stop()
#             self.is_analyzing = False
#             self.analyzer_btn.config(text="🎤 Start Audio Analysis", bg="#00aa00")
#             self.show_status("⏸ Audio analysis stopped")
#             # Reset visualizer
#             self.volume_canvas.delete("all")
#             self.freq_canvas.delete("all")
#             self.volume_text.config(text="0 dB")
#             self.freq_text.config(text="Dominant: 0 Hz")

#     def update_visualizer(self):
#         if not self.is_analyzing:
#             return

#         audio_data = self.audio_analyzer.get_audio_data()
#         if audio_data is not None and len(audio_data) > 0:
#             # Calculate RMS and convert to dB
#             rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
#             if rms > 0:
#                 db = 20 * np.log10(rms / 32768.0)  # Normalize to 16-bit range
#                 db = max(-60, min(0, db))
#             else:
#                 db = -60
#         else:
#             db = -60
#             audio_data = np.zeros(self.audio_analyzer.CHUNK, dtype=np.int16)

#         # Volume meter
#         self.volume_canvas.delete("all")
#         bar_width = int((db + 60) / 60 * 460)
#         color = "#00ff00" if db <= -30 else "#ffaa00" if db <= -10 else "#ff0000"
#         self.volume_canvas.create_rectangle(0, 0, bar_width, 40, fill=color, outline="")
#         self.volume_text.config(text=f"{db:.1f} dB")

#         # Frequency spectrum
#         if len(audio_data) > 0:
#             # Apply windowing and FFT
#             windowed = audio_data.astype(np.float32) * np.hamming(len(audio_data))
#             fft = np.fft.rfft(windowed)
#             magnitude = np.abs(fft)
#             freqs = np.fft.rfftfreq(len(audio_data), 1/self.audio_analyzer.RATE)
            
#             # Draw spectrum (logarithmic scale for better visualization)
#             self.freq_canvas.delete("all")
#             num_bars = 50
#             max_freq_idx = min(len(magnitude), len(freqs))
#             bar_width = 460 / num_bars
            
#             # Group frequencies into bars
#             for i in range(num_bars):
#                 start_idx = int(i * max_freq_idx / num_bars)
#                 end_idx = int((i + 1) * max_freq_idx / num_bars)
#                 if end_idx > start_idx:
#                     bar_mag = np.mean(magnitude[start_idx:end_idx])
#                     bar_height = min(int(bar_mag / 100), 150)  # Scale and cap height
                    
#                     # Color gradient based on frequency
#                     if i < num_bars * 0.3:
#                         color = "#ff0000"  # Low freq - red
#                     elif i < num_bars * 0.6:
#                         color = "#00ff00"  # Mid freq - green
#                     else:
#                         color = "#0000ff"  # High freq - blue
                    
#                     x1 = i * bar_width
#                     x2 = x1 + bar_width - 1
#                     y1 = 150 - bar_height
#                     self.freq_canvas.create_rectangle(x1, y1, x2, 150, fill=color, outline="")
            
#             # Find dominant frequency (excluding DC component)
#             if len(magnitude) > 1:
#                 dominant_idx = np.argmax(magnitude[1:]) + 1
#                 dominant_freq = freqs[dominant_idx]
#                 self.freq_text.config(text=f"Dominant: {dominant_freq:.0f} Hz")
#             else:
#                 self.freq_text.config(text="Dominant: 0 Hz")
#         else:
#             self.freq_canvas.delete("all")
#             self.freq_text.config(text="Dominant: 0 Hz")

#         self.root.after(50, self.update_visualizer)

#     def show_status(self, message):
#         self.status_label.config(text=message)
#         self.root.after(2000, lambda: self.status_label.config(text="Ready"))

#     # Media controls
#     def play_pause(self):
#         self.keyboard.press(Key.media_play_pause)
#         self.keyboard.release(Key.media_play_pause)
#         self.show_status("⏯ Play/Pause toggled")

#     def next_track(self):
#         self.keyboard.press(Key.media_next)
#         self.keyboard.release(Key.media_next)
#         self.show_status("⏭ Skipped to next track")

#     def previous_track(self):
#         self.keyboard.press(Key.media_previous)
#         self.keyboard.release(Key.media_previous)
#         self.show_status("⏮ Previous track")

#     def volume_up(self):
#         self.keyboard.press(Key.media_volume_up)
#         self.keyboard.release(Key.media_volume_up)
#         self.show_status("🔊 Volume increased")

#     def volume_down(self):
#         self.keyboard.press(Key.media_volume_down)
#         self.keyboard.release(Key.media_volume_down)
#         self.show_status("🔉 Volume decreased")

#     def on_closing(self):
#         if self.is_analyzing:
#             self.audio_analyzer.stop()
#         self.root.destroy()


# def main():
#     root = tk.Tk()
#     app = YouTubeMusicController(root)
#     root.mainloop()


# if __name__ == "__main__":
#     main()


import sounddevice as sd

print(sd.query_devices())