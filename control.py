import tkinter as tk
from tkinter import ttk
from pynput.keyboard import Key, Controller
import threading
import time
import numpy as np
import pyaudio
from scipy import signal
import queue

class AudioAnalyzer:
    def __init__(self):
        self.CHUNK = 2048
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 2
        self.RATE = 44100
        self.running = False
        self.audio = None
        self.stream = None
        self.data_queue = queue.Queue()
        
    def start(self):
        self.running = True
        self.audio = pyaudio.PyAudio()
        
        # Try to find stereo mix / loopback device
        device_index = None
        for i in range(self.audio.get_device_count()):
            dev_info = self.audio.get_device_info_by_index(i)
            if ('stereo mix' in dev_info['name'].lower() or 
                'loopback' in dev_info['name'].lower() or
                'wave out' in dev_info['name'].lower() or
                'what u hear' in dev_info['name'].lower()):
                if dev_info['maxInputChannels'] > 0:
                    device_index = i
                    break
        
        # If no loopback found, use default input
        if device_index is None:
            device_index = self.audio.get_default_output_device_info()['index']
        
        self.stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=self.CHUNK,
            stream_callback=self.audio_callback
        )
        self.stream.start_stream()
    
    def audio_callback(self, in_data, frame_count, time_info, status):
        if self.running:
            self.data_queue.put(in_data)
        return (None, pyaudio.paContinue)
    
    def get_audio_data(self):
        if not self.data_queue.empty():
            data = self.data_queue.get()
            audio_data = np.frombuffer(data, dtype=np.int16)
            
            # Convert to mono if stereo
            if self.CHANNELS == 2:
                audio_data = audio_data.reshape(-1, 2).mean(axis=1)
            
            return audio_data
        return None
    
    def stop(self):
        self.running = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.audio:
            self.audio.terminate()

class YouTubeMusicController:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Music Controller")
        self.root.geometry("500x650")
        self.root.configure(bg="#282828")
        
        self.keyboard = Controller()
        self.audio_analyzer = AudioAnalyzer()
        self.is_analyzing = False
        
        # Title
        title = tk.Label(
            root,
            text="🎵 YouTube Music Controller",
            font=("Arial", 18, "bold"),
            bg="#282828",
            fg="#ffffff"
        )
        title.pack(pady=10)
        
        # Audio visualizer canvas
        viz_frame = tk.Frame(root, bg="#1a1a1a")
        viz_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        # Volume meter
        vol_label = tk.Label(
            viz_frame,
            text="Volume",
            font=("Arial", 10, "bold"),
            bg="#1a1a1a",
            fg="#ffffff"
        )
        vol_label.pack(pady=(5, 0))
        
        self.volume_canvas = tk.Canvas(
            viz_frame,
            width=460,
            height=40,
            bg="#000000",
            highlightthickness=0
        )
        self.volume_canvas.pack(pady=5)
        
        self.volume_text = tk.Label(
            viz_frame,
            text="0 dB",
            font=("Arial", 9),
            bg="#1a1a1a",
            fg="#00ff00"
        )
        self.volume_text.pack()
        
        # Frequency spectrum
        freq_label = tk.Label(
            viz_frame,
            text="Frequency Spectrum",
            font=("Arial", 10, "bold"),
            bg="#1a1a1a",
            fg="#ffffff"
        )
        freq_label.pack(pady=(10, 0))
        
        self.freq_canvas = tk.Canvas(
            viz_frame,
            width=460,
            height=150,
            bg="#000000",
            highlightthickness=0
        )
        self.freq_canvas.pack(pady=5)
        
        # Dominant frequency display
        self.freq_text = tk.Label(
            viz_frame,
            text="Dominant: 0 Hz",
            font=("Arial", 9),
            bg="#1a1a1a",
            fg="#00ffff"
        )
        self.freq_text.pack(pady=5)
        
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
        
        # Audio analyzer toggle
        self.analyzer_btn = tk.Button(
            root,
            text="🎤 Start Audio Analysis",
            command=self.toggle_analyzer,
            font=("Arial", 10, "bold"),
            width=20,
            height=1,
            bg="#00aa00",
            fg="white",
            activebackground="#008800",
            activeforeground="white",
            border=0,
            cursor="hand2"
        )
        self.analyzer_btn.pack(pady=10)
        
        # Info label
        self.info_label = tk.Label(
            root,
            text="Enable 'Stereo Mix' in Windows Sound settings for audio capture",
            font=("Arial", 8),
            bg="#282828",
            fg="#aaaaaa"
        )
        self.info_label.pack(pady=5)
        
        # Status label
        self.status_label = tk.Label(
            root,
            text="Ready",
            font=("Arial", 9),
            bg="#282828",
            fg="#00ff00"
        )
        self.status_label.pack(pady=5)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def toggle_analyzer(self):
        if not self.is_analyzing:
            try:
                self.audio_analyzer.start()
                self.is_analyzing = True
                self.analyzer_btn.config(text="⏸ Stop Audio Analysis", bg="#aa0000")
                self.update_visualizer()
                self.show_status("🎤 Audio analysis started")
            except Exception as e:
                self.show_status(f"❌ Error: {str(e)}")
        else:
            self.audio_analyzer.stop()
            self.is_analyzing = False
            self.analyzer_btn.config(text="🎤 Start Audio Analysis", bg="#00aa00")
            self.show_status("⏸ Audio analysis stopped")
    
    def update_visualizer(self):
        if not self.is_analyzing:
            return
        
        audio_data = self.audio_analyzer.get_audio_data()
        
        if audio_data is not None and len(audio_data) > 0:
            # Calculate volume (RMS)
            rms = np.sqrt(np.mean(audio_data**2))
            db = 20 * np.log10(rms + 1e-10)  # Add small value to avoid log(0)
            db = max(-60, min(0, db))  # Clamp between -60 and 0 dB
            
            # Draw volume meter
            self.volume_canvas.delete("all")
            bar_width = int((db + 60) / 60 * 460)
            
            # Color gradient based on volume
            if db > -10:
                color = "#ff0000"
            elif db > -30:
                color = "#ffaa00"
            else:
                color = "#00ff00"
            
            self.volume_canvas.create_rectangle(
                0, 0, bar_width, 40,
                fill=color,
                outline=""
            )
            self.volume_text.config(text=f"{db:.1f} dB")
            
            # Calculate frequency spectrum using FFT
            fft = np.fft.rfft(audio_data * np.hamming(len(audio_data)))
            magnitude = np.abs(fft)
            freqs = np.fft.rfftfreq(len(audio_data), 1/self.audio_analyzer.RATE)
            
            # Limit to audible range (20 Hz - 20 kHz)
            max_freq_idx = np.where(freqs <= 20000)[0][-1]
            magnitude = magnitude[:max_freq_idx]
            freqs = freqs[:max_freq_idx]
            
            # Downsample for visualization
            num_bars = 100
            chunk_size = len(magnitude) // num_bars
            if chunk_size > 0:
                magnitude_bars = [np.max(magnitude[i:i+chunk_size]) 
                                 for i in range(0, len(magnitude), chunk_size)][:num_bars]
                
                # Normalize
                if len(magnitude_bars) > 0 and max(magnitude_bars) > 0:
                    magnitude_bars = np.array(magnitude_bars) / max(magnitude_bars)
                    
                    # Draw frequency bars
                    self.freq_canvas.delete("all")
                    bar_width = 460 / num_bars
                    
                    for i, mag in enumerate(magnitude_bars):
                        height = mag * 150
                        x = i * bar_width
                        
                        # Color based on frequency range
                        if i < num_bars * 0.2:  # Bass
                            color = "#ff0000"
                        elif i < num_bars * 0.6:  # Mids
                            color = "#00ff00"
                        else:  # Treble
                            color = "#0088ff"
                        
                        self.freq_canvas.create_rectangle(
                            x, 150 - height, x + bar_width - 1, 150,
                            fill=color,
                            outline=""
                        )
            
            # Find dominant frequency
            if len(magnitude) > 0:
                dominant_idx = np.argmax(magnitude)
                dominant_freq = freqs[dominant_idx]
                self.freq_text.config(text=f"Dominant: {dominant_freq:.0f} Hz")
        
        self.root.after(50, self.update_visualizer)
    
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
        if self.is_analyzing:
            self.audio_analyzer.stop()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = YouTubeMusicController(root)
    root.mainloop()

if __name__ == "__main__":
    main()