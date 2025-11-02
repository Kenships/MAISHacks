import asyncio
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from datetime import datetime, timezone, timedelta
from typing import Optional
import os                      # <-- NEW
from dotenv import load_dotenv  # <-- NEW

# --- NEW: Load the .env file ---
load_dotenv()

from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as SMTC,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
)

class MediaInfo:
    """Fetch current Windows media session info as a data object."""

    def __init__(self):
        # --- MODIFIED: Load keys from os.getenv ---
        CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
        CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")

        self.sp = None
        if CLIENT_ID and CLIENT_SECRET: # Check if keys were found
            try:
                auth_manager = SpotifyClientCredentials(client_id=CLIENT_ID,
                                                      client_secret=CLIENT_SECRET)
                self.sp = spotipy.Spotify(auth_manager=auth_manager)
                print("Spotipy (Spotify API) initialized successfully from .env.")
            except Exception as e:
                print(f"Error initializing Spotipy: {e}")
                print("Spotify album art will not be available.")
        else:
            print("SPOTIPY_CLIENT_ID or SPOTIPY_CLIENT_SECRET not in .env file.")
            print("Spotify album art will not be available.")
            

    def get(self) -> Optional[dict]:
        """Return a dict with all current session info, or None if no session."""
        return asyncio.run(self._get_info())

    async def _get_info(self) -> Optional[dict]:
        manager = await SMTC.request_async()
        session = manager.get_current_session()
        if not session:
            sessions = manager.get_sessions()
            session = next((s for s in sessions if s.get_playback_info()), None)
        if not session:
            return None

        info = session.get_playback_info()
        tl = session.get_timeline_properties()
        props = await session.try_get_media_properties_async()

        # Defensive defaults
        position = getattr(tl, "position", None)
        end_time = getattr(tl, "end_time", None)
        last_update = getattr(tl, "last_updated_time", None)
        rate = getattr(info, "playback_rate", 1.0) or 1.0

        # Compute live position
        if (
            info.playback_status == PlaybackStatus.PLAYING
            and position is not None
            and last_update is not None
        ):
            now = datetime.now(timezone.utc)
            elapsed = now - last_update
            if isinstance(elapsed, timedelta):
                try:
                    position = position + (elapsed * rate)
                except TypeError:
                    position = position + elapsed

        pos_sec = position.total_seconds() if position else None
        dur_sec = end_time.total_seconds() if end_time else None

        # --- Get Album Art URL from Spotipy ---
        album_art_url = None
        app_id = session.source_app_user_model_id
        
        if "spotify" in app_id.lower() and props.title and self.sp:
            try:
                query = f"track:{props.title} artist:{props.artist}"
                results = self.sp.search(q=query, type="track", limit=1)
                
                if results and results["tracks"]["items"]:
                    track = results["tracks"]["items"][0]
                    if track["album"]["images"]:
                        album_art_url = track["album"]["images"][0]["url"]
            except Exception as e:
                print(f"Error searching Spotify: {e}")

        return {
            "app_id": app_id,
            "title": props.title,
            "artist": props.artist,
            "album": props.album_title,
            "album_artist": props.album_artist,
            "genres": list(props.genres) if props.genres else [],
            "track_number": getattr(props, "track_number", None),
            "status": str(info.playback_status),
            "playback_rate": rate,
            "position_seconds": pos_sec,
            "duration_seconds": dur_sec,
            "last_updated_utc": last_update.isoformat() if last_update else None,
            "collected_utc": datetime.now(timezone.utc).isoformat(),
            "album_art_url": album_art_url
        }