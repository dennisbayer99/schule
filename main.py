#!/usr/bin/env python3
"""
GALAXY SHOOTER
==============
Arcade-Shooter mit pygame. Alles wird prozedural gezeichnet, es sind keine
externen Dateien nötig. Eigene Sprites/Sounds kannst du optional in den Ordner
assets/ legen (siehe Abschnitt ASSETS weiter unten).

Installation:  pip install pygame
Start:         python main.py
"""
import array
import json
import math
import random
import sys
from pathlib import Path

import pygame
from pygame.math import Vector2

# =============================================================================
# KONSTANTEN (hier drehst du an Schwierigkeit, Tempo und Look)
# =============================================================================

# --- Fenster -----------------------------------------------------------------
WIDTH, HEIGHT = 900, 1000          # Hochformat, jederzeit änderbar
FPS = 60
TITLE = "Galaxy Shooter"

# --- Spieler -----------------------------------------------------------------
PLAYER_LIVES = 3                   # Start-Leben
PLAYER_SIZE = 76                   # Sprite-Größe in Pixel
PLAYER_HIT_RADIUS = 17             # Hitbox (kleiner als das Sprite = fairer)
PLAYER_MAX_SPEED = 640.0           # max. Geschwindigkeit in px/s
PLAYER_RESPONSE = 9.0              # Trägheit: kleiner = träger/schwammiger
MOUSE_FOLLOW = 7.0                 # wie stark das Schiff der Maus hinterherzieht
INVULN_TIME = 2.0                  # Unverwundbarkeit nach Treffer (Sekunden)
GAME_OVER_DELAY = 1.4              # Pause zwischen Tod und Game-Over-Screen

# --- Level-System ------------------------------------------------------------
KILLS_BASE = 10                    # Kills für Level 1 -> 2
KILLS_STEP = 5                     # jedes weitere Level braucht so viele mehr
LEVELUP_BANNER_TIME = 2.4          # Dauer des "LEVEL UP!"-Banners


def kills_needed(level):
    """Benötigte Kills für den Aufstieg: 10 + (Level - 1) * 5."""
    return KILLS_BASE + (level - 1) * KILLS_STEP


# --- Waffen ------------------------------------------------------------------
BULLET_SPEED = 950.0               # Geschossgeschwindigkeit px/s
FIRE_RATE_MIN_COOLDOWN = 0.10      # schneller als das wird nie geschossen

# --- Gegner-Spawning ---------------------------------------------------------
WAVE_START_DELAY = 1.0             # Sekunden bis zur ersten Welle
WAVE_INTERVAL_BASE = 2.2           # Sekunden zwischen Wellen auf Level 1
WAVE_INTERVAL_DECAY = 0.08         # pro Level kürzer
WAVE_INTERVAL_MIN = 0.8            # kürzer wird es nie
MAX_ENEMIES = 40                   # Obergrenze gleichzeitiger Gegner
ENEMY_SPEED_PER_LEVEL = 0.04       # +4 % Tempo pro Level
ENEMY_SPEED_CAP = 1.8              # max. Tempo-Faktor
ENEMY_HP_EVERY_N_LEVELS = 4        # alle N Level +1 Lebenspunkt für Gegner

# Gegnertypen: hp = Lebenspunkte, speed = px/s, size = Pixel, points = Score,
# unlock = ab diesem Level tauchen sie auf, weight = Spawn-Häufigkeit
ENEMY_TYPES = {
    "grunt":    dict(hp=2, speed=130, size=58, points=10, unlock=1, weight=10),
    "asteroid": dict(hp=3, speed=150, size=(48, 96), points=15, unlock=1, weight=6),
    "scout":    dict(hp=1, speed=300, size=42, points=15, unlock=2, weight=5),
    "zigzag":   dict(hp=2, speed=160, size=54, points=20, unlock=3, weight=5),
    "tank":     dict(hp=8, speed=70, size=92, points=40, unlock=4, weight=3),
}

# --- Effekte -----------------------------------------------------------------
SHAKE_DECAY = 70.0                 # wie schnell das Wackeln abklingt
SHAKE_MAX = 28.0
MAX_PARTICLES = 700

# --- Farben (Neon-Palette) ---------------------------------------------------
BG_TOP = (4, 6, 20)
BG_BOTTOM = (18, 8, 42)
CYAN = (60, 225, 255)
MAGENTA = (255, 70, 210)
YELLOW = (255, 220, 80)
ORANGE = (255, 140, 40)
GREEN = (80, 255, 150)
RED = (255, 70, 80)
WHITE = (255, 255, 255)
GRAY = (150, 160, 190)
PANEL = (14, 18, 40)

# --- ASSETS ------------------------------------------------------------------
# Lege PNG-Dateien mit diesen Namen in assets/ und sie ersetzen die gezeichneten
# Grafiken automatisch: player.png, grunt.png, scout.png, zigzag.png, tank.png,
# asteroid.png. Sounds (optional) in assets/sounds/: shoot.wav, explode.wav,
# hit.wav, levelup.wav, click.wav. Fehlt eine Datei, wird die Standardgrafik bzw.
# der erzeugte Ton genutzt.
BASE_DIR = Path(__file__).resolve().parent
ASSET_DIR = BASE_DIR / "assets"
HIGHSCORE_FILE = BASE_DIR / "highscore.json"

# Waffen-Namen pro Level (nur für die Anzeige)
WEAPON_NAMES = {
    1: "Pulsschuss",
    2: "Schwerer Schuss",
    3: "Doppelschuss",
    4: "Dreifach-Fächer",
    5: "Durchschlag-Strahl",
}


def weapon_name(level):
    return WEAPON_NAMES.get(level, f"Mega-Salve (Stufe {level - 5})")


# =============================================================================
# HILFSFUNKTIONEN: Glow, Sprites, Highscore
# =============================================================================
_glow_cache = {}
_asset_cache = {}


def glow_surf(radius, color):
    """Weicher, runder Leuchtfleck (wird gecacht, additiv zu blitten)."""
    r = max(2, int(radius) // 2 * 2)
    col = tuple(min(255, (int(c) + 8) // 16 * 16) for c in color)
    key = (r, col)
    surf = _glow_cache.get(key)
    if surf is None:
        surf = pygame.Surface((r * 2, r * 2))
        surf.fill((0, 0, 0))
        step = 1 if r <= 64 else 2
        for i in range(r, 0, -step):
            f = (1 - i / r) ** 1.8
            c = (int(col[0] * f), int(col[1] * f), int(col[2] * f))
            pygame.draw.circle(surf, c, (r, r), i)
        _glow_cache[key] = surf
    return surf


def draw_glow(surf, pos, radius, color):
    """Zeichnet einen additiven Glow (heller werdend, typischer Neon-Look)."""
    if radius < 2:
        return
    g = glow_surf(radius, color)
    r = g.get_width() // 2
    surf.blit(g, (int(pos[0]) - r, int(pos[1]) - r), special_flags=pygame.BLEND_ADD)


def render_sprite(size, draw_fn, supersample=3):
    """Zeichnet ein Sprite in 3-facher Auflösung und skaliert glatt herunter."""
    w, h = size
    big = pygame.Surface((w * supersample, h * supersample), pygame.SRCALPHA)
    draw_fn(big, w * supersample, h * supersample)
    return pygame.transform.smoothscale(big, (w, h))


def try_asset(name, size):
    """Lädt assets/<name>.png falls vorhanden, sonst None."""
    key = (name, tuple(size))
    if key in _asset_cache:
        return _asset_cache[key]
    img = None
    path = ASSET_DIR / f"{name}.png"
    if path.exists():
        try:
            img = pygame.transform.smoothscale(
                pygame.image.load(str(path)).convert_alpha(), size)
        except (pygame.error, OSError):
            img = None
    _asset_cache[key] = img
    return img


def load_sprite(name, size, draw_fn):
    """Eigenes Sprite aus assets/ oder Fallback auf die gezeichnete Grafik."""
    return try_asset(name, size) or render_sprite(size, draw_fn)


def load_highscore():
    try:
        with open(HIGHSCORE_FILE, "r", encoding="utf-8") as f:
            return int(json.load(f).get("highscore", 0))
    except (OSError, ValueError, TypeError, AttributeError):
        return 0


def save_highscore(value):
    try:
        with open(HIGHSCORE_FILE, "w", encoding="utf-8") as f:
            json.dump({"highscore": int(value)}, f)
    except OSError:
        pass


def rr(W, H, x, y, w, h):
    """Rechteck aus relativen Koordinaten (0..1) für die Sprite-Zeichner."""
    return pygame.Rect(int(x * W), int(y * H), max(1, int(w * W)), max(1, int(h * H)))


# =============================================================================
# SPRITE-ZEICHNER (prozedural, Koordinaten relativ 0..1)
# =============================================================================
def draw_player(s, W, H):
    P = lambda pts: [(x * W, y * H) for x, y in pts]
    mirror = lambda pts: [(1 - x, y) for x, y in pts]
    lw = max(2, int(W * 0.025))
    wing = [(0.40, 0.42), (0.02, 0.80), (0.05, 0.97), (0.24, 0.90), (0.40, 0.80)]
    for w in (wing, mirror(wing)):
        pygame.draw.polygon(s, (40, 110, 255), P(w))
        pygame.draw.polygon(s, (150, 225, 255), P(w), lw)
    # Wing-Spitzen in Magenta
    for tip in ([(0.02, 0.80), (0.05, 0.97), (0.12, 0.93), (0.10, 0.84)],):
        pygame.draw.polygon(s, MAGENTA, P(tip))
        pygame.draw.polygon(s, MAGENTA, P(mirror(tip)))
    body = [(0.5, 0.02), (0.60, 0.30), (0.65, 0.62), (0.58, 0.88),
            (0.5, 0.80), (0.42, 0.88), (0.35, 0.62), (0.40, 0.30)]
    pygame.draw.polygon(s, (205, 225, 250), P(body))
    pygame.draw.polygon(s, (120, 200, 255), P(body), lw)
    pygame.draw.polygon(s, (60, 130, 230), P([(0.5, 0.10), (0.56, 0.32), (0.5, 0.30), (0.44, 0.32)]))
    pygame.draw.ellipse(s, (20, 40, 90), rr(W, H, 0.43, 0.30, 0.14, 0.26))
    pygame.draw.ellipse(s, CYAN, rr(W, H, 0.455, 0.325, 0.09, 0.19))
    pygame.draw.ellipse(s, WHITE, rr(W, H, 0.47, 0.34, 0.03, 0.07))
    pygame.draw.circle(s, YELLOW, (int(0.5 * W), int(0.74 * H)), int(W * 0.035))


def draw_grunt(s, W, H):
    lw = max(2, int(W * 0.03))
    for sx in (0.28, 0.5, 0.72):
        pygame.draw.line(s, (40, 170, 110), (sx * W, 0.72 * H),
                         ((sx + (sx - 0.5) * 0.5) * W, 0.97 * H), lw + 1)
    pygame.draw.ellipse(s, (70, 235, 150), rr(W, H, 0.24, 0.04, 0.52, 0.56))
    pygame.draw.ellipse(s, (170, 255, 215), rr(W, H, 0.24, 0.04, 0.52, 0.56), lw)
    pygame.draw.ellipse(s, (30, 110, 90), rr(W, H, 0.04, 0.42, 0.92, 0.36))
    pygame.draw.ellipse(s, (120, 255, 200), rr(W, H, 0.04, 0.42, 0.92, 0.36), lw)
    for ex in (0.40, 0.60):
        pygame.draw.circle(s, WHITE, (int(ex * W), int(0.28 * H)), int(W * 0.075))
        pygame.draw.circle(s, (20, 20, 40), (int(ex * W), int(0.30 * H)), int(W * 0.04))
    for lx in (0.2, 0.38, 0.62, 0.8):
        pygame.draw.circle(s, YELLOW, (int(lx * W), int(0.60 * H)), int(W * 0.035))


def draw_scout(s, W, H):
    lw = max(2, int(W * 0.03))
    P = lambda pts: [(x * W, y * H) for x, y in pts]
    body = [(0.5, 1.0), (0.96, 0.14), (0.64, 0.30), (0.5, 0.06), (0.36, 0.30), (0.04, 0.14)]
    pygame.draw.polygon(s, (255, 60, 170), P(body))
    pygame.draw.polygon(s, (255, 180, 225), P(body), lw)
    pygame.draw.polygon(s, (150, 20, 110), P([(0.5, 0.9), (0.66, 0.4), (0.5, 0.3), (0.34, 0.4)]))
    pygame.draw.circle(s, YELLOW, (int(0.5 * W), int(0.46 * H)), int(W * 0.09))
    pygame.draw.circle(s, WHITE, (int(0.5 * W), int(0.46 * H)), int(W * 0.04))


def draw_zigzag(s, W, H):
    lw = max(2, int(W * 0.03))
    P = lambda pts: [(x * W, y * H) for x, y in pts]
    mirror = lambda pts: [(1 - x, y) for x, y in pts]
    wing = [(0.5, 0.35), (0.0, 0.08), (0.08, 0.55), (0.28, 0.48), (0.38, 0.78), (0.5, 0.62)]
    for w in (wing, mirror(wing)):
        pygame.draw.polygon(s, (230, 110, 30), P(w))
        pygame.draw.polygon(s, (255, 200, 90), P(w), lw)
    pygame.draw.ellipse(s, (255, 175, 45), rr(W, H, 0.35, 0.18, 0.30, 0.66))
    pygame.draw.ellipse(s, (255, 235, 140), rr(W, H, 0.35, 0.18, 0.30, 0.66), lw)
    for ex in (0.43, 0.57):
        pygame.draw.circle(s, RED, (int(ex * W), int(0.40 * H)), int(W * 0.05))
        pygame.draw.circle(s, WHITE, (int(ex * W), int(0.39 * H)), int(W * 0.018))


def draw_tank(s, W, H):
    lw = max(2, int(W * 0.03))
    P = lambda pts: [(x * W, y * H) for x, y in pts]
    for sx in (0.14, 0.30, 0.50, 0.70, 0.86):
        pygame.draw.polygon(s, (190, 120, 255), P([(sx - 0.07, 0.92), (sx, 1.0), (sx + 0.07, 0.92)]))
    body = [(0.25, 0.04), (0.75, 0.04), (0.98, 0.45), (0.82, 0.94), (0.18, 0.94), (0.02, 0.45)]
    pygame.draw.polygon(s, (110, 50, 175), P(body))
    pygame.draw.polygon(s, (215, 160, 255), P(body), lw)
    plate = [(0.30, 0.16), (0.70, 0.16), (0.86, 0.46), (0.74, 0.82), (0.26, 0.82), (0.14, 0.46)]
    pygame.draw.polygon(s, (150, 85, 225), P(plate))
    pygame.draw.polygon(s, (90, 40, 150), P(plate), lw)
    for ex, ey in ((0.30, 0.46), (0.5, 0.40), (0.70, 0.46)):
        pygame.draw.circle(s, (255, 60, 60), (int(ex * W), int(ey * H)), int(W * 0.09))
        pygame.draw.circle(s, YELLOW, (int(ex * W), int(ey * H)), int(W * 0.045))
    pygame.draw.line(s, (60, 20, 100), (0.32 * W, 0.68 * H), (0.68 * W, 0.68 * H), lw + 1)


def make_asteroid_drawer(seed):
    """Jeder Asteroid bekommt eine eigene, zufällige Felsform."""
    def draw(s, W, H):
        rng = random.Random(seed)
        n = 12
        pts = []
        for i in range(n):
            a = i / n * math.tau
            r = rng.uniform(0.36, 0.5)
            pts.append((W * (0.5 + math.cos(a) * r), H * (0.5 + math.sin(a) * r)))
        lw = max(2, int(W * 0.03))
        pygame.draw.polygon(s, (112, 96, 86), pts)
        pygame.draw.polygon(s, (205, 180, 155), pts, lw)
        for _ in range(4):
            cx, cy = rng.uniform(0.3, 0.7), rng.uniform(0.3, 0.7)
            cr = rng.uniform(0.06, 0.12)
            pygame.draw.circle(s, (78, 66, 60), (int(cx * W), int(cy * H)), int(cr * W))
            pygame.draw.circle(s, (160, 140, 120), (int(cx * W), int(cy * H)), int(cr * W), max(1, lw // 2))
    return draw


ENEMY_DRAWERS = {"grunt": draw_grunt, "scout": draw_scout,
                 "zigzag": draw_zigzag, "tank": draw_tank}
ENEMY_GLOW = {"grunt": GREEN, "scout": MAGENTA, "zigzag": ORANGE,
              "tank": (170, 90, 255), "asteroid": (110, 90, 70)}
_enemy_sprites = {}


def enemy_sprite(kind, size):
    key = (kind, size)
    if key not in _enemy_sprites:
        _enemy_sprites[key] = load_sprite(kind, (size, size), ENEMY_DRAWERS[kind])
    return _enemy_sprites[key]


# =============================================================================
# SOUND (alles erzeugt, optional durch assets/sounds/*.wav ersetzbar)
# =============================================================================
class SoundBank:
    def __init__(self):
        self.ok = False
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(22050, -16, 1, 512)
            self.rate, _, self.channels = pygame.mixer.get_init()
            self.ok = True
        except pygame.error:
            return
        self._build()

    def _synth(self, f0, f1, dur, vol=0.4, noise=0.0, square=False):
        n = int(self.rate * dur)
        out = []
        phase = 0.0
        for i in range(n):
            t = i / n
            phase += math.tau * (f0 + (f1 - f0) * t) / self.rate
            v = math.sin(phase)
            if square:
                v = 1.0 if v > 0 else -1.0
            v = v * (1 - noise) + random.uniform(-1, 1) * noise
            env = min(1.0, i / 80) * (1 - t) ** 2
            out.append(int(v * env * vol * 32767))
        return out

    def _make(self, samples):
        buf = array.array("h")
        for v in samples:
            buf.extend([v] * self.channels)   # Mono auf alle Kanäle kopieren
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def _build(self):
        gen = {
            "shoot": lambda: self._synth(900, 350, 0.07, 0.07, square=True),
            "explode": lambda: self._synth(220, 40, 0.35, 0.30, noise=0.6),
            "hit": lambda: self._synth(300, 50, 0.55, 0.40, noise=0.5),
            "click": lambda: self._synth(650, 650, 0.04, 0.15),
            "levelup": lambda: sum((self._synth(f, f, 0.11, 0.25, square=True)
                                    for f in (440, 554, 659, 880)), []),
        }
        for name, fn in gen.items():
            path = ASSET_DIR / "sounds" / f"{name}.wav"
            try:
                if path.exists():
                    self.sounds[name] = pygame.mixer.Sound(str(path))
                    continue
            except pygame.error:
                pass
            self.sounds[name] = self._make(fn())

    def play(self, name):
        if self.ok and name in self.sounds:
            self.sounds[name].play()


# =============================================================================
# HINTERGRUND: Parallax-Sterne + Nebel
# =============================================================================
class Starfield:
    # (Anzahl, Tempo px/s, Größe, Helligkeit) pro Ebene: hinten -> vorne
    LAYERS = [(70, 25, 1, 95), (45, 70, 2, 160), (26, 160, 3, 245)]

    def __init__(self):
        self.layers = []
        for count, speed, size, bright in self.LAYERS:
            stars = [[random.uniform(0, WIDTH), random.uniform(0, HEIGHT),
                      random.uniform(0.6, 1.0)] for _ in range(count)]
            self.layers.append((stars, speed, size, bright))
        # Farbverlauf einmalig vorrendern
        self.bg = pygame.Surface((WIDTH, HEIGHT))
        for y in range(HEIGHT):
            t = y / HEIGHT
            c = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
            pygame.draw.line(self.bg, c, (0, y), (WIDTH, y))
        # Nebelflecken, die langsam driften
        self.nebulas = [[WIDTH * 0.25, HEIGHT * 0.2, 340, (46, 12, 80), 14],
                        [WIDTH * 0.80, HEIGHT * 0.6, 300, (10, 30, 80), 18],
                        [WIDTH * 0.45, HEIGHT * 1.0, 360, (70, 14, 60), 10]]

    def update(self, dt):
        for stars, speed, _, _ in self.layers:
            for st in stars:
                st[1] += speed * dt
                if st[1] > HEIGHT:
                    st[0], st[1] = random.uniform(0, WIDTH), -4
        for n in self.nebulas:
            n[1] += n[4] * dt
            if n[1] - n[2] > HEIGHT:
                n[1] = -n[2]
                n[0] = random.uniform(0, WIDTH)

    def draw(self, surf):
        surf.blit(self.bg, (0, 0))
        for x, y, r, col, _ in self.nebulas:
            draw_glow(surf, (x, y), r, col)
        for stars, _, size, bright in self.layers:
            for x, y, tw in stars:
                b = int(bright * tw)
                col = (b, b, min(255, b + 20))
                if size == 1:
                    surf.set_at((int(x), int(y)), col)
                else:
                    pygame.draw.circle(surf, col, (int(x), int(y)), size // 2 + 1)
                    if size == 3:
                        draw_glow(surf, (x, y), 7, (60, 70, 110))


# =============================================================================
# PARTIKEL
# =============================================================================
class Particle:
    def __init__(self, pos, vel, life, color, size, drag=2.0, ring=False, grow=0.0):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.life = self.max_life = life
        self.color = color
        self.size = size
        self.drag = drag
        self.ring = ring
        self.grow = grow

    def update(self, dt):
        self.life -= dt
        self.pos += self.vel * dt
        self.vel *= max(0.0, 1 - self.drag * dt)

    def draw(self, surf):
        t = max(0.0, self.life / self.max_life)
        if self.ring:
            r = int(self.size + self.grow * (1 - t))
            col = tuple(int(c * t) for c in self.color)
            pygame.draw.circle(surf, col, (int(self.pos.x), int(self.pos.y)), r, max(1, int(5 * t)))
            return
        r = self.size * (0.4 + 0.6 * t)
        col = tuple(int(c * t) for c in self.color)
        draw_glow(surf, self.pos, r * 3, col)
        core = tuple(int((c + 255) / 2 * t) for c in self.color)
        pygame.draw.circle(surf, core, (int(self.pos.x), int(self.pos.y)), max(1, int(r * 0.6)))


# =============================================================================
# BULLET
# =============================================================================
class Bullet:
    def __init__(self, pos, angle_deg, radius, damage, pierce, glow):
        a = math.radians(angle_deg)
        self.pos = Vector2(pos)
        self.vel = Vector2(math.sin(a), -math.cos(a)) * BULLET_SPEED
        self.radius = radius
        self.damage = damage
        self.pierce = pierce              # durchschlagend: trifft mehrere Gegner
        self.glow = glow
        self.color = MAGENTA if pierce else CYAN
        self.hit = set()                  # schon getroffene Gegner (nur 1x Schaden)
        self.alive = True

    def update(self, dt):
        self.pos += self.vel * dt
        if (self.pos.y < -40 or self.pos.x < -40 or self.pos.x > WIDTH + 40):
            self.alive = False

    def draw(self, surf):
        r = self.radius
        x, y = int(self.pos.x), int(self.pos.y)
        draw_glow(surf, (x, y), r * 3.4 * self.glow, self.color)
        pygame.draw.ellipse(surf, self.color, (x - r, y - int(r * 1.8), r * 2, int(r * 3.6)))
        pygame.draw.ellipse(surf, WHITE, (x - r // 2, y - r, max(2, r), int(r * 2)))


def weapon_for_level(level):
    """Gibt (Schussliste, Cooldown, Glow) zurück.
    Schuss = (x-Versatz, Winkel in Grad, Radius, Schaden, durchschlagend)."""
    if level == 1:
        return [(0, 0, 4, 1, False)], 0.28, 1.0
    if level == 2:
        return [(0, 0, 7, 2, False)], 0.28, 1.1
    if level == 3:
        return [(-14, 0, 7, 2, False), (14, 0, 7, 2, False)], 0.27, 1.1
    if level == 4:
        return [(0, 0, 7, 2, False), (-10, -12, 6, 2, False), (10, 12, 6, 2, False)], 0.26, 1.2
    if level == 5:
        return [(0, 0, 15, 4, True), (-18, -9, 5, 1, False), (18, 9, 5, 1, False)], 0.30, 1.3
    extra = level - 5                                  # Lv6+: mehr, schneller, heller
    shots = [(0, 0, 15 + min(extra, 5), 4 + extra // 2, True)]
    for i in range(1, min(1 + extra, 4) + 1):
        dmg = 2 + (1 if level >= 8 else 0)
        shots.append((-i * 10, -i * 9, 6, dmg, False))
        shots.append((i * 10, i * 9, 6, dmg, False))
    cooldown = max(FIRE_RATE_MIN_COOLDOWN, 0.30 - 0.02 * extra)
    return shots, cooldown, min(2.2, 1.3 + 0.12 * extra)


# =============================================================================
# PLAYER
# =============================================================================
class Player:
    def __init__(self):
        self.sprite = load_sprite("player", (PLAYER_SIZE, PLAYER_SIZE), draw_player)
        self.icon = pygame.transform.smoothscale(self.sprite, (28, 28))
        self.reset()

    def reset(self):
        self.pos = Vector2(WIDTH / 2, HEIGHT - 140)
        self.vel = Vector2()
        self.cooldown = 0.3
        self.invuln = 0.0
        self.lives = PLAYER_LIVES
        self.alive = True
        self.control = "keys"              # "keys" oder "mouse"
        self.t = 0.0

    def update(self, dt, keys, mouse_pos, mouse_ok):
        self.t += dt
        d = Vector2(
            (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT]),
            (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP]))
        if d.length_squared() > 0:
            self.control = "keys"
            desired = d.normalize() * PLAYER_MAX_SPEED
        elif self.control == "mouse" and mouse_ok:
            desired = (Vector2(mouse_pos) - self.pos) * MOUSE_FOLLOW
            if desired.length() > PLAYER_MAX_SPEED:
                desired.scale_to_length(PLAYER_MAX_SPEED)
        else:
            desired = Vector2()
        # weiche Beschleunigung = leichte Trägheit (framerate-unabhängig)
        self.vel += (desired - self.vel) * (1 - math.exp(-PLAYER_RESPONSE * dt))
        self.pos += self.vel * dt
        m = PLAYER_SIZE * 0.45
        if self.pos.x < m or self.pos.x > WIDTH - m:
            self.pos.x = max(m, min(WIDTH - m, self.pos.x))
            self.vel.x = 0
        if self.pos.y < 90 or self.pos.y > HEIGHT - m:
            self.pos.y = max(90, min(HEIGHT - m, self.pos.y))
            self.vel.y = 0
        if self.invuln > 0:
            self.invuln -= dt

    def fire(self, level):
        shots, cooldown, glow = weapon_for_level(level)
        bullets = [Bullet((self.pos.x + dx, self.pos.y - PLAYER_SIZE * 0.45),
                          ang, r, dmg, pierce, glow)
                   for dx, ang, r, dmg, pierce in shots]
        return bullets, cooldown

    def draw(self, surf):
        if self.invuln > 0 and int(self.invuln * 12) % 2 == 0:
            return                                    # Blinken nach Treffer
        x, y = self.pos.x, self.pos.y
        # Triebwerksflamme (flackert)
        flick = 0.8 + 0.3 * math.sin(self.t * 45) + random.uniform(0, 0.25)
        base = y + PLAYER_SIZE * 0.34
        draw_glow(surf, (x, base + 8), 30 * flick, ORANGE)
        pygame.draw.polygon(surf, ORANGE, [(x - 9, base), (x + 9, base), (x, base + 30 * flick)])
        pygame.draw.polygon(surf, (255, 240, 180), [(x - 4, base), (x + 4, base), (x, base + 17 * flick)])
        draw_glow(surf, (x, y), 50, (20, 60, 120))
        surf.blit(self.sprite, self.sprite.get_rect(center=(int(x), int(y))))


# =============================================================================
# ENEMY
# =============================================================================
class Enemy:
    def __init__(self, kind, x, y, level, size=None, target_x=None):
        spec = ENEMY_TYPES[kind]
        self.kind = kind
        if kind == "asteroid":
            self.size = size or random.randint(*spec["size"])
            self.sprite = try_asset("asteroid", (self.size, self.size)) or render_sprite(
                (self.size, self.size), make_asteroid_drawer(random.random()))
            self.hp = spec["hp"] + self.size // 40
        else:
            self.size = spec["size"]
            self.sprite = enemy_sprite(kind, self.size)
            self.hp = spec["hp"]
        self.hp += (level - 1) // ENEMY_HP_EVERY_N_LEVELS
        self.max_hp = self.hp
        mult = min(ENEMY_SPEED_CAP, 1 + ENEMY_SPEED_PER_LEVEL * (level - 1))
        self.speed = spec["speed"] * random.uniform(0.9, 1.1) * mult
        self.points = spec["points"]
        self.radius = self.size * 0.42
        self.pos = Vector2(x, y)
        self.base_x = x
        self.vel = Vector2(0, self.speed)
        self.age = random.uniform(0, 6)
        self.phase = random.uniform(0, math.tau)
        self.angle = 0.0
        self.spin = random.uniform(-90, 90)
        self.hit_flash = 0.0
        self.dead = False
        if kind == "asteroid":
            self.vel.x = random.uniform(-60, 60)
        elif kind == "scout" and target_x is not None:
            # Scouts steuern grob auf die Spielerposition zu
            self.vel.x = max(-140, min(140, (target_x - x) / (HEIGHT / self.speed)))

    def update(self, dt):
        self.age += dt
        m = self.size / 2
        if self.kind == "zigzag":
            self.pos.y += self.speed * dt
            self.pos.x = max(m, min(WIDTH - m, self.base_x + math.sin(self.age * 2.6 + self.phase) * 130))
        elif self.kind == "grunt":
            self.pos.y += self.speed * dt
            self.pos.x = self.base_x + math.sin(self.age * 1.5 + self.phase) * 28
        else:
            self.pos += self.vel * dt
            if self.kind == "asteroid":
                self.angle += self.spin * dt
                if (self.pos.x < m and self.vel.x < 0) or (self.pos.x > WIDTH - m and self.vel.x > 0):
                    self.vel.x *= -1
        if self.hit_flash > 0:
            self.hit_flash -= dt
        return self.pos.y < HEIGHT + self.size

    def draw(self, surf):
        draw_glow(surf, self.pos, self.size * 0.85, ENEMY_GLOW[self.kind])
        img = self.sprite
        if self.kind == "asteroid":
            img = pygame.transform.rotozoom(img, self.angle, 1.0)
        if self.hit_flash > 0:
            img = img.copy()
            img.fill((120, 120, 120, 0), special_flags=pygame.BLEND_RGB_ADD)
        surf.blit(img, img.get_rect(center=(int(self.pos.x), int(self.pos.y))))
        if self.max_hp >= 4 and self.hp < self.max_hp:        # Lebensbalken
            w = self.size * 0.8
            x, y = self.pos.x - w / 2, self.pos.y - self.size * 0.62
            pygame.draw.rect(surf, (40, 20, 40), (x, y, w, 5))
            pygame.draw.rect(surf, RED, (x, y, w * max(0, self.hp) / self.max_hp, 5))


# =============================================================================
# UI
# =============================================================================
class Button:
    def __init__(self, rect, label, action, color=CYAN):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.action = action
        self.color = color


def make_font(size, bold=True):
    return pygame.font.SysFont("bahnschrift,segoeui,arial,dejavusans", size, bold=bold)


class UI:
    def __init__(self):
        self.f_huge = make_font(128)
        self.f_big = make_font(96)
        self.f_title = make_font(64)
        self.f_med = make_font(40)
        self.f_hud = make_font(30)
        self.f_small = make_font(20)
        self.f_tiny = make_font(17)
        self._cache = {}
        self.pause_rect = pygame.Rect(WIDTH - 62, 16, 46, 46)
        cx = WIDTH // 2
        self.menu_buttons = [Button((cx - 170, 640, 340, 80), "START", "start")]
        self.over_buttons = [Button((cx - 190, 740, 380, 80), "NEUSTART", "start")]
        self.pause_buttons = [
            Button((cx - 190, 400, 380, 80), "WEITER", "resume", GREEN),
            Button((cx - 190, 500, 380, 80), "NEUSTART", "restart", YELLOW),
            Button((cx - 190, 600, 380, 80), "BEENDEN", "quit", RED)]

    # --- Text mit optionalem Glow ---------------------------------------------
    def text(self, surf, txt, font, color, pos, anchor="topleft", glow=False):
        key = (txt, id(font), color, glow)
        entry = self._cache.get(key)
        if entry is None:
            if len(self._cache) > 400:
                self._cache.clear()
            img = font.render(txt, True, color)
            halo = None
            if glow:
                pad = 16
                w, h = img.get_size()
                base = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
                base.blit(img, (pad, pad))
                small = pygame.transform.smoothscale(base, (max(1, base.get_width() // 4),
                                                            max(1, base.get_height() // 4)))
                blurred = pygame.transform.smoothscale(small, base.get_size())
                # Alpha vorab auf Schwarz verrechnen, sonst addiert BLEND_RGB_ADD
                # auch die (unsichtbaren) Pixel und es entsteht ein Rechteck.
                halo = pygame.Surface(base.get_size())
                halo.fill((0, 0, 0))
                halo.blit(blurred, (0, 0))
            entry = (img, halo)
            self._cache[key] = entry
        img, halo = entry
        rect = img.get_rect(**{anchor: pos})
        if halo is not None:
            hp = halo.get_rect(center=rect.center)
            surf.blit(halo, hp, special_flags=pygame.BLEND_RGB_ADD)
            surf.blit(halo, hp, special_flags=pygame.BLEND_RGB_ADD)
        surf.blit(img, rect)
        return rect

    def hit(self, buttons, pos):
        for b in buttons:
            if b.rect.collidepoint(pos):
                return b.action
        return None

    def draw_button(self, surf, b, mouse_pos):
        hover = b.rect.collidepoint(mouse_pos)
        fill = tuple(min(255, int(c * (0.30 if hover else 0.16)) + 10) for c in b.color)
        pygame.draw.rect(surf, fill, b.rect, border_radius=16)
        if hover:
            draw_glow(surf, b.rect.center, b.rect.width * 0.6, tuple(int(c * 0.35) for c in b.color))
        pygame.draw.rect(surf, b.color, b.rect, 3, border_radius=16)
        self.text(surf, b.label, self.f_med, WHITE, b.rect.center, "center", glow=hover)

    # --- HUD ---------------------------------------------------------------------
    def draw_hud(self, surf, game, mouse_pos):
        x = 24
        self.text(surf, "SCORE", self.f_tiny, GRAY, (x, 14))
        self.text(surf, f"{game.score:,}".replace(",", "."), self.f_title, WHITE, (x, 28), glow=True)
        self.text(surf, f"LEVEL {game.level}", self.f_hud, CYAN, (x, 94), glow=True)
        # Fortschrittsbalken bis zum nächsten Level
        bar = pygame.Rect(x, 134, 290, 16)
        pygame.draw.rect(surf, (20, 24, 52), bar, border_radius=8)
        fill_w = int(bar.width * max(0.0, min(1.0, game.bar_display)))
        if fill_w > 2:
            fill = pygame.Rect(bar.x, bar.y, fill_w, bar.height)
            pygame.draw.rect(surf, CYAN, fill, border_radius=8)
            pygame.draw.rect(surf, MAGENTA, (fill.right - min(fill_w, 40), fill.y, min(fill_w, 40), fill.height),
                             border_radius=8)
            draw_glow(surf, (fill.right, bar.centery), 26, (30, 70, 90))
        pygame.draw.rect(surf, (90, 110, 170), bar, 2, border_radius=8)
        need = kills_needed(game.level)
        self.text(surf, f"{game.kills_in_level}/{need}", self.f_tiny, WHITE, (bar.right + 10, bar.centery), "midleft")
        # Leben
        for i in range(game.player.lives):
            surf.blit(game.player.icon, (x + i * 34, 162))
        self.text(surf, weapon_name(game.level), self.f_tiny, GRAY, (x, 198))
        # Pause-Button oben rechts
        hover = self.pause_rect.collidepoint(mouse_pos)
        pygame.draw.rect(surf, (40, 60, 110) if hover else (18, 24, 52), self.pause_rect, border_radius=10)
        pygame.draw.rect(surf, CYAN, self.pause_rect, 2, border_radius=10)
        r = self.pause_rect
        pygame.draw.rect(surf, WHITE, (r.x + 14, r.y + 12, 6, 22), border_radius=2)
        pygame.draw.rect(surf, WHITE, (r.x + 26, r.y + 12, 6, 22), border_radius=2)

    def draw_banner(self, surf, game):
        if game.banner_timer <= 0:
            return
        t = LEVELUP_BANNER_TIME - game.banner_timer
        if t < 0.3:
            p = t / 0.3
            scale = 0.3 + 0.8 * (1 - (1 - p) ** 3)
        else:
            scale = 1.1 - 0.1 * min(1.0, (t - 0.3) / 0.3)
        alpha = 255 if game.banner_timer > 0.6 else int(255 * game.banner_timer / 0.6)
        cx, cy = WIDTH // 2, 330
        draw_glow(surf, (cx, cy), 260 * scale, tuple(int(c * alpha / 255 * 0.45) for c in MAGENTA))
        img = self.f_big.render("LEVEL UP!", True, YELLOW)
        img = pygame.transform.rotozoom(img, 0, scale)
        img.set_alpha(alpha)
        surf.blit(img, img.get_rect(center=(cx, cy)))
        sub = self.f_hud.render(f"Level {game.level}  -  {weapon_name(game.level)}", True, WHITE)
        sub.set_alpha(alpha)
        surf.blit(sub, sub.get_rect(center=(cx, cy + 70)))

    # --- Bildschirme ---------------------------------------------------------------
    def draw_menu(self, surf, game, mouse_pos):
        self.text(surf, "GALAXY", self.f_huge, CYAN, (WIDTH // 2, 190), "center", glow=True)
        self.text(surf, "SHOOTER", self.f_big, MAGENTA, (WIDTH // 2, 300), "center", glow=True)
        bob = math.sin(game.time * 2) * 10
        ship = game.menu_ship
        surf.blit(ship, ship.get_rect(center=(WIDTH // 2, int(470 + bob))))
        for b in self.menu_buttons:
            self.draw_button(surf, b, mouse_pos)
        if int(game.time * 2) % 2 == 0:
            self.text(surf, "oder LEERTASTE", self.f_small, GRAY, (WIDTH // 2, 742), "center")
        self.text(surf, f"HIGHSCORE  {game.highscore:,}".replace(",", "."), self.f_hud, YELLOW, (WIDTH // 2, 810), "center", glow=True)
        self.text(surf, "Maus oder WASD / Pfeiltasten  |  Auto-Fire  |  P / ESC = Pause",
                  self.f_small, GRAY, (WIDTH // 2, HEIGHT - 50), "center")

    def draw_pause(self, surf, mouse_pos):
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 12, 175))
        surf.blit(dim, (0, 0))
        self.text(surf, "PAUSE", self.f_big, CYAN, (WIDTH // 2, 290), "center", glow=True)
        for b in self.pause_buttons:
            self.draw_button(surf, b, mouse_pos)
        self.text(surf, "P / ESC = weiter", self.f_small, GRAY, (WIDTH // 2, 730), "center")

    def draw_game_over(self, surf, game, mouse_pos):
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((14, 0, 6, 190))
        surf.blit(dim, (0, 0))
        self.text(surf, "GAME OVER", self.f_big, RED, (WIDTH // 2, 230), "center", glow=True)
        panel = pygame.Rect(WIDTH // 2 - 230, 330, 460, 330)
        pygame.draw.rect(surf, PANEL, panel, border_radius=20)
        pygame.draw.rect(surf, (90, 110, 170), panel, 2, border_radius=20)
        cx = WIDTH // 2
        self.text(surf, "SCORE", self.f_small, GRAY, (cx, 365), "center")
        self.text(surf, f"{game.score:,}".replace(",", "."), self.f_title, WHITE, (cx, 405), "center", glow=True)
        self.text(surf, "LEVEL", self.f_small, GRAY, (cx, 470), "center")
        self.text(surf, str(game.level), self.f_med, CYAN, (cx, 505), "center", glow=True)
        self.text(surf, "HIGHSCORE", self.f_small, GRAY, (cx, 565), "center")
        self.text(surf, f"{game.highscore:,}".replace(",", "."), self.f_med, YELLOW, (cx, 600), "center", glow=True)
        if game.new_highscore and int(game.time * 3) % 2 == 0:
            self.text(surf, "NEUER HIGHSCORE!", self.f_hud, YELLOW, (cx, 690), "center", glow=True)
        for b in self.over_buttons:
            self.draw_button(surf, b, mouse_pos)
        self.text(surf, "oder LEERTASTE", self.f_small, GRAY, (cx, 840), "center")


# =============================================================================
# GAME
# =============================================================================
class Game:
    def __init__(self):
        pygame.display.init()
        pygame.font.init()
        try:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED)
        except pygame.error:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.canvas = pygame.Surface((WIDTH, HEIGHT))          # Spielwelt (wird gewackelt)
        self.flash_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.stars = Starfield()
        self.sounds = SoundBank()
        self.ui = UI()
        self.player = Player()
        self.menu_ship = pygame.transform.smoothscale(self.player.sprite, (150, 150))
        self.highscore = load_highscore()
        self.running = True
        self.time = 0.0
        self.state = "menu"                # menu | playing | paused | gameover
        self.state_time = 0.0
        self.reset_run()

    # --- Zustand --------------------------------------------------------------
    def reset_run(self):
        self.player.reset()
        self.enemies, self.bullets, self.particles = [], [], []
        self.score = 0
        self.level = 1
        self.kills_in_level = 0
        self.bar_display = 0.0
        self.wave_timer = WAVE_START_DELAY
        self.shake = 0.0
        self.flash = (0.0, WHITE, 0.0)      # (Restzeit, Farbe, Gesamtdauer)
        self.banner_timer = 0.0
        self.death_timer = 0.0
        self.new_highscore = False

    def set_state(self, state):
        self.state = state
        self.state_time = 0.0

    def start_game(self):
        self.reset_run()
        self.set_state("playing")
        self.sounds.play("click")

    def end_game(self):
        self.new_highscore = self.score > self.highscore
        if self.new_highscore:
            self.highscore = self.score
            save_highscore(self.highscore)
        self.set_state("gameover")

    def toggle_pause(self):
        if self.state == "playing":
            self.set_state("paused")
        elif self.state == "paused":
            self.set_state("playing")

    # --- Eingaben -------------------------------------------------------------
    def handle_event(self, e):
        focus_lost = getattr(pygame, "WINDOWFOCUSLOST", None)
        if e.type == pygame.QUIT:
            self.running = False
        elif focus_lost is not None and e.type == focus_lost and self.state == "playing":
            self.set_state("paused")           # Fokus weg -> automatisch pausieren
        elif e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_ESCAPE, pygame.K_p):
                if self.state in ("playing", "paused"):
                    self.toggle_pause()
                elif self.state == "menu" and e.key == pygame.K_ESCAPE:
                    self.running = False
            elif e.key in (pygame.K_SPACE, pygame.K_RETURN):
                if self.state == "menu" or (self.state == "gameover" and self.state_time > 0.4):
                    self.start_game()
        elif e.type == pygame.MOUSEMOTION:
            self.player.control = "mouse"
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.handle_click(e.pos)

    def handle_click(self, pos):
        ui = self.ui
        if self.state == "menu":
            action = ui.hit(ui.menu_buttons, pos)
        elif self.state == "gameover":
            action = ui.hit(ui.over_buttons, pos) if self.state_time > 0.4 else None
        elif self.state == "paused":
            action = ui.hit(ui.pause_buttons, pos)
            if action is None and ui.pause_rect.collidepoint(pos):
                action = "resume"
        elif self.state == "playing":
            action = "pause" if ui.pause_rect.collidepoint(pos) else None
        else:
            action = None
        if action == "start" or action == "restart":
            self.start_game()
        elif action == "resume":
            self.sounds.play("click")
            self.set_state("playing")
        elif action == "pause":
            self.sounds.play("click")
            self.set_state("paused")
        elif action == "quit":
            self.running = False

    # --- Effekte --------------------------------------------------------------
    def add_shake(self, amount):
        self.shake = min(SHAKE_MAX, self.shake + amount)

    def add_flash(self, color, duration, ):
        self.flash = (duration, color, duration)

    def add_particle(self, p):
        if len(self.particles) < MAX_PARTICLES:
            self.particles.append(p)

    def explode(self, pos, color, count=26, speed=320, size=5, ring=True):
        for _ in range(count):
            a = random.uniform(0, math.tau)
            v = Vector2(math.cos(a), math.sin(a)) * random.uniform(speed * 0.2, speed)
            col = random.choice([color, color, WHITE, YELLOW])
            self.add_particle(Particle(pos, v, random.uniform(0.35, 0.8), col,
                                       random.uniform(size * 0.6, size * 1.4)))
        if ring:
            self.add_particle(Particle(pos, (0, 0), 0.4, color, 6, ring=True, grow=size * 7))

    # --- Spawning -------------------------------------------------------------
    def spawn_wave(self):
        lv = self.level
        kinds = [k for k, s in ENEMY_TYPES.items() if lv >= s["unlock"]]
        kind = random.choices(kinds, [ENEMY_TYPES[k]["weight"] for k in kinds])[0]
        patterns = ["single", "single", "row"] if lv == 1 else ["single", "row", "column", "v"]
        pattern = random.choice(patterns)
        n = min(2 + lv // 3, 6)
        if kind == "tank":
            n = min(n, 2)
        margin = 60
        if pattern == "single":
            n = 1
        spots = []
        if pattern in ("single", "row"):
            span = min(WIDTH - 2 * margin, 150 * n) if n > 1 else 0
            cx = random.uniform(margin + span / 2, WIDTH - margin - span / 2)
            for i in range(n):
                x = cx - span / 2 + (span * i / (n - 1) if n > 1 else 0)
                spots.append((x, -60))
        elif pattern == "column":
            x = random.uniform(margin, WIDTH - margin)
            spots = [(x, -60 - i * 95) for i in range(n)]
        else:                                           # V-Formation, Anführer vorne
            count = min(n | 1, 5)
            cx = random.uniform(margin + 160, WIDTH - margin - 160)
            for i in range(count):
                k = i - count // 2
                spots.append((cx + k * 85, -60 - abs(k) * 75))
        for x, y in spots:
            if len(self.enemies) >= MAX_ENEMIES:
                break
            self.enemies.append(Enemy(kind, x, y, lv, target_x=self.player.pos.x))

    # --- Spielregeln ----------------------------------------------------------
    def kill_enemy(self, e):
        e.dead = True
        self.score += e.points
        self.kills_in_level += 1
        color = ENEMY_GLOW[e.kind] if e.kind != "asteroid" else (255, 190, 120)
        self.explode(e.pos, color, count=14 + int(e.size / 4), size=3 + e.size / 25)
        self.add_shake(3 + e.size / 20)
        self.sounds.play("explode")
        if self.kills_in_level >= kills_needed(self.level):
            self.level_up()

    def level_up(self):
        self.level += 1
        self.kills_in_level = 0
        self.banner_timer = LEVELUP_BANNER_TIME
        self.add_flash(WHITE, 0.45)
        self.add_shake(10)
        self.sounds.play("levelup")
        for r, g in ((8, 90), (6, 160), (4, 240)):       # Schockwellen um das Schiff
            self.add_particle(Particle(self.player.pos, (0, 0), 0.7, CYAN, r, ring=True, grow=g * 2))
        self.explode(self.player.pos, YELLOW, count=40, speed=500, ring=False)

    def hurt_player(self, e):
        p = self.player
        p.lives -= 1
        p.invuln = INVULN_TIME
        e.dead = True
        self.explode(e.pos, ORANGE, count=24)
        self.add_shake(16)
        self.add_flash(RED, 0.3)
        self.sounds.play("hit")
        if p.lives <= 0:
            p.alive = False
            self.death_timer = 0.0
            self.explode(p.pos, CYAN, count=70, speed=520, size=7)
            self.explode(p.pos, MAGENTA, count=40, speed=380, size=6)
            self.add_shake(26)

    def handle_collisions(self):
        for b in self.bullets:
            for e in self.enemies:
                if e.dead or e in b.hit:
                    continue
                if (b.pos - e.pos).length_squared() <= (b.radius + e.radius) ** 2:
                    b.hit.add(e)
                    e.hp -= b.damage
                    e.hit_flash = 0.08
                    for _ in range(3):
                        v = Vector2(random.uniform(-160, 160), random.uniform(-260, -40))
                        self.add_particle(Particle(b.pos, v, 0.3, b.color, 3))
                    if e.hp <= 0:
                        self.kill_enemy(e)
                    if not b.pierce:
                        b.alive = False
                        break
        p = self.player
        if p.alive and p.invuln <= 0:
            for e in self.enemies:
                if not e.dead and (e.pos - p.pos).length_squared() <= (e.radius + PLAYER_HIT_RADIUS) ** 2:
                    self.hurt_player(e)
                    break

    # --- Update ---------------------------------------------------------------
    def update(self, dt):
        self.time += dt
        self.state_time += dt
        if self.state == "paused":
            return                                      # Spielwelt eingefroren
        self.stars.update(dt)
        if self.state == "menu":
            return
        if self.state == "playing":
            self.update_playing(dt)
        else:                                           # gameover: Partikel laufen aus
            self.update_world_effects(dt)

    def update_world_effects(self, dt):
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.life > 0]
        self.shake = max(0.0, self.shake - SHAKE_DECAY * dt)
        t, col, total = self.flash
        self.flash = (max(0.0, t - dt), col, total)
        self.banner_timer = max(0.0, self.banner_timer - dt)
        target = self.kills_in_level / kills_needed(self.level)
        self.bar_display += (target - self.bar_display) * (1 - math.exp(-8 * dt))

    def update_playing(self, dt):
        p = self.player
        if p.alive:
            mouse_pos = pygame.mouse.get_pos()
            mouse_ok = pygame.mouse.get_focused() and not self.ui.pause_rect.collidepoint(mouse_pos)
            p.update(dt, pygame.key.get_pressed(), mouse_pos, mouse_ok)
            p.cooldown -= dt
            if p.cooldown <= 0:                         # Auto-Fire
                new, cooldown = p.fire(self.level)
                self.bullets.extend(new)
                p.cooldown = cooldown
                self.sounds.play("shoot")
        else:
            self.death_timer += dt
            if self.death_timer >= GAME_OVER_DELAY:
                self.end_game()

        self.wave_timer -= dt
        if self.wave_timer <= 0:
            self.spawn_wave()
            self.wave_timer = max(WAVE_INTERVAL_MIN,
                                  WAVE_INTERVAL_BASE - WAVE_INTERVAL_DECAY * (self.level - 1))

        for b in self.bullets:
            b.update(dt)
        self.enemies = [e for e in self.enemies if e.update(dt) and not e.dead]
        self.handle_collisions()
        self.bullets = [b for b in self.bullets if b.alive]
        self.enemies = [e for e in self.enemies if not e.dead]
        self.update_world_effects(dt)

    # --- Zeichnen ---------------------------------------------------------------
    def draw_world(self):
        c = self.canvas
        self.stars.draw(c)
        for e in self.enemies:
            e.draw(c)
        for b in self.bullets:
            b.draw(c)
        if self.player.alive and self.state != "menu":
            self.player.draw(c)
        for p in self.particles:
            p.draw(c)

    def draw(self):
        mouse_pos = pygame.mouse.get_pos()
        self.draw_world()
        self.screen.fill((0, 0, 0))
        ox = oy = 0
        if self.shake > 0.5:
            ox = int(random.uniform(-self.shake, self.shake))
            oy = int(random.uniform(-self.shake, self.shake))
        self.screen.blit(self.canvas, (ox, oy))

        t, col, total = self.flash
        if t > 0:
            self.flash_surf.fill((*col, int(150 * t / total)))
            self.screen.blit(self.flash_surf, (0, 0))

        if self.state == "menu":
            self.ui.draw_menu(self.screen, self, mouse_pos)
        else:
            self.ui.draw_hud(self.screen, self, mouse_pos)
            self.ui.draw_banner(self.screen, self)
            if self.state == "paused":
                self.ui.draw_pause(self.screen, mouse_pos)
            elif self.state == "gameover":
                self.ui.draw_game_over(self.screen, self, mouse_pos)
        pygame.display.flip()

    # --- Hauptschleife ----------------------------------------------------------
    def run(self):
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)    # Delta-Time, gedeckelt
            for e in pygame.event.get():
                self.handle_event(e)
            self.update(dt)
            self.draw()
        pygame.quit()


def main():
    Game().run()


if __name__ == "__main__":
    main()
    sys.exit()
