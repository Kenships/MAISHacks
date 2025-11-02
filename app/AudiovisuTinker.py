import soundcard as sc
import numpy as np
import tkinter as tk
from tkinter import Canvas
import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="soundcard")
# Get loopback device for system audio
default_speaker = sc.default_speaker()
try:
    loopback = sc.get_microphone(id=str(default_speaker.name), include_loopback=True)
except:
    mics = sc.all_microphones(include_loopback=True)
    loopback = [mic for mic in mics if "loopback" in mic.name.lower()][0]

print(f"Recording from: {loopback.name}")

# Setup tkinter window
root = tk.Tk()
root.title("Audio Visualizer")
root.configure(bg='black')

# Canvas for drawing bars
canvas_width = 800
canvas_height = 400
canvas = Canvas(root, width=canvas_width, height=canvas_height, bg='black', highlightthickness=0)
canvas.pack(padx=20, pady=20)

# Create 20 rainbow colored bars
num_bars = 20
bar_width = canvas_width // num_bars - 5
bar_spacing = canvas_width // num_bars

# Generate rainbow colors
def get_rainbow_color(i, total):
    hue = i / total
    # Convert HSV to RGB (simplified)
    if hue < 1/6:
        r, g, b = 1, hue*6, 0
    elif hue < 2/6:
        r, g, b = 2-hue*6, 1, 0
    elif hue < 3/6:
        r, g, b = 0, 1, (hue-2/6)*6
    elif hue < 4/6:
        r, g, b = 0, (4/6-hue)*6, 1
    elif hue < 5/6:
        r, g, b = (hue-4/6)*6, 0, 1
    else:
        r, g, b = 1, 0, (1-hue)*6
    return f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'

# Create bar rectangles
bars = []
for i in range(num_bars):
    color = get_rainbow_color(i, num_bars)
    x = i * bar_spacing + 5
    bar = canvas.create_rectangle(x, canvas_height, x + bar_width, canvas_height, 
                                   fill=color, outline='')
    bars.append(bar)

# Start recording
recorder = loopback.recorder(samplerate=44100)
recorder.__enter__()

def update_bars():
    try:
        # Record audio chunk
        data = recorder.record(numframes=1024)
        
        # Convert stereo to mono
        if len(data.shape) > 1:
            data = np.mean(data, axis=1)
        
        # Randomly sample 20 points
        random_indices = np.random.choice(len(data), num_bars, replace=False)
        sampled_data = data[random_indices]
        
        # Get absolute values (amplitude)
        amplitudes = np.abs(sampled_data)
        
        # Update bar heights
        for i, (bar, amp) in enumerate(zip(bars, amplitudes)):
            x = i * bar_spacing + 5
            # Scale amplitude to canvas height (with some boost for visibility)
            height = min(amp * canvas_height * 2, canvas_height)
            y1 = canvas_height - height
            canvas.coords(bar, x, y1, x + bar_width, canvas_height)
        
        # Schedule next update (every 50ms = 20 FPS)
        root.after(50, update_bars)
    except Exception as e:
        print(f"Error: {e}")
        recorder.__exit__(None, None, None)
        root.quit()

# Start the animation
update_bars()

# Cleanup on close
def on_closing():
    recorder.__exit__(None, None, None)
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()