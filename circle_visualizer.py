# circle_visualizer.py
import time
import tkinter as tk
from PIL import Image, ImageTk
import numpy as np
import soundcard as sc

class AudioRingVisualizer:
    """
    Audio-reactive gradient ring with internal render resolution + upscale,
    half-ring interpolation + mirror, vivid colors, bass-only center pulse.

    API:
      v = AudioRingVisualizer(parent, size=480, fps=60)
      v.show(); v.start()
      v.stop(); v.hide()
    """

    # ----- Visual / DSP knobs tuned to your prior version -----
    INTERNAL_SIZE    = 320     # render resolution (keeps edges smooth)
    N_ANGLE          = 360     # must be even
    NUM_BANDS        = 16
    FFT_CHUNK        = 2048
    FS               = 44100
    FEATHER_PX       = 3.0
    INNER_RATIO      = 0.50
    DEFORM_SCALE     = 0.4
    BASS_EMPHASIS    = 1.8
    HUE_BAND_SPREAD  = 0.67
    HUE_AMP_WOBBLE   = 0.7
    HUE_DELTA_BLEND  = 0.35
    VAL_BASE         = 0.25
    VAL_AMP_BOOST    = 0.85
    VAL_BAND_BOOST   = 0.35
    RING_MARGIN_PX   = 14.0
    SAFETY           = 0.03

    # smoothing
    ALPHA_ATTACK       = 0.2
    ALPHA_RELEASE      = 0.4
    ALPHA_LOUD_ATTACK  = 0.2
    ALPHA_LOUD_RELEASE = 0.4

    # bass-only pulse
    PULSE_GAIN   = 0.6
    PULSE_DECAY  = 0.5
    PULSE_STRENGTH = 0.2

    # bass detection
    BASS_MAX_HZ   = 160.0
    BASS_WEIGHT_EXP = 0.4
    FLUX_HISTORY  = 90
    FLUX_K_MAD    = 4.0
    REFRACTORY    = 0.1
    MIN_ACTIVITY  = 0.1

    def __init__(self, parent, size=480, fps=60):
        assert self.N_ANGLE % 2 == 0, "N_ANGLE must be even."
        self.parent = parent
        self.size = int(size)  # display size
        self.fps = int(fps)

        self.canvas_w = 640
        self.canvas_h = 480

        # Tk canvas anchored in parent
        self.canvas = tk.Canvas(parent, width=640, height=self.size,
                                bg="#282828", highlightthickness=0, bd=0, relief="flat")

        # Internal render grid (square)
        S = self.INTERNAL_SIZE
        self.cx = self.cy = S // 2
        yy, xx = np.mgrid[0:S, 0:S]
        dx, dy = xx - self.cx, yy - self.cy
        self.rr = np.hypot(dx, dy)
        theta = (np.arctan2(dy, dx) + 2 * np.pi) % (2 * np.pi)
        self.angle_idx_map_full = (theta * (self.N_ANGLE / (2 * np.pi))).astype(np.int32)

        self.R_MAX_ALLOWED = min(self.cx, self.cy) - self.FEATHER_PX - 1

        # angle caches for HALF interpolation
        self.N_HALF = self.N_ANGLE // 2
        self.angles_per_band_half = self.N_HALF / self.NUM_BANDS
        pos_angles_half = np.arange(self.N_HALF, dtype=np.float32) / self.angles_per_band_half
        self.i0_half = np.floor(pos_angles_half).astype(np.int32) % self.NUM_BANDS
        self.i1_half = (self.i0_half + 1) % self.NUM_BANDS
        self.t_half  = (pos_angles_half - np.floor(pos_angles_half)).astype(np.float32)

        # FFT bands
        self.win = np.hanning(self.FFT_CHUNK).astype(np.float32)
        fmin, fmax = 50, self.FS / 2
        self.band_edges = np.geomspace(fmin, fmax, self.NUM_BANDS + 1)
        self.band_centers = np.sqrt(self.band_edges[:-1] * self.band_edges[1:])
        freqs = np.fft.rfftfreq(self.FFT_CHUNK, d=1.0 / self.FS)
        bin_band = np.searchsorted(self.band_edges, freqs, side='right') - 1
        bin_band[(freqs < self.band_edges[0]) | (freqs >= self.band_edges[-1])] = -1
        self.valid_bins = bin_band >= 0
        self.bin_band_valid = bin_band[self.valid_bins]
        self.band_counts = np.bincount(self.bin_band_valid, minlength=self.NUM_BANDS).astype(np.float32)
        self.band_counts[self.band_counts == 0] = 1.0

        # bass mask/weights
        bass_mask = self.band_centers <= self.BASS_MAX_HZ
        if not np.any(bass_mask):
            bass_mask[0] = True
        bass_centers_norm = np.clip(self.band_centers[bass_mask] / max(1e-6, self.BASS_MAX_HZ), 0.0, 1.0)
        self.bass_weights = (bass_centers_norm ** self.BASS_WEIGHT_EXP).astype(np.float32)
        self.bass_weights /= (self.bass_weights.sum() + 1e-9)
        self.bass_mask = bass_mask

        # State
        self.levels     = np.zeros(self.NUM_BANDS, dtype=np.float32)
        self.prev_lvls  = np.zeros_like(self.levels)
        self.delta_ema  = np.zeros_like(self.levels)
        self.loud_state = 0.0
        self.pulse_state = 0.0
        self.prev_norm_for_flux_bass = None
        self.flux_prev2 = 0.0
        self.flux_prev1 = 0.0
        self.flux_hist = np.zeros(self.FLUX_HISTORY, dtype=np.float32)
        self.flux_hist_idx = 0
        self.flux_hist_count = 0
        self.last_trigger_time = 0.0

        # Tk image ids
        self.tk_img = None
        self.img_id = None
        self.white_oval_id = None

        # Load Spotify logo
        try:
            logo = Image.open("SpotifyLogo.png").convert("RGBA")
            self.logo_img = logo
            self.tk_logo = None
            self.logo_id = None
        except Exception as e:
            print("Failed to load Spotify logo:", e)
            self.logo_img = None
            self.tk_logo = None
            self.logo_id = None

        # audio + loop
        self.rec = None
        self.running = False

    # ---------- Public API ----------
    def show(self):
        self.canvas.place(relx=0.5, rely=0.5, anchor="center")

    def hide(self):
        self.canvas.place_forget()

    def start(self):
        if self.running:
            return
        default_speaker = sc.default_speaker()
        try:
            loopback = sc.get_microphone(id=str(default_speaker.name), include_loopback=True)
        except Exception:
            mics = sc.all_microphones(include_loopback=True)
            loopback = [m for m in mics if "loopback" in m.name.lower()][0]
        self.rec = loopback.recorder(samplerate=self.FS)
        self.rec.__enter__()
        self.running = True
        self._tick()

    def stop(self):
        if not self.running:
            return
        self.running = False
        try:
            if self.rec is not None:
                self.rec.__exit__(None, None, None)
        finally:
            self.rec = None
        self.canvas.delete("all")
        self.img_id = None
        self.white_oval_id = None
        self.tk_img = None

    # ---------- Core ----------
    def _tick(self):
        if not self.running:
            return
        t0 = time.perf_counter()
        try:
            # Audio
            data = self.rec.record(numframes=self.FFT_CHUNK)
            data = data.mean(axis=1).astype(np.float32) if data.ndim > 1 else data.astype(np.float32)

            spec = np.fft.rfft(data * self.win)
            mag  = np.abs(spec)
            mag_valid = mag[self.valid_bins]
            band_sum = np.bincount(self.bin_band_valid, weights=mag_valid, minlength=self.NUM_BANDS).astype(np.float32)
            amps = band_sum / self.band_counts

            # robust normalize
            med = float(np.median(amps)) + 1e-8
            p90 = float(np.percentile(amps, 90)) + 1e-8
            norm = np.clip((amps - med) / (p90 - med), 0.0, 1.0)

            # Bass-only spectral flux (lag-1 peak)
            bass_norm = norm[self.bass_mask]
            if self.prev_norm_for_flux_bass is None:
                flux_bass_now = 0.0
            else:
                pos = np.clip(bass_norm - self.prev_norm_for_flux_bass, 0.0, 1.0)
                if self.bass_weights.shape[0] == pos.shape[0]:
                    flux_bass_now = float(np.sum(pos * self.bass_weights))
                else:
                    flux_bass_now = float(np.mean(pos))
            self.prev_norm_for_flux_bass = bass_norm.copy()

            # per-band smoothing
            rising = norm > self.levels
            self.levels = np.where(
                rising,
                self.ALPHA_ATTACK  * self.levels + (1 - self.ALPHA_ATTACK)  * norm,
                self.ALPHA_RELEASE * self.levels + (1 - self.ALPHA_RELEASE) * norm
            )
            delta = np.clip(self.levels - self.prev_lvls, 0.0, 1.0)
            self.delta_ema = 0.70 * self.delta_ema + 0.30 * delta
            self.prev_lvls = self.levels.copy()

            # activity (loudness)
            loud_now = float(np.sqrt(np.mean(self.levels * self.levels)))
            if loud_now > self.loud_state:
                self.loud_state = self.ALPHA_LOUD_ATTACK  * self.loud_state + (1 - self.ALPHA_LOUD_ATTACK)  * loud_now
            else:
                self.loud_state = self.ALPHA_LOUD_RELEASE * self.loud_state + (1 - self.ALPHA_LOUD_RELEASE) * loud_now
            activity = float(np.clip(self.loud_state, 0.0, 1.0))

            # Update flux history on prev1 (lag-1)
            if self.flux_hist_count < self.FLUX_HISTORY:
                self.flux_hist[self.flux_hist_idx] = self.flux_prev1
                self.flux_hist_count += 1
            else:
                self.flux_hist[self.flux_hist_idx] = self.flux_prev1
            self.flux_hist_idx = (self.flux_hist_idx + 1) % self.FLUX_HISTORY

            if self.flux_hist_count >= 10:
                medf = float(np.median(self.flux_hist[:self.flux_hist_count]))
                mad  = float(np.median(np.abs(self.flux_hist[:self.flux_hist_count] - medf))) + 1e-9
                thresh = medf + self.FLUX_K_MAD * (1.4826 * mad)
            else:
                thresh = 1.0

            # Bass beat trigger → white center pulse
            now_time = time.perf_counter()
            is_peak = (self.flux_prev1 > self.flux_prev2) and (self.flux_prev1 > flux_bass_now)
            strong_enough = (self.flux_prev1 > thresh)
            refractory_ok = (now_time - self.last_trigger_time) >= self.REFRACTORY
            active_enough = (activity >= self.MIN_ACTIVITY)

            self.pulse_state *= self.PULSE_DECAY
            if is_peak and strong_enough and refractory_ok and active_enough:
                self.pulse_state += self.PULSE_GAIN
                self.last_trigger_time = now_time

            self.flux_prev2, self.flux_prev1 = self.flux_prev1, flux_bass_now

            # ---- Build colors & deformation (half → mirror) ----
            band_h, band_v = self._band_hv(self.levels, self.delta_ema, activity)
            band_rgb = self._hsv_to_rgb_numpy(band_h, np.ones_like(band_h), band_v).astype(np.float32)

            # deformation with bass emphasis
            idx = np.arange(self.NUM_BANDS, dtype=np.float32)
            wts = 1.0 / np.sqrt(1.0 + idx)
            wts /= wts.max()
            wts[:3] *= self.BASS_EMPHASIS
            band_def = wts * (self.levels - self.levels.mean())
            m = np.max(np.abs(band_def))
            if m > 1e-6:
                band_def /= m
            band_def *= (1.0 - 0.9 * (1.0 - activity))  # REST_DEFORM_PULL=0.9

            # interpolate HALF angles
            pal_half = band_rgb[self.i0_half] * (1.0 - self.t_half[:, None]) + band_rgb[self.i1_half] * (self.t_half[:, None])
            def_half = band_def[self.i0_half] * (1.0 - self.t_half) + band_def[self.i1_half] * (self.t_half)

            # mirror to FULL
            pal_full = np.concatenate([pal_half, pal_half[::-1]], axis=0).astype(np.uint8)
            def_full = np.concatenate([def_half, def_half[::-1]], axis=0).astype(np.float32)

            # adaptive headroom
            max_def = float(np.max(np.abs(def_full)))
            den = max(1e-6, 1.0 + self.DEFORM_SCALE * max_def)
            r_base_dyn = (self.R_MAX_ALLOWED * (1.0 - self.SAFETY)) / den
            r_per_angle = r_base_dyn * (1.0 + self.DEFORM_SCALE * def_full)
            r_per_angle = np.clip(r_per_angle, 0.0, self.R_MAX_ALLOWED - 2.0)

            # render to internal RGB then upscale
            r_map = r_per_angle[self.angle_idx_map_full]
            dist  = r_map - self.rr
            alpha = np.clip(dist / self.FEATHER_PX + 1.0, 0.0, 1.0)
            alpha = np.where(self.rr <= (self.R_MAX_ALLOWED + self.FEATHER_PX), alpha, 0.0)

            color = pal_full[self.angle_idx_map_full]
            img_arr_small = (alpha[..., None] * color).astype(np.uint8)

            # fill empty pixels with #282828 instead of black
            bg_color = np.array([40, 40, 40], dtype=np.uint8)  # hex #282828 = (40,40,40)
            img_arr_small = np.where(alpha[..., None] > 0, img_arr_small, bg_color)

            # upscale to display size
            img = Image.fromarray(img_arr_small, "RGB").resize((self.size, self.size), Image.BILINEAR)
            self.tk_img = ImageTk.PhotoImage(img)
            cx_out = self.canvas_w // 2
            cy_out = self.canvas_h // 2
            if self.img_id is None:
                self.img_id = self.canvas.create_image(cx_out, cy_out, image=self.tk_img)
            else:
                self.canvas.itemconfig(self.img_id, image=self.tk_img)
                # ensure it stays centered even if canvas resizes later
                self.canvas.coords(self.img_id, cx_out, cy_out)

            # white center pulses only on strong bass
            r_inner_base_small = self.R_MAX_ALLOWED * self.INNER_RATIO
            r_inner_small = r_inner_base_small * (1.0 + self.PULSE_STRENGTH * min(1.0, self.pulse_state))
            r_inner_small = min(r_inner_small, self.R_MAX_ALLOWED - self.RING_MARGIN_PX)

            scale = self.size / self.INTERNAL_SIZE
            r_inner = r_inner_small * scale
            cx_out = self.canvas_w // 2
            cy_out = self.canvas_h // 2
            coords = (cx_out - r_inner, cy_out - r_inner, cx_out + r_inner, cy_out + r_inner)

            # Draw Spotify logo instead of white oval
            if self.logo_img is not None:
                # Scale logo to current pulse size
                diameter = int(2 * r_inner)
                logo_resized = self.logo_img.resize((diameter, diameter), Image.LANCZOS)
                self.tk_logo = ImageTk.PhotoImage(logo_resized)
                if self.logo_id is None:
                    self.logo_id = self.canvas.create_image(cx_out, cy_out, image=self.tk_logo)
                else:
                    self.canvas.itemconfig(self.logo_id, image=self.tk_logo)
                    self.canvas.coords(self.logo_id, cx_out, cy_out)
                    self.canvas.tag_raise(self.logo_id)
            else:
                # fallback white circle
                if self.white_oval_id is None:
                    self.white_oval_id = self.canvas.create_oval(*coords, fill="white", outline="")
                else:
                    self.canvas.coords(self.white_oval_id, *coords)
                    self.canvas.tag_raise(self.white_oval_id)

        except Exception as e:
            print("Visualizer error:", e)
            self.stop()

        if self.running:
            delay_ms = max(1, int(1000 / self.fps))
            self.canvas.after(delay_ms, self._tick)

    # ----- helpers -----
    def _band_hv(self, levels_01, delta_01, activity_01):
        idx = np.arange(self.NUM_BANDS, dtype=np.float32)
        phi = 2.0 * np.pi * (idx / self.NUM_BANDS)

        w1 = levels_01 + 1e-6
        z1 = np.sum(w1 * np.exp(1j * phi))
        hue_energy = (np.angle(z1) % (2 * np.pi)) / (2 * np.pi)

        w2 = delta_01 + 1e-6
        z2 = np.sum(w2 * np.exp(1j * phi))
        hue_change = (np.angle(z2) % (2 * np.pi)) / (2 * np.pi)

        hue_base = (1.0 - self.HUE_DELTA_BLEND) * hue_energy + self.HUE_DELTA_BLEND * hue_change
        hue_base %= 1.0

        h0 = (hue_base + self.HUE_BAND_SPREAD * (idx / max(1, self.NUM_BANDS - 1))) % 1.0
        h1 = (h0 + self.HUE_AMP_WOBBLE * levels_01) % 1.0
        # shortest-arc hue lerp
        d = ((h1 - h0 + 0.5) % 1.0) - 0.5
        h = (h0 + levels_01 * d) % 1.0

        v = np.clip(self.VAL_BASE + self.VAL_AMP_BOOST * activity_01 + self.VAL_BAND_BOOST * levels_01, 0.0, 1.0)
        return h, v

    @staticmethod
    def _hsv_to_rgb_numpy(h, s, v):
        h = (h % 1.0) * 6.0
        i = np.floor(h).astype(np.int32)
        f = h - i
        p = v * (1 - s)
        q = v * (1 - s * f)
        t = v * (1 - s * (1 - f))
        r = np.choose(i % 6, [v, q, p, p, t, v], mode='clip')
        g = np.choose(i % 6, [t, v, v, q, p, p], mode='clip')
        b = np.choose(i % 6, [p, p, t, v, v, q], mode='clip')
        return (np.clip(np.stack([r, g, b], axis=-1), 0, 1) * 255.0)
