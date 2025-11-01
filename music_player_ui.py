import pygame
import math

# Initialize Pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 1920, 1080
FPS = 60

# Colors
BG_COLOR = (18, 18, 25)
CARD_BG = (28, 28, 38)
ACCENT = (138, 43, 226)  # Purple
ACCENT_HOVER = (158, 63, 246)
TEXT_PRIMARY = (255, 255, 255)
TEXT_SECONDARY = (150, 150, 160)
SLIDER_BG = (45, 45, 55)

# Create window
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Music Player")
clock = pygame.time.Clock()

# Fonts
title_font = pygame.font.Font(None, 32)
button_font = pygame.font.Font(None, 48)
small_font = pygame.font.Font(None, 24)

class Button:
    def __init__(self, x, y, width, height, text, callback=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.callback = callback
        self.hovered = False
        self.pressed = False
        
    def draw(self, surface):
        color = ACCENT_HOVER if self.hovered else ACCENT
        if self.pressed:
            color = tuple(max(0, c - 30) for c in color)
        
        # Draw rounded rectangle
        pygame.draw.rect(surface, color, self.rect, border_radius=12)
        
        # Draw text
        text_surf = button_font.render(self.text, True, TEXT_PRIMARY)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)
    
    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.pressed = True
        elif event.type == pygame.MOUSEBUTTONUP:
            if self.pressed and self.rect.collidepoint(event.pos):
                if self.callback:
                    self.callback()
            self.pressed = False

class IconButton:
    def __init__(self, x, y, size, icon_type, callback=None):
        self.rect = pygame.Rect(x - size//2, y - size//2, size, size)
        self.icon_type = icon_type
        self.callback = callback
        self.hovered = False
        self.pressed = False
        
    def draw(self, surface):
        color = ACCENT_HOVER if self.hovered else ACCENT
        if self.pressed:
            color = tuple(max(0, c - 30) for c in color)
        
        # Draw circle background
        pygame.draw.circle(surface, color, self.rect.center, self.rect.width // 2)
        
        # Draw icon
        cx, cy = self.rect.center
        if self.icon_type == "play":
            # Triangle pointing right
            points = [
                (cx - 8, cy - 12),
                (cx - 8, cy + 12),
                (cx + 10, cy)
            ]
            pygame.draw.polygon(surface, TEXT_PRIMARY, points)
        elif self.icon_type == "pause":
            # Two vertical bars
            pygame.draw.rect(surface, TEXT_PRIMARY, (cx - 8, cy - 10, 5, 20))
            pygame.draw.rect(surface, TEXT_PRIMARY, (cx + 3, cy - 10, 5, 20))
        elif self.icon_type == "prev":
            # Previous track icon
            points = [
                (cx + 6, cy - 10),
                (cx + 6, cy + 10),
                (cx - 4, cy)
            ]
            pygame.draw.polygon(surface, TEXT_PRIMARY, points)
            pygame.draw.rect(surface, TEXT_PRIMARY, (cx - 8, cy - 10, 3, 20))
        elif self.icon_type == "next":
            # Next track icon
            points = [
                (cx - 6, cy - 10),
                (cx - 6, cy + 10),
                (cx + 4, cy)
            ]
            pygame.draw.polygon(surface, TEXT_PRIMARY, points)
            pygame.draw.rect(surface, TEXT_PRIMARY, (cx + 5, cy - 10, 3, 20))
    
    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.pressed = True
        elif event.type == pygame.MOUSEBUTTONUP:
            if self.pressed and self.rect.collidepoint(event.pos):
                if self.callback:
                    self.callback()
            self.pressed = False

class VolumeSlider:
    def __init__(self, x, y, width, height):
        self.rect = pygame.Rect(x, y, width, height)
        self.value = 0.7  # 0.0 to 1.0
        self.dragging = False
        self.hovered = False
        
    def draw(self, surface):
        # Draw background track
        track_rect = pygame.Rect(self.rect.x, self.rect.centery - 3, self.rect.width, 6)
        pygame.draw.rect(surface, SLIDER_BG, track_rect, border_radius=3)
        
        # Draw filled portion
        filled_width = int(self.rect.width * self.value)
        if filled_width > 0:
            filled_rect = pygame.Rect(self.rect.x, self.rect.centery - 3, filled_width, 6)
            pygame.draw.rect(surface, ACCENT, filled_rect, border_radius=3)
        
        # Draw handle
        handle_x = self.rect.x + int(self.rect.width * self.value)
        handle_color = ACCENT_HOVER if (self.hovered or self.dragging) else ACCENT
        pygame.draw.circle(surface, handle_color, (handle_x, self.rect.centery), 10)
        pygame.draw.circle(surface, TEXT_PRIMARY, (handle_x, self.rect.centery), 6)
        
        # Draw volume percentage
        vol_text = f"{int(self.value * 100)}%"
        text_surf = small_font.render(vol_text, True, TEXT_SECONDARY)
        text_rect = text_surf.get_rect(midtop=(self.rect.centerx, self.rect.bottom + 10))
        surface.blit(text_surf, text_rect)
    
    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            handle_x = self.rect.x + int(self.rect.width * self.value)
            handle_rect = pygame.Rect(handle_x - 10, self.rect.centery - 10, 20, 20)
            self.hovered = handle_rect.collidepoint(event.pos)
            
            if self.dragging:
                rel_x = event.pos[0] - self.rect.x
                self.value = max(0.0, min(1.0, rel_x / self.rect.width))
                
        elif event.type == pygame.MOUSEBUTTONDOWN:
            handle_x = self.rect.x + int(self.rect.width * self.value)
            handle_rect = pygame.Rect(handle_x - 10, self.rect.centery - 10, 20, 20)
            if handle_rect.collidepoint(event.pos) or self.rect.collidepoint(event.pos):
                self.dragging = True
                rel_x = event.pos[0] - self.rect.x
                self.value = max(0.0, min(1.0, rel_x / self.rect.width))
                
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
    
    def get_value(self):
        return self.value

# Player state
is_playing = False
current_song = "No Song Playing"
volume = 70

# Callback functions - Map your actual functions here
def toggle_play_pause():
    global is_playing
    is_playing = not is_playing
    status = "Playing" if is_playing else "Paused"
    print(f"Play/Pause clicked - Status: {status}")
    # YOUR CODE HERE: Add your play/pause logic

def skip_next():
    global current_song
    print("Skip Next clicked")
    # YOUR CODE HERE: Add your skip next logic
    current_song = "Next Song"

def skip_prev():
    global current_song
    print("Skip Previous clicked")
    # YOUR CODE HERE: Add your skip previous logic
    current_song = "Previous Song"

# Create UI elements
play_pause_btn = IconButton(WIDTH // 2, 320, 70, "play" if not is_playing else "pause", toggle_play_pause)
prev_btn = IconButton(WIDTH // 2 - 100, 320, 50, "prev", skip_prev)
next_btn = IconButton(WIDTH // 2 + 100, 320, 50, "next", skip_next)
volume_slider = VolumeSlider(100, 450, 300, 20)

# Main loop
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        
        # Update play/pause button icon
        play_pause_btn.icon_type = "pause" if is_playing else "play"
        
        # Handle events
        play_pause_btn.handle_event(event)
        prev_btn.handle_event(event)
        next_btn.handle_event(event)
        volume_slider.handle_event(event)
    
    # Update volume value
    volume = int(volume_slider.get_value() * 100)
    
    # Clear screen
    screen.fill(BG_COLOR)
    
    # Draw main card
    card_rect = pygame.Rect(40, 60, WIDTH - 80, HEIGHT - 120)
    pygame.draw.rect(screen, CARD_BG, card_rect, border_radius=20)
    
    # Draw album art placeholder
    album_rect = pygame.Rect(WIDTH // 2 - 80, 100, 160, 160)
    pygame.draw.rect(screen, SLIDER_BG, album_rect, border_radius=15)
    music_icon = "♪"
    icon_surf = title_font.render(music_icon, True, TEXT_SECONDARY)
    icon_rect = icon_surf.get_rect(center=album_rect.center)
    screen.blit(icon_surf, icon_rect)
    
    # Draw song title
    title_surf = title_font.render(current_song, True, TEXT_PRIMARY)
    title_rect = title_surf.get_rect(center=(WIDTH // 2, 280))
    screen.blit(title_surf, title_rect)
    
    # Draw controls
    prev_btn.draw(screen)
    play_pause_btn.draw(screen)
    next_btn.draw(screen)
    
    # Draw volume label
    vol_label = small_font.render("Volume", True, TEXT_SECONDARY)
    vol_label_rect = vol_label.get_rect(center=(WIDTH // 2, 410))
    screen.blit(vol_label, vol_label_rect)
    
    # Draw volume slider
    volume_slider.draw(screen)
    
    # Update display
    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()