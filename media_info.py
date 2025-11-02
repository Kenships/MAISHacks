import spotipy
from spotipy.oauth2 import SpotifyOAuth
from typing import Optional
import os
from dotenv import load_dotenv

# Load the .env file
load_dotenv()

class MediaInfo:
    """Fetch current Spotify info using the Spotipy API."""

    def __init__(self):
        CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
        CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
        REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")
        
        self.sp = None
        if CLIENT_ID and CLIENT_SECRET and REDIRECT_URI:
            try:
                # This scope is all we need to read the current song
                scope = "user-read-currently-playing"
                
                # This is the user login flow.
                # It will open a browser the first time.
                self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                    client_id=CLIENT_ID,
                    client_secret=CLIENT_SECRET,
                    redirect_uri=REDIRECT_URI,
                    scope=scope,
                    cache_path=".spotipyoauthcache" # Saves the login
                ))
                # Test the login
                self.sp.me() 
                print("Spotipy (User Login) initialized successfully.")
            except Exception as e:
                print(f"Error initializing Spotipy: {e}")
                print("Make sure you have a .env file with all three keys.")
                print("You may need to run the app once and log in via your browser.")
        else:
            print("Spotify .env keys not found. Media info will not be available.")
            

    def get(self) -> Optional[dict]:
        """Return a dict with all current session info, or None if no session."""
        if not self.sp:
            return None # Spotipy failed to initialize

        try:
            # This is the magic call:
            current_track = self.sp.current_user_playing_track()
            
            if not current_track or not current_track['item']:
                return None # Nothing is playing

            item = current_track['item']
            album_art_url = None
            if item['album']['images']:
                album_art_url = item['album']['images'][0]['url'] # Get highest res
            
            artist = item['artists'][0]['name'] if item['artists'] else "Unknown Artist"

            return {
                "title": item['name'],
                "artist": artist,
                "album": item['album']['name'],
                "album_art_url": album_art_url,
                # We add other fields as None to prevent crashes in the UI
                "app_id": "spotify", 
                "album_artist": None,
                "genres": [],
                "track_number": item.get('track_number'),
                "status": "PlaybackStatus.PLAYING" if current_track.get('is_playing') else "PlaybackStatus.PAUSED",
                "playback_rate": 1.0,
                "position_seconds": current_track.get('progress_ms', 0) / 1000.0,
                "duration_seconds": item.get('duration_ms', 0) / 1000.0,
                "last_updated_utc": None,
                "collected_utc": None,
            }
        except Exception as e:
            print(f"Error in MediaInfo.get(): {e}")
            return None