import soundcard as sc
import numpy as np
import customtkinter as ctk
import tkinter as tk
from tkinter import Canvas
from PIL import Image, ImageTk
import warnings, time

warnings.filterwarnings("ignore", category=RuntimeWarning, module="soundcard")

# =========================
# customtkinter setup
# =========================
ctk.set_appearance_mode("dark")          # "light" | "dark" | "system"
ctk.set_default_color_theme("dark-blue") # "blue" | "green" | "dark-blue"
ctk.set_widget_scaling(1.0)
ctk.set_window_scaling(1.0)

# =========================
# Performance knobs (your tweaked values kept)
# =========================
CANVAS_SIZE    = 480
INTERNAL_SIZE  = 320
N_ANGLE        = 360
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
# Geometry (precompute)
# =========================
cx = cy = INTERNAL_SIZE // 2
FEATHER_PX = 3.0
R_MAX_ALLOWED = min(cx, cy) - FEATHER_PX - 1

yy, xx = np.mgrid[0:INTERNAL_SIZE, 0:INTERNAL_SIZE]
dx, dy = xx - cx, yy - cy
rr = np.hypot(dx, dy)
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
# Visual parameters (from your version)
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
PULSE_GAIN        = 0.6
PULSE_DECAY       = 0.5
PULSE_STRENGTH    = 0.2
RING_MARGIN_PX    = 14.0

# Bass detection config
BASS_MAX_HZ       = 160.0
BASS_WEIGHT_EXP   = 0.4
FLUX_HISTORY      = 90
FLUX_K_MAD        = 4.0
REFRACTORY_SEC    = 0.1
MIN_ACTIVITY      = 0.1

# Precompute bass band mask & weights
bass_band_mask = band_centers <= BASS_MAX_HZ
if not np.any(bass_band_mask):
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

pulse_state = 0.0
prev_norm_for_flux_bass = None
flux_prev2 = 0.0
flux_prev1 = 0.0
flux_hist = np.zeros(FLUX_HISTORY, dtype=np.float32)
flux_hist_count = 0
flux_hist_idx = 0
last_trigger_time = 0.0

# Image and per-canvas handles
tk_img = None  # keep a strong ref to avoid GC
canvas_items = {}  # canvas -> {"img_id": int, "oval_id": int}

# =========================
# Multi-canvas helpers
# =========================
def register_canvas(cnv: Canvas):
    """Register a canvas to receive frames."""
    canvas_items[cnv] = {"img_id": None, "oval_id": None}

# =========================
# Core builders (compute HALF, then mirror)
# =========================
def build_from_audio(levels_01, delta_01, activity_01):
    idx = np.arange(num_bands, dtype=np.float32)
    phi = 2.0 * np.pi * (idx / num_bands)

    w1 = levels_01 + 1e-6
    z1 = np.sum(w1 * np.exp(1j * phi))
    hue_energy = (np.angle(z1) % (2 * np.pi)) / (2 * np.pi)

    w2 = delta_01 + 1e-6
    z2 = np.sum(w2 * np.exp(1j * phi))
    hue_change = (np.angle(z2) % (2 * np.pi)) / (2 * np.pi)

    hue_base = (1.0 - HUE_DELTA_BLEND) * hue_energy + HUE_DELTA_BLEND * hue_change
    hue_base %= 1.0

    band_h0 = (hue_base + HUE_BAND_SPREAD * (idx / max(1, num_bands - 1))) % 1.0
    band_h1 = (band_h0 + HUE_AMP_WOBBLE * levels_01) % 1.0
    band_h  = hue_lerp(band_h0, band_h1, levels_01)
    band_s  = np.ones_like(band_h)  # full saturation
    band_v  = np.clip(VAL_BASE + VAL_AMP_BOOST * activity_01 + VAL_BAND_BOOST * levels_01, 0.0, 1.0)
    band_rgb = hsv_to_rgb_numpy(band_h, band_s, band_v).astype(np.float32)

    wts = 1.0 / np.sqrt(1.0 + idx); wts /= wts.max(); wts[:3] *= BASS_EMPHASIS
    band_def = wts * (levels_01 - levels_01.mean())
    m = np.max(np.abs(band_def))
    if m > 1e-6: band_def /= m
    band_def *= (1.0 - REST_DEFORM_PULL * (1.0 - activity_01))

    pal_half = band_rgb[i0_half] * (1.0 - t_half[:, None]) + band_rgb[i1_half] * (t_half[:, None])
    def_half = band_def[i0_half] * (1.0 - t_half) + band_def[i1_half] * (t_half)

    pal_full = np.concatenate([pal_half, pal_half[::-1]], axis=0)
    def_full = np.concatenate([def_half, def_half[::-1]], axis=0)
    return pal_full.astype(np.uint8), def_full.astype(np.float32)

# =========================
# UI (customtkinter window + canvases)
# =========================
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Audio Reactive Gradient (customtkinter) • Bass-Only Pulse")
        self.configure(fg_color="black")
        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left frame
        self.left = ctk.CTkFrame(self, corner_radius=16)
        self.left.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")
        self.left.grid_columnconfigure(0, weight=1)
        self.left.grid_rowconfigure(0, weight=1)

        # # Right frame
        # self.right = ctk.CTkFrame(self, corner_radius=16)
        # self.right.grid(row=0, column=1, padx=12, pady=12, sticky="nsew")
        # self.right.grid_columnconfigure(0, weight=1)
        # self.right.grid_rowconfigure(0, weight=1)

        # Put native tk.Canvas inside the CTkFrames (fastest drawing)
        self.canvas1 = tk.Canvas(self.left, width=CANVAS_SIZE, height=CANVAS_SIZE,
                                 bg="black", highlightthickness=0, bd=0, relief="flat")
        self.canvas1.grid(row=0, column=0, padx=10, pady=10)

        # self.canvas2 = tk.Canvas(self.right, width=CANVAS_SIZE, height=CANVAS_SIZE,
        #                          bg="black", highlightthickness=0, bd=0, relief="flat")
        # self.canvas2.grid(row=0, column=0, padx=10, pady=10)

        # Register both canvases for rendering
        register_canvas(self.canvas1)
        # register_canvas(self.canvas2)

# =========================
# Audio loop (optimized)
# =========================
rec = loopback.recorder(samplerate=fs); rec.__enter__()
TARGET_DT = 1.0 / TARGET_FPS

def update_frame(app: App):
    global levels, prev_lvls, delta_ema, loud_state
    global pulse_state, prev_norm_for_flux_bass, flux_prev2, flux_prev1
    global flux_hist, flux_hist_idx, flux_hist_count, last_trigger_time
    global tk_img

    t0 = time.perf_counter()
    try:
        data = rec.record(numframes=chunk)
        data = data.mean(axis=1).astype(np.float32) if data.ndim > 1 else data.astype(np.float32)

        spec = np.fft.rfft(data * win)
        mag  = np.abs(spec)
        mag_valid = mag[valid_bins]
        band_sum = np.bincount(bin_band_valid, weights=mag_valid, minlength=num_bands).astype(np.float32)
        amps = band_sum / band_counts

        med = float(np.median(amps)) + 1e-8
        p90 = float(np.percentile(amps, 90)) + 1e-8
        norm = np.clip((amps - med) / (p90 - med), 0.0, 1.0)

        # Bass-only spectral flux
        bass_norm = norm[bass_band_mask]
        if prev_norm_for_flux_bass is None:
            flux_bass_now = 0.0
        else:
            pos = np.clip(bass_norm - prev_norm_for_flux_bass, 0.0, 1.0)
            if bass_weights.shape[0] == pos.shape[0]:
                flux_bass_now = float(np.sum(pos * bass_weights))
            else:
                flux_bass_now = float(np.mean(pos))
        prev_norm_for_flux_bass = bass_norm.copy()

        # Band smoothing (visuals)
        rising = norm > levels
        levels = np.where(
            rising,
            ALPHA_ATTACK  * levels + (1 - ALPHA_ATTACK)  * norm,
            ALPHA_RELEASE * levels + (1 - ALPHA_RELEASE) * norm
        )

        delta = np.clip(levels - prev_lvls, 0.0, 1.0)
        delta_ema = 0.70 * delta_ema + 0.30 * delta
        prev_lvls = levels.copy()

        loud_now = float(np.sqrt(np.mean(levels * levels)))
        if loud_now > loud_state:
            loud_state = ALPHA_LOUD_ATTACK  * loud_state + (1 - ALPHA_LOUD_ATTACK)  * loud_now
        else:
            loud_state = ALPHA_LOUD_RELEASE * loud_state + (1 - ALPHA_LOUD_RELEASE) * loud_now
        activity = float(np.clip(loud_state, 0.0, 1.0))

        # Strong bass-beat detection (adaptive, gated)
        now_time = time.perf_counter()
        if flux_hist_count < FLUX_HISTORY:
            flux_hist[flux_hist_idx] = flux_prev1
            flux_hist_count += 1
        else:
            flux_hist[flux_hist_idx] = flux_prev1
        flux_hist_idx = (flux_hist_idx + 1) % FLUX_HISTORY

        if flux_hist_count >= 10:
            med_flux = float(np.median(flux_hist[:flux_hist_count]))
            mad = float(np.median(np.abs(flux_hist[:flux_hist_count] - med_flux))) + 1e-9
            thresh = med_flux + FLUX_K_MAD * (1.4826 * mad)
        else:
            thresh = 1.0

        is_peak = (flux_prev1 > flux_prev2) and (flux_prev1 > flux_bass_now)
        strong_enough = (flux_prev1 > thresh)
        refractory_ok = (now_time - last_trigger_time) >= REFRACTORY_SEC
        active_enough = (activity >= MIN_ACTIVITY)

        pulse_state *= PULSE_DECAY
        if is_peak and strong_enough and refractory_ok and active_enough:
            pulse_state += PULSE_GAIN
            last_trigger_time = now_time

        flux_prev2, flux_prev1 = flux_prev1, flux_bass_now

        # Build ring
        pal_full, deform_full = build_from_audio(levels, delta_ema, activity)

        max_def = float(np.max(np.abs(deform_full)))
        den = max(1e-6, 1.0 + DEFORM_SCALE * max_def)
        r_base_dyn = (R_MAX_ALLOWED * (1.0 - SAFETY)) / den
        r_per_angle = r_base_dyn * (1.0 + DEFORM_SCALE * deform_full)
        r_per_angle = np.clip(r_per_angle, 0.0, R_MAX_ALLOWED - 2.0)

        r_map = r_per_angle[angle_idx_map_full]
        dist  = r_map - rr
        alpha = np.clip(dist / FEATHER_PX + 1.0, 0.0, 1.0)
        alpha = np.where(rr <= (R_MAX_ALLOWED + FEATHER_PX), alpha, 0.0)

        color = pal_full[angle_idx_map_full]
        img_arr_small = (alpha[..., None] * color).astype(np.uint8)

        # Upscale for display (shared for all canvases)
        img = Image.fromarray(img_arr_small, "RGB").resize((CANVAS_SIZE, CANVAS_SIZE), Image.BILINEAR)
        # keep strong ref so Tk doesn't garbage-collect it
        global tk_img
        tk_img = ImageTk.PhotoImage(img)

        # White center geometry
        r_inner_base_small = R_MAX_ALLOWED * INNER_RADIUS_RATIO
        r_inner_small = r_inner_base_small * (1.0 + PULSE_STRENGTH * min(1.0, pulse_state))
        r_inner_small = min(r_inner_small, R_MAX_ALLOWED - RING_MARGIN_PX)
        scale  = CANVAS_SIZE / INTERNAL_SIZE
        r_inner = r_inner_small * scale

        # Blit to all registered canvases
        for cnv, ids in canvas_items.items():
            if ids["img_id"] is None:
                ids["img_id"] = cnv.create_image(CANVAS_SIZE//2, CANVAS_SIZE//2, image=tk_img)
            else:
                cnv.itemconfig(ids["img_id"], image=tk_img)

            cx_out = cy_out = CANVAS_SIZE // 2
            coords = (cx_out - r_inner, cy_out - r_inner, cx_out + r_inner, cy_out + r_inner)
            if ids["oval_id"] is None:
                ids["oval_id"] = cnv.create_oval(*coords, fill="white", outline="")
            else:
                cnv.coords(ids["oval_id"], *coords)
                cnv.tag_raise(ids["oval_id"])

        # Frame pacing
        elapsed = time.perf_counter() - t0
        delay_ms = max(1, int(1000 * max(0.0, (1.0 / TARGET_FPS) - elapsed)))
        app.after(delay_ms, lambda: update_frame(app))

    except Exception as e:
        print("Error:", e)
        try:
            rec.__exit__(None, None, None)
        finally:
            app.destroy()

# =========================
# Run
# =========================
if __name__ == "__main__":
    app = App()
    update_frame(app)
    app.protocol("WM_DELETE_WINDOW", lambda: (rec.__exit__(None, None, None), app.destroy()))
    app.mainloop()
