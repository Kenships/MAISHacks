import soundcard as sc
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Get loopback device for system audio
default_speaker = sc.default_speaker()
try:
    loopback = sc.get_microphone(id=str(default_speaker.name), include_loopback=True)
except:
    mics = sc.all_microphones(include_loopback=True)
    loopback = [mic for mic in mics if "loopback" in mic.name.lower()][0]

print(f"Recording from: {loopback.name}")

# Setup the plot
fig, ax = plt.subplots(figsize=(12, 6), facecolor='black')
ax.set_facecolor('black')
ax.set_ylim(0, 1)
ax.set_xlim(0, 20)
ax.set_xticks([])
ax.set_yticks([])

# Create 20 colored bars (rainbow gradient)
colors = plt.cm.rainbow(np.linspace(0, 1, 20))
bars = ax.bar(range(20), np.zeros(20), color=colors, width=0.8, edgecolor='none')

# Start recording
recorder = loopback.recorder(samplerate=44100)
recorder.__enter__()

def update(frame):
    # Record audio chunk
    data = recorder.record(numframes=1024)
    
    # Convert stereo to mono by averaging channels
    if len(data.shape) > 1:
        data = np.mean(data, axis=1)
    
    # Randomly sample 20 points from the 1024 frames
    random_indices = np.random.choice(len(data), 20, replace=False)
    sampled_data = data[random_indices]
    
    # Get absolute values (amplitude)
    amplitudes = np.abs(sampled_data)
    
    # Update bar heights
    for bar, height in zip(bars, amplitudes):
        bar.set_height(height)
    
    return bars

# Animate
ani = FuncAnimation(fig, update, interval=50, blit=True, cache_frame_data=False)

plt.tight_layout()
plt.show()

# Cleanup
recorder.__exit__(None, None, None)