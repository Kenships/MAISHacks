import os
import platform
import sys
import time
import subprocess

import psutil
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Load environment variables from .env
load_dotenv()

CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")


def auth_spotify():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope="user-read-playback-state user-modify-playback-state user-read-currently-playing"
    ))

def list_devices(sp):
    """Return list of available devices (dicts)."""
    return sp.devices().get("devices", [])
def get_device_id(sp, device_name=None):
    """
    Return a device_id. If device_name is given, match by name (case-insensitive).
    Otherwise return the current active device_id if any.
    """
    devices = list_devices(sp)
    if device_name:
        for d in devices:
            if d["name"].lower() == device_name.lower():
                return d["id"]
        raise RuntimeError(f"Device named '{device_name}' not found. Available: {[d['name'] for d in devices]}")
    # fall back to active device
    for d in devices:
        if d.get("is_active"):
            return d["id"]
    # no active device
    return None

def transfer_to_device(sp, device_name, force_play=False):
    device_id = get_device_id(sp, device_name)
    sp.transfer_playback(device_id, force_play=force_play)
    return device_id

def pause(sp, device_name=None):
    device_id = get_device_id(sp, device_name)
    sp.pause_playback(device_id=device_id)

def play(sp, device_name=None, uris=None, context_uri=None, position_ms=None):
    """
    Resume or start playback. Optionally pass track URIs, a context_uri (album/playlist),
    or a starting position_ms.
    """
    device_id = get_device_id(sp, device_name)
    sp.start_playback(
        device_id=device_id,
        uris=uris,
        context_uri=context_uri,
        position_ms=position_ms
    )

def next_track(sp, device_name=None):
    device_id = get_device_id(sp, device_name)
    sp.next_track(device_id=device_id)

def previous_track(sp, device_name=None):
    device_id = get_device_id(sp, device_name)
    sp.previous_track(device_id=device_id)


def get_current_volume(sp):
    """Return the active device's current volume percent (0–100)."""
    playback = sp.current_playback()
    if playback and playback.get("device"):
        return playback["device"].get("volume_percent")
    return None


def increase_volume(sp, step=5, device_name=None):
    """Increase volume by `step` percent (default +5)."""
    current = get_current_volume(sp)
    if current is None:
        print("No active device or unable to get current volume.")
        return
    new_volume = min(100, current + step)
    set_volume(sp, new_volume, device_name)
    print(f"Volume increased to {new_volume}%")


def decrease_volume(sp, step=5, device_name=None):
    """Decrease volume by `step` percent (default -5)."""
    current = get_current_volume(sp)
    if current is None:
        print("No active device or unable to get current volume.")
        return
    new_volume = max(0, current - step)
    set_volume(sp, new_volume, device_name)
    print(f"Volume decreased to {new_volume}%")

def set_volume(sp, volume_percent, device_name=None):
    """0–100"""
    volume_percent = max(0, min(100, int(volume_percent)))
    device_id = get_device_id(sp, device_name)
    sp.volume(volume_percent, device_id=device_id)

def playpause(sp, device_name=None):
    """
    Toggle playback:
    - If currently playing, pauses.
    - If currently paused, resumes.
    """
    try:
        playback = sp.current_playback()
        if not playback:
            activate_and_play_here(sp, "Its late")
            print("No active playback found. Start playing something first.")
            return

        is_playing = playback.get("is_playing", False)
        device_id = playback.get("device", {}).get("id") or get_device_id(sp, device_name)

        if is_playing:
            sp.pause_playback(device_id=device_id)
            print("⏸️  Paused playback.")
        else:
            sp.start_playback(device_id=device_id)
            print("▶️  Resumed playback.")

    except Exception as e:
        print(f"Error toggling playback: {e}")

def _local_names():
    # Primary: Windows COMPUTERNAME or hostname
    candidates = set()
    if os.getenv("COMPUTERNAME"):
        candidates.add(os.getenv("COMPUTERNAME"))
    if platform.node():
        candidates.add(platform.node())
    # Common cosmetic variants Spotify may use (esp. macOS)
    user = None
    try:
        user = os.getlogin()
    except Exception:
        user = os.getenv("USERNAME") or os.getenv("USER")
    if user:
        for base in list(candidates) or ["Computer"]:
            candidates.add(f"{user}’s {base}")  # curly apostrophe
            candidates.add(f"{user}'s {base}")  # straight apostrophe
    # Lowercase for comparison
    return {c.strip().lower() for c in candidates if c}

def _is_spotify_running():
    for p in psutil.process_iter(attrs=["name"]):
        try:
            n = p.info["name"]
            if n and "spotify" in n.lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False

def _launch_spotify():
    try:
        if sys.platform.startswith("win"):
            os.startfile("spotify:")  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-a", "Spotify"])
        else:
            subprocess.Popen(["spotify"])
        return True
    except Exception:
        return False

def _find_this_device_id(sp, timeout_sec=20, poll=1.0, explicit_name=None):
    """
    Find THIS computer's device id.
    Priority:
      1) exact name match to explicit_name (if provided)
      2) exact name match to local hostname variants
      3) if only one 'Computer' device exists, use it
    """
    want = {explicit_name.lower()} if explicit_name else set()
    want |= _local_names()

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        devs = sp.devices().get("devices", []) or []
        # 1) exact name match
        for d in devs:
            name = (d.get("name") or "").strip().lower()
            if name in want:
                return d.get("id")
        # 2) single 'Computer' fall-back
        computers = [d for d in devs if d.get("type") == "Computer"]
        if len(computers) == 1:
            return computers[0].get("id")
        time.sleep(poll)
    return None

def _verify_active(sp, device_id, attempts=6, wait=0.5):
    """Confirm the active device equals device_id."""
    for _ in range(attempts):
        pb = sp.current_playback()
        if pb and pb.get("device", {}).get("id") == device_id:
            return True
        time.sleep(wait)
    return False

# ---------- main combined action ----------
def activate_and_play_here(sp, playlist_uri=None, shuffle=True, wait_open=8, device_name=None):
    """
    Ensure THIS device is the active Spotify device, then shuffle+play a playlist.
    - Launches Spotify locally if needed
    - Resolves this machine's Spotify device and transfers playback *here*
    - Verifies activation before starting playback
    - If playlist_uri is None, uses your FIRST playlist
    """
    # Normalize playlist link to Spotify URI
    def norm_uri(u):
        if not u:
            return u
        if u.startswith("https://open.spotify.com/playlist/"):
            return "spotify:playlist:" + u.split("/")[-1].split("?")[0]
        return u

    playlist_uri = norm_uri(playlist_uri)

    # 0) Make sure Spotify app is open locally
    if not _is_spotify_running():
        _launch_spotify()
        time.sleep(wait_open)

    # 1) Resolve THIS device id
    device_id = _find_this_device_id(sp, timeout_sec=wait_open, explicit_name=device_name)
    if not device_id:
        raise RuntimeError(
            "Could not identify this computer as a Spotify device. "
            "Open the Spotify desktop app and make sure you're logged in."
        )

    # 2) Transfer playback HERE (make this the active device)
    sp.transfer_playback(device_id=device_id, force_play=False)
    if not _verify_active(sp, device_id):
        raise RuntimeError("Failed to set this device as active. Try again after the app fully loads.")

    # 3) Choose playlist if none provided
    if not playlist_uri:
        pls = sp.current_user_playlists(limit=1)
        if not pls.get("items"):
            raise RuntimeError("No playlists found on this account.")
        playlist_uri = pls["items"][0]["uri"]
        playlist_name = pls["items"][0]["name"]
    else:
        playlist_name = playlist_uri

    # 4) Shuffle + play HERE
    sp.shuffle(bool(shuffle), device_id=device_id)
    sp.start_playback(device_id=device_id, context_uri=playlist_uri)
    print(f"🎯 Active device set to THIS computer.\n🔀▶️  Shuffling and playing: {playlist_name}")