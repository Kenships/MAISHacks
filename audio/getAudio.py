import soundcard as sc
import numpy as np

default_speaker = sc.default_speaker()
print(f"Default speaker: {default_speaker.name}")

try:
    loopback = sc.get_microphone(id=str(default_speaker.name), include_loopback=True)
    print(f"Recording from: {loopback.name}")
except:
    # Fallback: try to find any loopback device
    print("\nSearching for loopback devices...")
    mics = sc.all_microphones(include_loopback=True)
    for i, mic in enumerate(mics):
        print(f"{i}: {mic.name}")
        if "loopback" in mic.name.lower():
            loopback = mic
            break
    else:
        print("\nERROR: No loopback device found!")
        print("You need to enable 'Stereo Mix' in Windows Sound Settings")
        exit(1)

with loopback.recorder(samplerate=48000) as recorder:
    print("Recording computer audio output... Press Ctrl+C to stop")
    try:
        while True:
            data = recorder.record(numframes=2048)
            # print(len(data))
            # print(f"Audio level: {np.max(np.abs(data)):.4f}")
    except KeyboardInterrupt:
        print("\nStopped recording")