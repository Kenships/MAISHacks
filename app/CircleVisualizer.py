import soundcard as sc
import numpy as np
import tkinter as tk
from tkinter import Canvas
from PIL import Image, ImageTk
import warnings, time

warnings.filterwarnings("ignore", category=RuntimeWarning, module="soundcard")

# =========================
# Performance knobs
# =========================
CANVAS_SIZE    = 480   # output size you see
INTERNAL_SIZE  = 320   # render size (lower = faster: 256–360)
N_ANGLE        = 360   # total angles (must be even for mirroring)
NUM_BANDS      = 16
FFT_CHUNK      = 2048
TARGET_FPS     = 90
assert N_ANGLE % 2 == 0, "N_ANGLE must be even for mirroring."
N_HALF = N_ANGLE // 2

# =========================
# Audio device
# =========================
default_speaker = sc.default_speaker()
try:
    loopback = sc.get_microphone(id=str(default_speaker.name), include_loopback=True)
except Exception:
    mics = sc.all_microphones(include_loopback=True)
    loopback = [mic for mic in mics if "loopback" in mic.name.lower()][0]
print(f"Recording from: {loopback.name}")

# =========================
# Tk window
# =========================
root = tk.Tk()
root.title("Audio Reactive Gradient (Half+Mirror) • Bass-Only Pulse")
root.configure(bg="black")
canvas = Canvas(root, width=CANVAS_SIZE, height=CANVAS_SIZE, bg="black", highlightthickness=0)
canvas.pack(padx=10, pady=10)

# =========================
# Geometry (precompute)
# =========================
cx = cy = INTERNAL_SIZE // 2
FEATHER_PX = 3.0
R_MAX_ALLOWED = min(cx, cy) - FEATHER_PX - 1

yy, xx = np.mgrid[0:INTERNAL_SIZE, 0:INTERNAL_SIZE]
dx, dy = xx - cx, yy - cy
rr = np.hypot(dx, dy)

# Full-angle map for sampling the final (mirrored) arrays
theta = (np.arctan2(dy, dx) + 2 * np.pi) % (2 * np.pi)
angle_idx_map_full = (theta * (N_ANGLE / (2 * np.pi))).astype(np.int32)

# =========================
# FFT bands (precompute)
# =========================
fs = 44100
chunk = FFT_CHUNK
num_bands = NUM_BANDS
fmin, fmax = 50, fs / 2
band_edges = np.geomspace(fmin, fmax, num_bands + 1)
band_centers = np.sqrt(band_edges[:-1] * band_edges[1:])  # geometric centers (Hz)

win = np.hanning(chunk).astype(np.float32)
freqs = np.fft.rfftfreq(chunk, d=1.0 / fs)
bin_band = np.searchsorted(band_edges, freqs, side='right') - 1
bin_band[(freqs < band_edges[0]) | (freqs >= band_edges[-1])] = -1
valid_bins = bin_band >= 0
bin_band_valid = bin_band[valid_bins]
band_counts = np.bincount(bin_band_valid, minlength=num_bands).astype(np.float32)
band_counts[band_counts == 0] = 1.0

# =========================
# Angle interpolation caches (HALF only)
# =========================
angles_per_band_half = N_HALF / num_bands
pos_angles_half = np.arange(N_HALF, dtype=np.float32) / angles_per_band_half
i0_half = np.floor(pos_angles_half).astype(np.int32) % num_bands
i1_half = (i0_half + 1) % num_bands
t_half  = (pos_angles_half - np.floor(pos_angles_half)).astype(np.float32)

# =========================
# Color helpers
# =========================
def hsv_to_rgb_numpy(h, s, v):
    h = (h % 1.0) * 6.0
    i = np.floor(h).astype(np.int32)
    f = h - i
    p = v * (1 - s)
    q = v * (1 - s * f)
    t = v * (1 - s * (1 - f))
    r = np.choose(i % 6, [v, q, p, p, t, v], mode='clip')
    g = np.choose(i % 6, [t, v, v, q, p, p], mode='clip')
    b = np.choose(i % 6, [p, p, t, v, v, q], mode='clip')
    return (np.clip(np.stack([r, g, b], axis=-1), 0, 1) * 255).astype(np.uint8)

def hue_lerp(h0, h1, t):
    d = ((h1 - h0 + 0.5) % 1.0) - 0.5
    return (h0 + t * d) % 1.0

# =========================
# Visual parameters (full saturation; vivid)
# =========================
HUE_BAND_SPREAD = 0.67
HUE_AMP_WOBBLE  = 0.7
HUE_DELTA_BLEND = 0.35

VAL_BASE        = 0.25
VAL_AMP_BOOST   = 0.85
VAL_BAND_BOOST  = 0.35
REST_VAL        = 0.20
REST_DEFORM_PULL= 0.9

DEFORM_SCALE    = 0.4
BASS_EMPHASIS   = 1.8

# Envelope (attack/decay)
ALPHA_ATTACK       = 0.2
ALPHA_RELEASE      = 0.4
ALPHA_LOUD_ATTACK  = 0.2
ALPHA_LOUD_RELEASE = 0.4

# Compose / safety
INNER_RADIUS_RATIO = 0.50
EXTRA_CLAMP = 2.0
SAFETY = 0.03

# --- Bass-only beat pulse (white center) ---
PULSE_GAIN        = 0.6   # radius bump per *triggered* bass hit
PULSE_DECAY       = 0.5   # decay between hits
PULSE_STRENGTH    = 0.2   # radius growth on each hit
RING_MARGIN_PX    = 14.0   # keep visible ring at peaks

# Bass detection config
BASS_MAX_HZ       = 160.0  # <= this is considered "bass" (try 160–220)
BASS_WEIGHT_EXP   = 0.4   # weighting by (f/f_bass_max)^exp to favor sub-bass
FLUX_HISTORY      = 90     # frames for adaptive stats (~1.8 s @50 FPS)
FLUX_K_MAD        = 4.0    # threshold = median + K * MAD (robust)
REFRACTORY_SEC    = 0.1   # minimum time between hits
MIN_ACTIVITY      = 0.1   # ignore near-silence

# Precompute bass band mask & weights
bass_band_mask = band_centers <= BASS_MAX_HZ
if not np.any(bass_band_mask):
    # ensure at least the lowest band counts as bass
    bass_band_mask[0] = True
bass_centers_norm = np.clip(band_centers[bass_band_mask] / max(1e-6, BASS_MAX_HZ), 0.0, 1.0)
bass_weights = (bass_centers_norm ** BASS_WEIGHT_EXP).astype(np.float32)
bass_weights = bass_weights / (bass_weights.sum() + 1e-9)

# =========================
# State
# =========================
levels     = np.zeros(num_bands, dtype=np.float32)
prev_lvls  = np.zeros(num_bands, dtype=np.float32)
delta_ema  = np.zeros(num_bands, dtype=np.float32)
loud_state = 0.0

# Pulse & bass-beat detection
pulse_state = 0.0
white_oval_id = None

prev_norm_for_flux_bass = None
flux_prev2 = 0.0
flux_prev1 = 0.0
flux_hist = np.zeros(FLUX_HISTORY, dtype=np.float32)
flux_hist_count = 0
flux_hist_idx = 0
last_trigger_time = 0.0

# Tk image handles (persist to avoid GC)
tk_img = None
img_id = None

# =========================
# Core builders (compute HALF, then mirror)
# =========================
def build_from_audio(levels_01, delta_01, activity_01):
    """Return (pal_full[N_ANGLE,3], deform_full[N_ANGLE]) built from half + mirror."""
    idx = np.arange(num_bands, dtype=np.float32)
    phi = 2.0 * np.pi * (idx / num_bands)

    # Hue base from energy + change (purely audio)
    w1 = levels_01 + 1e-6
    z1 = np.sum(w1 * np.exp(1j * phi))
    hue_energy = (np.angle(z1) % (2 * np.pi)) / (2 * np.pi)

    w2 = delta_01 + 1e-6
    z2 = np.sum(w2 * np.exp(1j * phi))
    hue_change = (np.angle(z2) % (2 * np.pi)) / (2 * np.pi)

    hue_base = (1.0 - HUE_DELTA_BLEND) * hue_energy + HUE_DELTA_BLEND * hue_change
    hue_base %= 1.0

    # Per-band hue (full saturation)
    band_h0 = (hue_base + HUE_BAND_SPREAD * (idx / max(1, num_bands - 1))) % 1.0
    band_h1 = (band_h0 + HUE_AMP_WOBBLE * levels_01) % 1.0
    band_h  = hue_lerp(band_h0, band_h1, levels_01)
    band_s  = np.ones_like(band_h)  # full saturation
    band_v  = np.clip(VAL_BASE + VAL_AMP_BOOST * activity_01 + VAL_BAND_BOOST * levels_01, 0.0, 1.0)
    band_rgb = hsv_to_rgb_numpy(band_h, band_s, band_v).astype(np.float32)

    # Deformation with bass emphasis and rest pull
    wts = 1.0 / np.sqrt(1.0 + idx); wts /= wts.max(); wts[:3] *= BASS_EMPHASIS
    band_def = wts * (levels_01 - levels_01.mean())
    m = np.max(np.abs(band_def))
    if m > 1e-6: band_def /= m
    band_def *= (1.0 - REST_DEFORM_PULL * (1.0 - activity_01))

    # Interpolate HALF angles (vectorized)
    pal_half = band_rgb[i0_half] * (1.0 - t_half[:, None]) + band_rgb[i1_half] * (t_half[:, None])
    def_half = band_def[i0_half] * (1.0 - t_half) + band_def[i1_half] * (t_half)

    # Mirror to FULL
    pal_full = np.concatenate([pal_half, pal_half[::-1]], axis=0)
    def_full = np.concatenate([def_half, def_half[::-1]], axis=0)
    return pal_full.astype(np.uint8), def_full.astype(np.float32)

# =========================
# Audio loop (optimized)
# =========================
rec = loopback.recorder(samplerate=fs); rec.__enter__()
TARGET_DT = 1.0 / TARGET_FPS

def update_frame():
    global levels, prev_lvls, delta_ema, loud_state
    global pulse_state, white_oval_id
    global prev_norm_for_flux_bass, flux_prev2, flux_prev1, flux_hist, flux_hist_idx, flux_hist_count, last_trigger_time
    global tk_img, img_id

    t0 = time.perf_counter()
    try:
        # Capture & FFT
        data = rec.record(numframes=chunk)
        data = data.mean(axis=1).astype(np.float32) if data.ndim > 1 else data.astype(np.float32)

        spec = np.fft.rfft(data * win)
        mag  = np.abs(spec)
        mag_valid = mag[valid_bins]
        band_sum = np.bincount(bin_band_valid, weights=mag_valid, minlength=num_bands).astype(np.float32)
        amps = band_sum / band_counts

        # Normalize to [0,1] per band (robust)
        med = float(np.median(amps)) + 1e-8
        p90 = float(np.percentile(amps, 90)) + 1e-8
        norm = np.clip((amps - med) / (p90 - med), 0.0, 1.0)

        # ---------- Bass-only spectral flux ----------
        bass_norm = norm[bass_band_mask]
        if prev_norm_for_flux_bass is None:
            flux_bass_now = 0.0
        else:
            # positive changes in bass bands, weighted (favor sub-bass slightly)
            pos = np.clip(bass_norm - prev_norm_for_flux_bass, 0.0, 1.0)
            if bass_weights.shape[0] == pos.shape[0]:
                flux_bass_now = float(np.sum(pos * bass_weights))
            else:
                # fallback uniform if sizes mismatch
                flux_bass_now = float(np.mean(pos))
        prev_norm_for_flux_bass = bass_norm.copy()

        # Dual-time smoothing per band for visuals
        rising = norm > levels
        levels = np.where(
            rising,
            ALPHA_ATTACK  * levels + (1 - ALPHA_ATTACK)  * norm,
            ALPHA_RELEASE * levels + (1 - ALPHA_RELEASE) * norm
        )

        # Positive band delta (for hue motion)
        delta = np.clip(levels - prev_lvls, 0.0, 1.0)
        delta_ema = 0.70 * delta_ema + 0.30 * delta
        prev_lvls = levels.copy()

        # Global loudness → activity (for colors/shape, not for pulse gating)
        loud_now = float(np.sqrt(np.mean(levels * levels)))
        if loud_now > loud_state:
            loud_state = ALPHA_LOUD_ATTACK  * loud_state + (1 - ALPHA_LOUD_ATTACK)  * loud_now
        else:
            loud_state = ALPHA_LOUD_RELEASE * loud_state + (1 - ALPHA_LOUD_RELEASE) * loud_now
        activity = float(np.clip(loud_state, 0.0, 1.0))

        # =========================
        # Strong bass-beat detection (adaptive, gated)
        # Peak test on prev1; threshold = median + K*MAD from history; refractory + activity gate
        # =========================
        now_time = time.perf_counter()

        # Update history with prev1 (lag-1 peak test)
        if flux_hist_count < FLUX_HISTORY:
            flux_hist[flux_hist_idx] = flux_prev1
            flux_hist_count += 1
        else:
            flux_hist[flux_hist_idx] = flux_prev1
        flux_hist_idx = (flux_hist_idx + 1) % FLUX_HISTORY

        if flux_hist_count >= 10:
            med_flux = float(np.median(flux_hist[:flux_hist_count]))
            mad = float(np.median(np.abs(flux_hist[:flux_hist_count] - med_flux))) + 1e-9
            thresh = med_flux + FLUX_K_MAD * (1.4826 * mad)  # robust sigma
        else:
            thresh = 1.0  # conservative during warmup

        is_peak = (flux_prev1 > flux_prev2) and (flux_prev1 > flux_bass_now)
        strong_enough = (flux_prev1 > thresh)
        refractory_ok = (now_time - last_trigger_time) >= REFRACTORY_SEC
        active_enough = (activity >= MIN_ACTIVITY)

        # Decay pulse every frame
        pulse_state *= PULSE_DECAY

        if is_peak and strong_enough and refractory_ok and active_enough:
            pulse_state += PULSE_GAIN
            last_trigger_time = now_time

        # Rotate flux values for next frame
        flux_prev2, flux_prev1 = flux_prev1, flux_bass_now

        # Build HALF + mirror to FULL for ring color/shape
        pal_full, deform_full = build_from_audio(levels, delta_ema, activity)

        # Adaptive headroom (avoid clipping)
        max_def = float(np.max(np.abs(deform_full)))
        den = max(1e-6, 1.0 + DEFORM_SCALE * max_def)
        r_base_dyn = (R_MAX_ALLOWED * (1.0 - SAFETY)) / den
        r_per_angle = r_base_dyn * (1.0 + DEFORM_SCALE * deform_full)
        r_per_angle = np.clip(r_per_angle, 0.0, R_MAX_ALLOWED - EXTRA_CLAMP)

        # Map to pixels
        r_map = r_per_angle[angle_idx_map_full]
        dist  = r_map - rr
        alpha = np.clip(dist / FEATHER_PX + 1.0, 0.0, 1.0)
        alpha = np.where(rr <= (R_MAX_ALLOWED + FEATHER_PX), alpha, 0.0)

        color = pal_full[angle_idx_map_full]
        img_arr_small = (alpha[..., None] * color).astype(np.uint8)

        # Upscale for display (persist image ref)
        img = Image.fromarray(img_arr_small, "RGB").resize((CANVAS_SIZE, CANVAS_SIZE), Image.BILINEAR)
        tk_img = ImageTk.PhotoImage(img)
        if img_id is None:
            img_id = canvas.create_image(CANVAS_SIZE//2, CANVAS_SIZE//2, image=tk_img)
        else:
            canvas.itemconfig(img_id, image=tk_img)

        # --------- White center: only pulses on STRONG BASS beats ---------
        r_inner_base_small = R_MAX_ALLOWED * INNER_RADIUS_RATIO
        r_inner_small = r_inner_base_small * (1.0 + PULSE_STRENGTH * min(1.0, pulse_state))
        r_inner_small = min(r_inner_small, R_MAX_ALLOWED - RING_MARGIN_PX)

        scale  = CANVAS_SIZE / INTERNAL_SIZE
        r_inner = r_inner_small * scale
        cx_out = cy_out = CANVAS_SIZE // 2
        coords = (cx_out - r_inner, cy_out - r_inner, cx_out + r_inner, cy_out + r_inner)

        global white_oval_id
        if white_oval_id is None:
            white_oval_id = canvas.create_oval(*coords, fill="white", outline="")
        else:
            canvas.coords(white_oval_id, *coords)
            canvas.tag_raise(white_oval_id)
        # -------------------------------------------------------------

        # Frame pacing
        elapsed = time.perf_counter() - t0
        delay_ms = max(1, int(1000 * max(0.0, TARGET_DT - elapsed)))
        root.after(delay_ms, update_frame)

    except Exception as e:
        print("Error:", e)
        try:
            rec.__exit__(None, None, None)
        finally:
            root.quit()

update_frame()
root.protocol("WM_DELETE_WINDOW", lambda: (rec.__exit__(None,None,None), root.destroy()))
root.mainloop()
