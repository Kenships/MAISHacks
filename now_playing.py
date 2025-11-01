import os
import json
from datetime import timedelta
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# --- Config ---
CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID", "c941694026c34cdf810a1e5538de293e")
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET", "387fca1d5c074596affd8d218ec7f705")
REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
SCOPES = "user-read-playback-state user-read-currently-playing"
# ---------------

def ms_to_clock(ms: int) -> str:
    if ms is None:
        return "0:00"
    td = timedelta(milliseconds=ms)
    # Strip hours if 0 to get M:SS
    total_seconds = int(td.total_seconds())
    m, s = divmod(total_seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def main():
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPES,
        open_browser=True,
        cache_path=".spotipy_cache"  # token cache
    ))

    # Two endpoints:
    # 1) current_user_playing_track() -> details about the item + progress
    # 2) current_playback()          -> adds device, repeat/shuffle, volume, etc.
    playing = sp.current_user_playing_track()
    playback = sp.current_playback()

    if not playing and not playback:
        print("Nothing is playing on your account right now.")
        return

    # Safely pull fields from both payloads
    item = (playing or {}).get("item") or (playback or {}).get("item")
    is_playing = (playing or playback or {}).get("is_playing")
    progress_ms = (playing or {}).get("progress_ms") or (playback or {}).get("progress_ms")
    device = (playback or {}).get("device") or {}
    context = (playback or {}).get("context") or (playing or {}).get("context") or {}

    # Track / album / artists
    track = {
        "id": item.get("id") if item else None,
        "uri": item.get("uri") if item else None,
        "name": item.get("name") if item else None,
        "artists": [{"name": a["name"], "id": a["id"], "uri": a["uri"]} for a in (item.get("artists") or [])] if item else [],
        "album": {
            "name": item.get("album", {}).get("name") if item else None,
            "id": item.get("album", {}).get("id") if item else None,
            "uri": item.get("album", {}).get("uri") if item else None,
            "release_date": item.get("album", {}).get("release_date") if item else None,
            "images": item.get("album", {}).get("images") or []
        } if item else None,
        "duration_ms": item.get("duration_ms") if item else None,
        "explicit": item.get("explicit") if item else None,
        "popularity": item.get("popularity") if item else None,
        "external_urls": item.get("external_urls") if item else None,
        "preview_url": item.get("preview_url") if item else None,
        "track_number": item.get("track_number") if item else None,
        "disc_number": item.get("disc_number") if item else None,
    }

    # Playback / device / context
    details = {
        "is_playing": bool(is_playing),
        "progress_ms": progress_ms,
        "progress": ms_to_clock(progress_ms),
        "duration": ms_to_clock(track["duration_ms"]) if track["duration_ms"] else None,
        "shuffle_state": (playback or {}).get("shuffle_state"),
        "repeat_state": (playback or {}).get("repeat_state"),
        "timestamp": (playback or {}).get("timestamp"),
        "device": {
            "id": device.get("id"),
            "name": device.get("name"),
            "type": device.get("type"),
            "volume_percent": device.get("volume_percent"),
            "is_active": device.get("is_active"),
            "is_private_session": device.get("is_private_session"),
            "supports_volume": device.get("supports_volume"),
        },
        "context": {
            "type": context.get("type"),
            "uri": context.get("uri"),
            "href": context.get("href"),
            "external_urls": (context.get("external_urls") or {}),
        }
    }

    # Merge into one payload
    payload = {"track": track, "playback": details}

    # Pretty print
    print("\n=== Now Playing ===")
    title = track["name"] or "Unknown"
    artist_names = ", ".join(a["name"] for a in track["artists"]) or "Unknown Artist"
    print(f"{title} — {artist_names}")
    duration_str = ms_to_clock(track["duration_ms"]) if track.get("duration_ms") else None
    if details["progress"] and duration_str:
        print(f"{details['progress']} / {duration_str}")
    if details["device"]["name"]:
        print(f"Device: {details['device']['name']} ({details['device']['type']})  "
              f"Volume: {details['device']['volume_percent']}%")
    if track["album"] and track["album"]["name"]:
        print(f"Album: {track['album']['name']} (released {track['album']['release_date']})")

    # Full raw JSON to file for inspection
    with open("now_playing.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print("\nWrote full details to now_playing.json")
    # If you want to also see the raw Spotify responses, uncomment:
    # with open("raw_playing.json", "w", encoding="utf-8") as f: json.dump(playing, f, indent=2)
    # with open("raw_playback.json", "w", encoding="utf-8") as f: json.dump(playback, f, indent=2)

if __name__ == "__main__":
    main()
