import time
import numpy as np
import soundcard as sc
import matplotlib.pyplot as plt

# ====== Config ======
FS = 48000           # sample rate
CHUNK = 1024         # frames per block (lower = lower latency, more CPU)
N_BANDS = 32         # number of visual bands
F_MIN, F_MAX = 20, 20000  # visualization range in Hz
SMOOTH = 0.7         # 0..1, higher = smoother/laggier
REF_DBFS = -10       # reference for scaling bars; tweak to taste

# ====== Helpers ======
def logspace_bands(n_bands, fmin, fmax, fs, nfft):
    freqs = np.fft.rfftfreq(nfft, 1/fs)
    edges = np.geomspace(fmin, fmax, n_bands+1)
    # map band edges to FFT bin indices
    idx = np.searchsorted(freqs, edges)
    # ensure strictly increasing and within range
    idx = np.clip(idx, 1, len(freqs)-1)
    # make (start, end) pairs
    bands = [(idx[i-1], idx[i]) for i in range(1, len(idx))]
    return bands, freqs

def dbfs(x, eps=1e-12):
    # x: float array in [-1, 1] typical; compute RMS dBFS
    rms = np.sqrt(np.mean(np.square(x) + eps))
    return 20*np.log10(rms + eps)

def spectrum_db(mono, fs):
    n = len(mono)
    win = np.hanning(n)
    xw = mono * win
    spec = np.fft.rfft(xw, n=n)
    mag = np.abs(spec) / (np.sum(win)/2.0)
    # convert magnitude to dB, relative to 1.0 full-scale sine
    sdb = 20*np.log10(mag + 1e-12)
    return sdb

def band_reduce(sdb, bands):
    vals = []
    for a, b in bands:
        if b > a:
            vals.append(np.max(sdb[a:b]))
        else:
            vals.append(sdb[b])
    return np.array(vals)

# ====== Capture device ======
speaker = sc.default_speaker()  # WASAPI loopback via soundcard

# Precompute band mapping for plotting
bands, freqs = logspace_bands(N_BANDS, F_MIN, F_MAX, FS, CHUNK)
band_centers = [freqs[(a+b)//2] for a,b in bands]

# ====== Plot setup ======
plt.ion()
fig = plt.figure(figsize=(10,5))
ax1 = fig.add_subplot(1, 1, 1)
bars = ax1.bar(range(N_BANDS), np.zeros(N_BANDS))
ax1.set_ylim(-100, 0)  # dB scale
ax1.set_xlim(-0.5, N_BANDS-0.5)
ax1.set_ylabel("dBFS")
ax1.set_title("System Audio Visualizer (Spectrum + Volume)")
ax1.set_xticks(range(N_BANDS))
# show band center labels (roughly)
labels = []
for f in band_centers:
    if f >= 1000:
        labels.append(f"{f/1000:.1f}k")
    else:
        labels.append(f"{int(f)}")
ax1.set_xticklabels(labels, rotation=45, ha="right")

# Simple text VU meter
vu_text = ax1.text(0.99, 0.9, "VU: -- dBFS", transform=ax1.transAxes,
                   ha="right", va="center", fontsize=11)

# Smoothed state
smooth_bands = np.full(N_BANDS, -100.0)

# ====== Main loop ======
with speaker.recorder(samplerate=FS, channels=2) as rec:
    # Warm-up read to prime buffers
    _ = rec.record(numframes=CHUNK)
    while plt.fignum_exists(fig.number):
        block = rec.record(numframes=CHUNK)  # shape: (CHUNK, 2)
        mono = np.mean(block, axis=1).astype(np.float32)

        # Volume (RMS dBFS)
        vol_db = dbfs(mono)

        # Spectrum
        sdb = spectrum_db(mono, FS)
        band_vals = band_reduce(sdb, bands)

        # Normalize visual range a bit (optional gentle compression)
        band_vals = np.clip(band_vals, -100, 0)
        # Optional “anchoring” relative to a reference
        band_vals = np.clip(band_vals - (REF_DBFS - vol_db), -100, 0)

        # Smooth
        smooth_bands = SMOOTH * smooth_bands + (1 - SMOOTH) * band_vals

        # Update bars
        for bar, h in zip(bars, smooth_bands):
            bar.set_height(h)

        # Update VU text
        vu_text.set_text(f"VU: {vol_db:6.1f} dBFS")

        plt.pause(0.001)  # yield to UI
        # Avoid tight loop if plot is closed
        time.sleep(0.001)