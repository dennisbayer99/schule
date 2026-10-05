#!/usr/bin/env python3
"""
GALAXY SHOOTER
==============
Arcade-Shooter mit pygame im Galaga-Stil: Gegner fliegen in Schwärmen ein,
nehmen Formation ein und stürzen sich auf dich. Nach einigen Schwärmen kommt
ein Endboss. Alles wird prozedural gezeichnet, es sind keine Dateien nötig.
Eigene Sprites/Sounds kannst du optional in den Ordner assets/ legen.

Installation:  pip install pygame      (bei Python 3.13+: pip install pygame-ce)
Start:         python main.py
"""
import array
import bisect
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
PLAYER_MAX_LIVES = 5               # mehr Leben kann man nicht sammeln
PLAYER_SIZE = 80                   # Sprite-Größe der Grundstufe in Pixel
PLAYER_HIT_RADIUS = 16             # Hitbox (kleiner als das Sprite = fairer)
PLAYER_TIER_LEVELS = (3, 5, 7, 9)  # ab diesen Leveln bekommt das Schiff ein Upgrade
PLAYER_SIZE_PER_TIER = 10          # so viele Pixel wächst das Schiff pro Stufe
PLAYER_HIT_PER_TIER = 1.2          # Hitbox wächst nur minimal mit
PLAYER_MAX_SPEED = 640.0           # max. Geschwindigkeit in px/s
PLAYER_RESPONSE = 9.0              # Trägheit: kleiner = träger/schwammiger
MOUSE_FOLLOW = 7.0                 # wie stark das Schiff der Maus hinterherzieht
INVULN_TIME = 2.0                  # Unverwundbarkeit nach Treffer (Sekunden)
GAME_OVER_DELAY = 1.6              # Pause zwischen Tod und Game-Over-Screen

# --- Level-System ------------------------------------------------------------
KILLS_BASE = 10                    # Kills für Level 1 -> 2
KILLS_STEP = 5                     # jedes weitere Level braucht so viele mehr
LEVELUP_BANNER_TIME = 2.4


def kills_needed(level):
    """Benötigte Kills für den Aufstieg: 10 + (Level - 1) * 5."""
    return KILLS_BASE + (level - 1) * KILLS_STEP


# --- Waffen ------------------------------------------------------------------
BULLET_SPEED = 980.0
FIRE_RATE_MIN_COOLDOWN = 0.10

# --- Schwärme (Galaga-Formation) ---------------------------------------------
SWARMS_PER_BOSS = 4                # nach so vielen Schwärmen kommt ein Boss
SWARM_BREAK = 1.6                  # Pause zwischen zwei Schwärmen (s)
SWARM_ENTRY_SPEED = 430.0          # Tempo beim Einfliegen
SWARM_ENTRY_GAP = 0.14             # Abstand (s) zwischen Gegnern in der Kette
FORMATION_TOP = 170                # y-Position der hintersten Reihe
FORMATION_SWAY = 70                # wie weit die Formation hin und her schwingt
SLOT_DX, SLOT_DY = 76, 62          # Abstand der Plätze in der Formation
DIVE_SPEED = 380.0                 # Tempo der Sturzflüge
DIVE_INTERVAL_BASE = 3.2           # Sekunden zwischen Sturzflügen auf Level 1
DIVE_INTERVAL_DECAY = 0.15         # pro Level kürzer
DIVE_INTERVAL_MIN = 0.9
STRAGGLER_COUNT = 2                # so wenige übrig -> sie greifen nur noch an
STRAGGLER_TIMEOUT = 14.0           # danach ziehen die Nachzügler ab

# --- Asteroiden (Hindernisse zwischendurch) ----------------------------------
ASTEROID_INTERVAL_BASE = 7.0
ASTEROID_INTERVAL_DECAY = 0.3
ASTEROID_INTERVAL_MIN = 2.5

# --- Gegner-Skalierung -------------------------------------------------------
ENEMY_SPEED_PER_LEVEL = 0.05       # +5 % Tempo pro Level
ENEMY_SPEED_CAP = 2.0
ENEMY_HP_PER_LEVEL = 0.18          # +18 % Lebenspunkte pro Level

# hp = Leben, size = Pixel, points = Score, unlock = ab Level, dive = Sturzflug-Tempo
ENEMY_TYPES = {
    "grunt":    dict(hp=2, size=58, points=10, unlock=1, dive=1.0),
    "scout":    dict(hp=1, size=48, points=15, unlock=2, dive=1.45),
    "zigzag":   dict(hp=2, size=62, points=20, unlock=3, dive=1.1),
    "tank":     dict(hp=7, size=86, points=40, unlock=4, dive=0.6),
    "asteroid": dict(hp=3, size=(52, 72, 94), points=15, unlock=1, dive=1.0, speed=150),
}

# Gegner-Schüsse: ab welchem Level, Cooldown (s), Muster
ENEMY_FIRE = {
    "grunt":  dict(unlock=2, cooldown=3.4, pattern="straight"),   # ab Lv6 gezielt
    "zigzag": dict(unlock=3, cooldown=2.9, pattern="aimed"),
    "tank":   dict(unlock=4, cooldown=2.4, pattern="spread"),
}
ENEMY_BULLET_SPEED = 330.0
ENEMY_BULLET_SPEED_PER_LEVEL = 0.03
ENEMY_BULLET_SPEED_CAP = 1.7
ENEMY_FIRE_RATE_PER_LEVEL = 0.06
ENEMY_FIRE_RATE_CAP = 2.2
MAX_ENEMY_BULLETS = 220

# --- Boss --------------------------------------------------------------------
BOSS_BASE_HP = 200
BOSS_HP_GROWTH = 1.0               # jeder weitere Boss hat +100 % Basis-Leben
BOSS_POINTS = 1500
BOSS_KILL_VALUE = 5                # zählt wie 5 Kills für das Level-System
BOSS_WARNING_TIME = 2.6
BOSS_DEATH_TIME = 2.2
BOSS_Y = 230
BOSS_NAMES = ["DREADNOUGHT", "VOID-KÖNIGIN", "MUTTERSCHIFF"]

# --- Combo -------------------------------------------------------------------
COMBO_WINDOW = 1.8                 # Sekunden bis die Combo abreißt
COMBO_STEP = 5                     # alle 5 Kills steigt der Multiplikator
COMBO_MAX = 5                      # max. x5

# --- Effekte -----------------------------------------------------------------
SHAKE_DECAY = 70.0
SHAKE_MAX = 28.0
MAX_PARTICLES = 500
ROT_STEP = 10                      # Grad pro vorberechnetem Drehbild

# --- Farben ------------------------------------------------------------------
BG_TOP = (6, 6, 24)
BG_BOTTOM = (26, 12, 44)
CYAN = (70, 225, 255)
MAGENTA = (255, 70, 200)
YELLOW = (255, 215, 70)
ORANGE = (255, 145, 45)
GREEN = (80, 255, 150)
RED = (255, 70, 80)
WHITE = (255, 255, 255)
GRAY = (150, 160, 190)
PANEL = (14, 16, 38)
OUTLINE = (22, 18, 34)             # dunkle Kontur aller Schiffe (Referenz-Stil)
METAL = (78, 82, 100)
METAL_DARK = (40, 42, 56)
METAL_HI = (165, 170, 190)

# --- ASSETS ------------------------------------------------------------------
# PNGs in assets/ ersetzen die gezeichneten Grafiken automatisch:
#   player.png (oder player_0.png ... player_4.png für jede Schiff-Stufe),
#   grunt.png, scout.png, zigzag.png, tank.png (nach UNTEN schauend), boss.png
# Sounds in assets/sounds/: shoot, explode, hit, levelup, click, alarm, boom, bonus (.wav)
BASE_DIR = Path(__file__).resolve().parent
ASSET_DIR = BASE_DIR / "assets"
HIGHSCORE_FILE = BASE_DIR / "highscore.json"

WEAPON_NAMES = {1: "Pulsschuss", 2: "Schwerer Schuss", 3: "Doppelschuss",
                4: "Dreifach-Fächer", 5: "Durchschlag-Strahl"}


def weapon_name(level):
    return WEAPON_NAMES.get(level, f"Mega-Salve (Stufe {level - 5})")


# =============================================================================
# HILFSFUNKTIONEN: Glow, Sprites, Highscore
# =============================================================================
_glow_cache = {}
_asset_cache = {}


def shade(col, f):
    return tuple(max(0, min(255, int(c * f))) for c in col)


def glow_surf(radius, color):
    """Weicher Leuchtfleck (gecacht), wird additiv geblittet."""
    r = max(2, int(radius) // 2 * 2)
    col = tuple(min(255, (int(c) + 8) // 16 * 16) for c in color)
    key = (r, col)
    surf = _glow_cache.get(key)
    if surf is None:
        if len(_glow_cache) > 1500:                     # Speicher begrenzen
            _glow_cache.clear()
        surf = pygame.Surface((r * 2, r * 2)).convert()
        surf.fill((0, 0, 0))
        step = 1 if r <= 64 else 2
        for i in range(r, 0, -step):
            f = (1 - i / r) ** 1.8
            pygame.draw.circle(surf, (int(col[0] * f), int(col[1] * f), int(col[2] * f)), (r, r), i)
        _glow_cache[key] = surf
    return surf


def draw_glow(surf, pos, radius, color):
    if radius < 2:
        return
    g = glow_surf(radius, color)
    r = g.get_width() // 2
    surf.blit(g, (int(pos[0]) - r, int(pos[1]) - r), special_flags=pygame.BLEND_ADD)


def render_sprite(size, draw_fn, supersample=3):
    """Zeichnet in mehrfacher Auflösung und skaliert glatt herunter (Anti-Aliasing)."""
    w, h = size
    big = pygame.Surface((w * supersample, h * supersample), pygame.SRCALPHA)
    draw_fn(big, w * supersample, h * supersample)
    return pygame.transform.smoothscale(big, (w, h)).convert_alpha()


def try_asset(name, size):
    key = (name, tuple(size))
    if key not in _asset_cache:
        img = None
        path = ASSET_DIR / f"{name}.png"
        if path.exists():
            try:
                img = pygame.transform.smoothscale(pygame.image.load(str(path)).convert_alpha(), size)
            except (pygame.error, OSError):
                img = None
        _asset_cache[key] = img
    return _asset_cache[key]


def make_flash(img, tint=(150, 150, 150)):
    """Aufgehellte/getönte Kopie für das Treffer-Aufblitzen."""
    c = img.copy()
    c.fill((*tint, 0), special_flags=pygame.BLEND_RGB_ADD)
    return c


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


def fmt(n):
    return f"{n:,}".replace(",", ".")


# =============================================================================
# ZEICHENSTIFT IM REFERENZ-STIL (Panzerplatten, Kontur, Rohre, Turbinen)
# Koordinaten sind relativ (0..1), sym=True spiegelt an der Mittelachse.
# =============================================================================
class Pen:
    def __init__(self, surf, W, H):
        self.s, self.W, self.H = surf, W, H
        self.lw = max(2, int(min(W, H) * 0.018))

    def P(self, pts):
        return [(x * self.W, y * self.H) for x, y in pts]

    def _each(self, pts, sym):
        return (pts, [(1 - x, y) for x, y in pts]) if sym else (pts,)

    def plate(self, pts, col, sym=False, bevel=True):
        """Panzerplatte: dunkler Rand, hellere Innenfläche, dicke Kontur."""
        for p in self._each(pts, sym):
            P = self.P(p)
            pygame.draw.polygon(self.s, shade(col, 0.70) if bevel else col, P)
            if bevel:
                cx = sum(x for x, _ in P) / len(P)
                cy = sum(y for _, y in P) / len(P)
                inner = [(cx + (x - cx) * 0.78, cy + (y - cy) * 0.78 - self.H * 0.006) for x, y in P]
                pygame.draw.polygon(self.s, col, inner)
            pygame.draw.polygon(self.s, OUTLINE, P, self.lw)

    def line(self, a, b, col, w=1.0, sym=False):
        for p in self._each([a, b], sym):
            P = self.P(p)
            pygame.draw.line(self.s, col, P[0], P[1], max(1, int(self.lw * w)))

    def rect(self, x, y, w, h, col, sym=False, outline=True):
        for xx in ((x, 1 - x - w) if sym else (x,)):
            r = pygame.Rect(int(xx * self.W), int(y * self.H), max(1, int(w * self.W)), max(1, int(h * self.H)))
            rad = int(min(r.w, r.h) * 0.25)
            pygame.draw.rect(self.s, col, r, border_radius=rad)
            if outline:
                pygame.draw.rect(self.s, OUTLINE, r, self.lw, border_radius=rad)

    def barrel(self, cx, y, w, h, sym=False):
        """Kanonenrohr, cx = Mitte."""
        self.rect(cx - w / 2, y, w, h, METAL, sym)
        self.rect(cx - w / 2, y, w, h * 0.14, METAL_HI, sym)
        self.line((cx - w * 0.12, y + h * 0.25), (cx - w * 0.12, y + h * 0.85), METAL_HI, 0.6, sym)

    def circle(self, cx, cy, r, col, sym=False, outline=True):
        for xx in ((cx, 1 - cx) if sym else (cx,)):
            c = (int(xx * self.W), int(cy * self.H))
            rr = max(1, int(r * self.W))
            pygame.draw.circle(self.s, col, c, rr)
            if outline:
                pygame.draw.circle(self.s, OUTLINE, c, rr, self.lw)

    def turbine(self, cx, cy, r, sym=False):
        """Runde Turbine mit Kreuz (wie in der Referenz)."""
        self.circle(cx, cy, r, METAL, sym)
        self.circle(cx, cy, r * 0.62, METAL_DARK, sym)
        d = r * 0.42
        for xx in ((cx, 1 - cx) if sym else (cx,)):
            for sx, sy in ((1, 1), (1, -1)):
                a = ((xx - d * sx) * self.W, cy * self.H - d * sy * self.W)
                b = ((xx + d * sx) * self.W, cy * self.H + d * sy * self.W)
                pygame.draw.line(self.s, METAL_HI, a, b, max(1, self.lw // 2))

    def gem(self, cx, cy, w, h, col):
        """Cockpit als geschliffener Edelstein mit Glanzlicht."""
        top, right, bot, left = (cx, cy - h / 2), (cx + w / 2, cy), (cx, cy + h / 2), (cx - w / 2, cy)
        pygame.draw.polygon(self.s, shade(col, 0.55), self.P([top, right, bot, left]))
        pygame.draw.polygon(self.s, col, self.P([top, right, (cx, cy + h * 0.15), left]))
        pygame.draw.polygon(self.s, shade(col, 1.35), self.P([top, (cx, cy + h * 0.15), left]))
        pygame.draw.line(self.s, WHITE, *self.P([(cx - w * 0.18, cy - h * 0.12), (cx - w * 0.04, cy - h * 0.34)]),
                         max(1, self.lw))
        pygame.draw.polygon(self.s, OUTLINE, self.P([top, right, bot, left]), self.lw)

    def nozzle(self, cx, y, w, h, sym=False):
        """Triebwerksdüse mit glühendem Inneren."""
        self.rect(cx - w / 2, y, w, h, METAL_DARK, sym)
        self.rect(cx - w * 0.3, y + h * 0.45, w * 0.6, h * 0.4, ORANGE, sym, outline=False)


# =============================================================================
# SPRITE-DESIGNS
# =============================================================================
def player_tier(level):
    return sum(1 for lv in PLAYER_TIER_LEVELS if level >= lv)


def player_size(tier):
    return PLAYER_SIZE + PLAYER_SIZE_PER_TIER * tier


def draw_player(s, W, H, tier=0):
    """Eigenes Schiff im Stil der Referenz (hellblau, gelbe Streifen, oranges Cockpit).
    Jede Stufe fügt Teile hinzu: Pods, breitere Flügel, Canards, Pylonen."""
    pen = Pen(s, W, H)
    A = (110, 190, 238)
    A2 = (66, 132, 200)
    Y = (255, 210, 60) if tier < 4 else (255, 180, 40)
    G = (255, 150, 40)
    HI = (225, 245, 255)
    if tier >= 4:   # äußere Pylonen mit langen Rohren und Turbinen
        pen.barrel(0.08, 0.06, 0.035, 0.26, sym=True)
        pen.plate([(0.03, 0.30), (0.13, 0.27), (0.15, 0.82), (0.02, 0.86)], A2, sym=True)
        pen.turbine(0.085, 0.62, 0.05, sym=True)
        pen.line((0.06, 0.36), (0.06, 0.52), Y, 1.2, sym=True)
    if tier >= 2:
        wing = [(0.42, 0.34), (0.05, 0.66), (0.07, 0.86), (0.25, 0.88), (0.42, 0.80)]
    else:
        wing = [(0.42, 0.42), (0.12, 0.70), (0.14, 0.85), (0.42, 0.79)]
    pen.plate(wing, A, sym=True)
    pen.line((wing[1][0] + 0.03, wing[1][1] + 0.03), (0.40, wing[0][1] + 0.06), HI, 0.8, sym=True)
    pen.line((wing[2][0] + 0.06, wing[2][1] - 0.04), (0.36, 0.70), Y, 1.3, sym=True)
    if tier >= 1:   # Stacheln an den Flügeln
        tip = wing[1]
        pen.plate([(tip[0] + 0.01, tip[1]), (tip[0] - 0.01, tip[1] - 0.10), (tip[0] + 0.05, tip[1] - 0.02)],
                  METAL_HI, sym=True, bevel=False)
        # Seiten-Pods mit Turbine und Kanone
        pen.barrel(0.28, 0.22, 0.035, 0.24, sym=True)
        pen.plate([(0.23, 0.42), (0.33, 0.42), (0.34, 0.80), (0.22, 0.80)], A2, sym=True)
        pen.turbine(0.28, 0.64, 0.05, sym=True)
        pen.nozzle(0.28, 0.80, 0.07, 0.07, sym=True)
    else:
        pen.barrel(0.30, 0.44, 0.03, 0.16, sym=True)
    if tier >= 3:   # Canards + zusätzliche Rohre
        pen.barrel(0.37, 0.10, 0.03, 0.20, sym=True)
        pen.plate([(0.41, 0.22), (0.25, 0.32), (0.27, 0.40), (0.41, 0.36)], A, sym=True)
        pen.nozzle(0.44, 0.86, 0.08, 0.10, sym=True)
    else:
        pen.nozzle(0.5, 0.86, 0.12, 0.10)
    if tier >= 2:   # Zwillingsrohre an der Nase
        pen.barrel(0.455, 0.02, 0.026, 0.18, sym=True)
    body = [(0.5, 0.04), (0.58, 0.20), (0.62, 0.50), (0.60, 0.86), (0.5, 0.92),
            (0.40, 0.86), (0.38, 0.50), (0.42, 0.20)]
    pen.plate(body, A)
    pen.plate([(0.5, 0.52), (0.56, 0.60), (0.55, 0.80), (0.5, 0.84), (0.45, 0.80), (0.44, 0.60)], A2, bevel=False)
    pen.line((0.5, 0.56), (0.5, 0.80), Y, 1.0)
    pen.line((0.44, 0.22), (0.47, 0.13), HI, 0.8, sym=True)
    if tier >= 4:   # goldene Krone
        pen.plate([(0.5, 0.0), (0.54, 0.08), (0.5, 0.06), (0.46, 0.08)], Y, bevel=False)
    pen.gem(0.5, 0.34, 0.12, 0.22, G)


def draw_grunt(s, W, H):
    """Rotes Abfangschiff mit grünem Cockpit (Referenz oben links)."""
    pen = Pen(s, W, H)
    R = (205, 48, 52)
    pen.barrel(0.13, 0.50, 0.05, 0.22, sym=True)
    pen.plate([(0.40, 0.38), (0.06, 0.76), (0.10, 0.88), (0.40, 0.80)], R, sym=True)
    pen.line((0.14, 0.80), (0.36, 0.58), WHITE, 0.9, sym=True)
    pen.nozzle(0.5, 0.86, 0.14, 0.10)
    pen.plate([(0.5, 0.02), (0.62, 0.28), (0.66, 0.70), (0.58, 0.90), (0.42, 0.90), (0.34, 0.70), (0.38, 0.28)], R)
    pen.turbine(0.5, 0.70, 0.08)
    pen.line((0.42, 0.50), (0.46, 0.20), (255, 170, 170), 0.8, sym=True)
    pen.gem(0.5, 0.36, 0.15, 0.26, (60, 220, 120))


def draw_scout(s, W, H):
    """Kleiner, schneller oranger Pfeil (Referenz unten Mitte)."""
    pen = Pen(s, W, H)
    O = (242, 152, 42)
    pen.plate([(0.42, 0.74), (0.22, 0.96), (0.42, 0.90)], shade(O, 0.85), sym=True)
    pen.plate([(0.42, 0.36), (0.04, 0.62), (0.06, 0.74), (0.42, 0.70)], O, sym=True)
    pen.plate([(0.07, 0.60), (0.05, 0.48), (0.12, 0.58)], METAL_HI, sym=True, bevel=False)
    pen.nozzle(0.5, 0.86, 0.12, 0.10)
    pen.plate([(0.5, 0.02), (0.58, 0.24), (0.60, 0.80), (0.5, 0.92), (0.40, 0.80), (0.42, 0.24)], O)
    pen.line((0.16, 0.66), (0.38, 0.54), (60, 50, 40), 0.9, sym=True)
    pen.gem(0.5, 0.34, 0.13, 0.22, (60, 220, 235))


def draw_zigzag(s, W, H):
    """Olivgrüner Jäger mit gepfeilten Flügeln und Stacheln (Referenz unten)."""
    pen = Pen(s, W, H)
    OL = (122, 132, 52)
    pen.plate([(0.40, 0.64), (0.24, 0.97), (0.42, 0.90)], shade(OL, 0.85), sym=True)
    pen.plate([(0.40, 0.28), (0.02, 0.60), (0.04, 0.76), (0.22, 0.74), (0.40, 0.66)], OL, sym=True)
    for a, b in (((0.06, 0.70), (0.22, 0.60)), ((0.10, 0.74), (0.28, 0.66))):
        pen.line(a, b, WHITE, 1.1, sym=True)
    pen.plate([(0.19, 0.74), (0.22, 0.88), (0.26, 0.74)], METAL_HI, sym=True, bevel=False)
    pen.turbine(0.30, 0.52, 0.06, sym=True)
    pen.nozzle(0.5, 0.86, 0.12, 0.10)
    pen.plate([(0.5, 0.04), (0.60, 0.26), (0.62, 0.80), (0.5, 0.92), (0.38, 0.80), (0.40, 0.26)], OL)
    pen.line((0.5, 0.56), (0.5, 0.82), (60, 66, 20), 1.0)
    pen.gem(0.5, 0.30, 0.13, 0.24, (50, 205, 190))


def draw_tank(s, W, H):
    """Schwerer violetter Kreuzer mit Seitenpods und Cyan-Kern (Referenz 2)."""
    pen = Pen(s, W, H)
    V = (122, 92, 192)
    V2 = (78, 60, 140)
    pen.barrel(0.13, 0.02, 0.05, 0.22, sym=True)
    pen.rect(0.04, 0.20, 0.18, 0.64, V2, sym=True)
    pen.line((0.09, 0.30), (0.09, 0.72), (180, 150, 255), 0.8, sym=True)
    pen.rect(0.20, 0.42, 0.10, 0.14, METAL, sym=True)
    pen.nozzle(0.13, 0.84, 0.10, 0.10, sym=True)
    pen.barrel(0.42, 0.0, 0.045, 0.16, sym=True)
    pen.plate([(0.30, 0.10), (0.70, 0.10), (0.76, 0.30), (0.76, 0.84), (0.64, 0.96),
               (0.36, 0.96), (0.24, 0.84), (0.24, 0.30)], V)
    pen.rect(0.40, 0.34, 0.20, 0.22, (70, 230, 255))
    pen.rect(0.45, 0.38, 0.06, 0.08, WHITE, outline=False)
    pen.line((0.30, 0.66), (0.70, 0.66), V2, 1.2)
    pen.line((0.30, 0.76), (0.70, 0.76), V2, 1.2)
    pen.nozzle(0.5, 0.88, 0.14, 0.10)


BOSS_PALETTES = [((86, 110, 170), (52, 70, 120)),     # Stahlblau
                 ((126, 82, 186), (82, 52, 132)),     # Violett
                 ((176, 52, 64), (112, 32, 44))]      # Purpur-Rot


def make_boss_drawer(variant):
    B, B2 = BOSS_PALETTES[variant % len(BOSS_PALETTES)]

    def draw(s, W, H):
        pen = Pen(s, W, H)
        # Pylonen mit glühenden Streifen (wie die "I"-Träger der Referenz)
        pen.rect(0.02, 0.10, 0.10, 0.78, B2, sym=True)
        pen.rect(0.05, 0.16, 0.04, 0.66, (255, 170, 60), sym=True, outline=False)
        pen.rect(0.0, 0.05, 0.14, 0.08, METAL, sym=True)
        pen.rect(0.0, 0.85, 0.14, 0.08, METAL, sym=True)
        pen.barrel(0.07, 0.0, 0.03, 0.08, sym=True)
        pen.plate([(0.12, 0.40), (0.30, 0.34), (0.30, 0.56), (0.12, 0.62)], B2, sym=True)
        pen.barrel(0.24, 0.06, 0.028, 0.24, sym=True)
        pen.plate([(0.31, 0.18), (0.16, 0.30), (0.18, 0.76), (0.34, 0.86)], B, sym=True)
        pen.turbine(0.24, 0.62, 0.035, sym=True)
        pen.line((0.20, 0.40), (0.30, 0.34), YELLOW, 1.2, sym=True)
        pen.nozzle(0.42, 0.90, 0.06, 0.08, sym=True)
        pen.nozzle(0.5, 0.92, 0.07, 0.08)
        pen.barrel(0.44, 0.0, 0.028, 0.16, sym=True)
        pen.plate([(0.5, 0.02), (0.62, 0.12), (0.70, 0.30), (0.70, 0.80), (0.60, 0.94),
                   (0.40, 0.94), (0.30, 0.80), (0.30, 0.30), (0.38, 0.12)], B)
        pen.plate([(0.40, 0.58), (0.60, 0.58), (0.64, 0.80), (0.36, 0.80)], B2, bevel=False)
        pen.turbine(0.44, 0.70, 0.035, sym=True)
        pen.rect(0.43, 0.30, 0.14, 0.22, (70, 230, 255))
        pen.rect(0.46, 0.33, 0.04, 0.07, WHITE, outline=False)
        for y in (0.20, 0.24):
            pen.line((0.40, y), (0.60, y), YELLOW, 1.0)
    return draw


ASTEROID_COLORS = [(198, 112, 130), (172, 100, 134), (152, 96, 124)]
ASTEROID_VARIANTS = 6


def make_asteroid_drawer(seed):
    """Facettierter Low-Poly-Asteroid in Rosa/Lila (Referenz 2)."""
    def draw(s, W, H):
        rng = random.Random(seed)
        n = rng.randint(7, 9)
        pts = []
        for i in range(n):
            a = (i + rng.uniform(-0.25, 0.25)) / n * math.tau
            r = rng.uniform(0.38, 0.48)
            pts.append((0.5 + math.cos(a) * r, 0.5 + math.sin(a) * r))
        core = (0.5 + rng.uniform(-0.10, 0.0), 0.5 + rng.uniform(-0.10, 0.0))
        light = Vector2(-0.6, -0.8)
        base = rng.choice(ASTEROID_COLORS)
        P = lambda p: (p[0] * W, p[1] * H)
        lw = max(2, int(W * 0.02))
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            mid = Vector2((a[0] + b[0]) / 2 - 0.5, (a[1] + b[1]) / 2 - 0.5)
            f = 0.55 + 0.6 * max(0.0, mid.normalize().dot(light)) + rng.uniform(-0.05, 0.05)
            pygame.draw.polygon(s, shade(base, f), [P(core), P(a), P(b)])
            pygame.draw.line(s, shade(base, f * 0.8), P(core), P(a), max(1, lw // 2))
        pygame.draw.polygon(s, (60, 28, 52), [P(p) for p in pts], lw)
    return draw


ENEMY_DRAWERS = {"grunt": draw_grunt, "scout": draw_scout, "zigzag": draw_zigzag, "tank": draw_tank}
ENEMY_GLOW = {"grunt": (110, 20, 20), "scout": (110, 60, 10), "zigzag": (50, 70, 20),
              "tank": (70, 40, 130), "asteroid": (60, 30, 50)}

_base_cache = {}
_frame_cache = {}


def enemy_base(kind):
    """Gegner-Sprite (nach unten schauend). Eigene PNGs sollten schon nach unten zeigen."""
    if kind not in _base_cache:
        size = ENEMY_TYPES[kind]["size"]
        img = try_asset(kind, (size, size))
        if img is None:
            img = pygame.transform.flip(render_sprite((size, size), ENEMY_DRAWERS[kind]), False, True)
        _base_cache[kind] = img
    return _base_cache[kind]


def rotated_frame(key, base_fn, angle, flash):
    """Vorberechnete Drehbilder (Performance: rotate nur einmal pro Winkel)."""
    idx = int(round(angle / ROT_STEP)) % (360 // ROT_STEP)
    k = (key, idx, flash)
    img = _frame_cache.get(k)
    if img is None:
        if flash:
            img = make_flash(rotated_frame(key, base_fn, angle, False))
        else:
            base = base_fn()
            img = base if idx == 0 else pygame.transform.rotate(base, idx * ROT_STEP).convert_alpha()
        _frame_cache[k] = img
    return img


def asteroid_base(variant, size):
    key = ("asteroid", variant, size)
    if key not in _base_cache:
        _base_cache[key] = try_asset("asteroid", (size, size)) or render_sprite(
            (size, size), make_asteroid_drawer(variant * 7919 + 13), 2)
    return _base_cache[key]


_bullet_cache = {}


def bullet_sprite(radius, color, glow=1.0, round_=False):
    """Geschoss als ein einziges vorgerendertes Bild (Glow + Kern), additiv geblittet."""
    key = (radius, color, round(glow, 2), round_)
    img = _bullet_cache.get(key)
    if img is None:
        R = max(4, int(radius * 3.2 * glow))
        img = pygame.Surface((R * 2, R * 2)).convert()
        img.fill((0, 0, 0))
        g = glow_surf(R, color)
        img.blit(g, (R - g.get_width() // 2, R - g.get_height() // 2), special_flags=pygame.BLEND_ADD)
        if round_:
            pygame.draw.circle(img, color, (R, R), radius)
            pygame.draw.circle(img, (255, 240, 220), (R, R), max(1, radius - 3))
        else:
            h = min(int(radius * 3.6), R * 2 - 2)
            pygame.draw.ellipse(img, color, (R - radius, R - h // 2, radius * 2, h))
            pygame.draw.ellipse(img, WHITE, (R - radius // 2, R - h // 4, max(2, radius), max(2, h // 2)))
        _bullet_cache[key] = img
    return img


# =============================================================================
# SOUND (erzeugt, optional durch assets/sounds/*.wav ersetzbar)
# =============================================================================
class SoundBank:
    def __init__(self):
        self.ok = False
        self.muted = False
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(22050, -16, 1, 512)
            self.rate, _, self.channels = pygame.mixer.get_init()
            pygame.mixer.set_num_channels(24)
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
            buf.extend([v] * self.channels)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def _build(self):
        sy = self._synth
        gen = {
            "shoot": lambda: sy(900, 350, 0.07, 0.06, square=True),
            "explode": lambda: sy(220, 40, 0.35, 0.28, noise=0.6),
            "hit": lambda: sy(300, 50, 0.55, 0.40, noise=0.5),
            "click": lambda: sy(650, 650, 0.04, 0.15),
            "levelup": lambda: sum((sy(f, f, 0.11, 0.22, square=True) for f in (440, 554, 659, 880)), []),
            "alarm": lambda: sum((sy(f, f, 0.20, 0.20, square=True) for f in (660, 440) * 3), []),
            "boom": lambda: sy(140, 25, 1.1, 0.5, noise=0.75),
            "bonus": lambda: sum((sy(f, f, 0.08, 0.22) for f in (523, 659, 784, 1046)), []),
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
        if self.ok and not self.muted and name in self.sounds:
            self.sounds[name].play()


# =============================================================================
# HINTERGRUND: statisches Weltall + Planet + 3 Parallax-Sternebenen
# =============================================================================
def make_planet(radius, seed):
    rng = random.Random(seed)
    d = radius * 2
    surf = pygame.Surface((d, d), pygame.SRCALPHA)
    base = rng.choice([(150, 80, 120), (110, 80, 150), (160, 100, 90)])
    y = 0
    while y < d:                                   # Streifen wie in der Referenz
        h = rng.randint(d // 14, d // 6)
        pygame.draw.rect(surf, shade(base, rng.uniform(0.75, 1.15)), (0, y, d, h))
        y += h
    shadow = pygame.Surface((d, d), pygame.SRCALPHA)
    shadow.fill((8, 4, 20, 170))
    pygame.draw.circle(shadow, (0, 0, 0, 0), (int(radius * 0.75), int(radius * 0.75)), int(radius * 1.05))
    surf.blit(shadow, (0, 0))
    mask = pygame.Surface((d, d), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (radius, radius), radius)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surf.set_alpha(150)
    return surf.convert_alpha()


class Starfield:
    LAYERS = [(80, 20, 1, 90), (45, 55, 2, 150), (24, 120, 3, 235)]

    def __init__(self):
        self.layers = []
        for count, speed, size, bright in self.LAYERS:
            stars = [[random.uniform(0, WIDTH), random.uniform(0, HEIGHT), random.uniform(0.6, 1.0)]
                     for _ in range(count)]
            self.layers.append((stars, speed, size, bright))
        # Hintergrund EINMAL vorrendern (Verlauf + Nebel) = schnell
        self.bg = pygame.Surface((WIDTH, HEIGHT)).convert()
        for yy in range(HEIGHT):
            t = yy / HEIGHT
            c = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
            pygame.draw.line(self.bg, c, (0, yy), (WIDTH, yy))
        for x, y, r, col in ((0.2, 0.25, 360, (44, 12, 80)), (0.85, 0.6, 320, (10, 28, 80)),
                             (0.4, 0.95, 380, (70, 14, 60))):
            draw_glow(self.bg, (WIDTH * x, HEIGHT * y), r, col)
        for _ in range(250):
            v = random.randint(20, 45)
            self.bg.set_at((random.randrange(WIDTH), random.randrange(HEIGHT)), (v, v, v + 15))
        self.planets = [make_planet(150, 1), make_planet(90, 2), make_planet(60, 3)]
        self.planet = None
        self._new_planet(first=True)

    def _new_planet(self, first=False):
        img = random.choice(self.planets)
        x = random.choice([random.uniform(-40, 220), random.uniform(WIDTH - 220, WIDTH + 40)])
        y = random.uniform(100, HEIGHT * 0.6) if first else -img.get_height()
        self.planet = [img, x, y]

    def update(self, dt):
        for stars, speed, _, _ in self.layers:
            for st in stars:
                st[1] += speed * dt
                if st[1] > HEIGHT:
                    st[0], st[1] = random.uniform(0, WIDTH), -4
        self.planet[2] += 9 * dt
        if self.planet[2] > HEIGHT + 20:
            self._new_planet()

    def draw(self, surf):
        surf.blit(self.bg, (0, 0))
        img, x, y = self.planet
        surf.blit(img, (int(x - img.get_width() / 2), int(y)))
        for stars, _, size, bright in self.layers:
            for x, y, tw in stars:
                b = int(bright * tw)
                col = (b, b, min(255, b + 20))
                if size == 1:
                    surf.set_at((int(x), int(y)), col)
                elif size == 2:
                    pygame.draw.circle(surf, col, (int(x), int(y)), 1)
                else:   # helle Sterne als kleines Kreuz (Pixel-Look der Referenz)
                    ix, iy = int(x), int(y)
                    pygame.draw.line(surf, col, (ix - 2, iy), (ix + 2, iy))
                    pygame.draw.line(surf, col, (ix, iy - 2), (ix, iy + 2))


# =============================================================================
# PARTIKEL & SCHWEBENDE TEXTE
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
        col = shade(self.color, t)
        if self.ring:
            r = int(self.size + self.grow * (1 - t))
            pygame.draw.circle(surf, col, (int(self.pos.x), int(self.pos.y)), r, max(1, int(5 * t)))
            return
        r = self.size * (0.4 + 0.6 * t)
        draw_glow(surf, self.pos, r * 3, col)
        pygame.draw.circle(surf, tuple(int((c + 255) / 2 * t) for c in self.color),
                           (int(self.pos.x), int(self.pos.y)), max(1, int(r * 0.6)))


class FloatText:
    """Punkte-Popup, das aufsteigt und verblasst."""
    def __init__(self, pos, img):
        self.pos = Vector2(pos)
        self.img = img
        self.life = self.max_life = 0.8

    def update(self, dt):
        self.life -= dt
        self.pos.y -= 60 * dt

    def draw(self, surf):
        self.img.set_alpha(int(255 * max(0.0, self.life / self.max_life)))
        surf.blit(self.img, self.img.get_rect(center=(int(self.pos.x), int(self.pos.y))))


# =============================================================================
# GESCHOSSE
# =============================================================================
class Bullet:
    def __init__(self, pos, angle_deg, radius, damage, pierce, glow):
        a = math.radians(angle_deg)
        self.pos = Vector2(pos)
        self.vel = Vector2(math.sin(a), -math.cos(a)) * BULLET_SPEED
        self.radius = radius
        self.damage = damage
        self.pierce = pierce              # durchschlagend: trifft mehrere Gegner
        self.color = MAGENTA if pierce else CYAN
        self.sprite = bullet_sprite(radius, self.color, glow)
        self.hit = set()                  # schon getroffene Ziele (nur 1x Schaden)
        self.alive = True

    def update(self, dt):
        self.pos += self.vel * dt
        if self.pos.y < -40 or self.pos.x < -40 or self.pos.x > WIDTH + 40:
            self.alive = False

    def draw(self, surf):
        r = self.sprite.get_width() // 2
        surf.blit(self.sprite, (int(self.pos.x) - r, int(self.pos.y) - r), special_flags=pygame.BLEND_ADD)


class EnemyBullet:
    STYLES = {"orb": ((255, 110, 40), 7), "pink": ((255, 60, 170), 9), "needle": ((180, 100, 255), 6)}

    def __init__(self, pos, direction, speed, style="orb"):
        col, self.radius = self.STYLES[style]
        self.sprite = bullet_sprite(self.radius, col, 1.0, round_=True)
        self.pos = Vector2(pos)
        self.vel = Vector2(direction) * speed
        self.alive = True

    def update(self, dt):
        self.pos += self.vel * dt
        if not (-40 < self.pos.x < WIDTH + 40 and -60 < self.pos.y < HEIGHT + 40):
            self.alive = False

    def draw(self, surf):
        r = self.sprite.get_width() // 2
        surf.blit(self.sprite, (int(self.pos.x) - r, int(self.pos.y) - r), special_flags=pygame.BLEND_ADD)


def weapon_for_level(level):
    """(Schussliste, Cooldown, Glow). Schuss = (x-Versatz, Winkel, Radius, Schaden, durchschlagend)."""
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
    extra = level - 5
    shots = [(0, 0, 15 + min(extra, 5), 4 + extra // 2, True)]
    for i in range(1, min(1 + extra, 4) + 1):
        dmg = 2 + (1 if level >= 8 else 0)
        shots.append((-i * 10, -i * 9, 6, dmg, False))
        shots.append((i * 10, i * 9, 6, dmg, False))
    cooldown = max(FIRE_RATE_MIN_COOLDOWN, 0.30 - 0.02 * extra)
    return shots, cooldown, min(2.2, 1.3 + 0.12 * extra)


# =============================================================================
# FLUGBAHNEN (Catmull-Rom-Splines für die Schwarm-Einflüge und Sturzflüge)
# =============================================================================
def catmull_rom(points, steps=12):
    pts = [Vector2(p) for p in points]
    pts = [pts[0]] + pts + [pts[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for k in range(steps):
            t = k / steps
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (3 * p1 - p0 - 3 * p2 + p3) * t3))
    out.append(Vector2(pts[-2]))
    return out


class FlightPath:
    def __init__(self, points):
        self.pts = catmull_rom(points)
        self.cum = [0.0]
        for a, b in zip(self.pts, self.pts[1:]):
            self.cum.append(self.cum[-1] + a.distance_to(b))
        self.length = self.cum[-1]

    def pos_at(self, d):
        if d <= 0:
            return Vector2(self.pts[0])
        if d >= self.length:
            return Vector2(self.pts[-1])
        i = bisect.bisect_right(self.cum, d) - 1
        seg = self.cum[i + 1] - self.cum[i]
        t = (d - self.cum[i]) / seg if seg > 0 else 0.0
        return self.pts[i].lerp(self.pts[i + 1], t)


# Einflug-Bahnen für die linke Hälfte des Schwarms (rechts wird gespiegelt), relativ zu Breite/Höhe
ENTRY_PATHS = {
    "hook":   [(-0.08, 0.16), (0.25, 0.14), (0.45, 0.36), (0.32, 0.56), (0.14, 0.44), (0.24, 0.26)],
    "dive":   [(0.30, -0.06), (0.32, 0.28), (0.55, 0.55), (0.80, 0.42), (0.62, 0.24)],
    "sweep":  [(-0.08, 0.50), (0.30, 0.40), (0.62, 0.52), (0.84, 0.34), (0.60, 0.22)],
    "spiral": [(0.46, -0.06), (0.46, 0.24), (0.70, 0.40), (0.50, 0.58), (0.28, 0.42), (0.44, 0.26)],
}


def entry_path(name, mirror):
    pts = [((1 - x) if mirror else x, y) for x, y in ENTRY_PATHS[name]]
    return FlightPath([(x * WIDTH, y * HEIGHT) for x, y in pts])


class Formation:
    """Die Formation oben: schwingt und 'atmet', die Gegner haben feste Plätze."""
    def __init__(self, slots):
        self.slots = slots
        self.members = []
        self.total = len(slots)
        self.t = 0.0
        self.settled_time = 0.0
        self.dive_timer = 1.5
        self.released = False
        self.release_time = 0.0
        self.leaving = False

    def slot_pos(self, i):
        ox, oy = self.slots[i]
        b = 1 + 0.05 * math.sin(self.t * 1.7)
        sway = math.sin(self.t * 0.7) * FORMATION_SWAY
        return Vector2(WIDTH / 2 + sway + ox * b, FORMATION_TOP + oy * b)


# =============================================================================
# PLAYER
# =============================================================================
class Player:
    def __init__(self):
        self.sprites = {t: self._build(t) for t in range(len(PLAYER_TIER_LEVELS) + 1)}
        self.icon = pygame.transform.smoothscale(self.sprites[0], (28, 28))
        self.reset()

    @staticmethod
    def _build(tier):
        size = (player_size(tier),) * 2
        return (try_asset(f"player_{tier}", size) or try_asset("player", size)
                or render_sprite(size, lambda s, W, H: draw_player(s, W, H, tier)))

    def set_tier(self, tier):
        self.tier = tier
        self.size = player_size(tier)
        self.sprite = self.sprites[tier]
        self.hit_radius = PLAYER_HIT_RADIUS + PLAYER_HIT_PER_TIER * tier

    def reset(self):
        self.pos = Vector2(WIDTH / 2, HEIGHT - 150)
        self.vel = Vector2()
        self.cooldown = 0.3
        self.invuln = 0.0
        self.lives = PLAYER_LIVES
        self.alive = True
        self.control = "keys"              # "keys" oder "mouse"
        self.t = 0.0
        self.set_tier(0)

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
        self.vel += (desired - self.vel) * (1 - math.exp(-PLAYER_RESPONSE * dt))
        self.pos += self.vel * dt
        m = self.size * 0.45
        if self.pos.x < m or self.pos.x > WIDTH - m:
            self.pos.x = max(m, min(WIDTH - m, self.pos.x))
            self.vel.x = 0
        if self.pos.y < 120 or self.pos.y > HEIGHT - m:
            self.pos.y = max(120, min(HEIGHT - m, self.pos.y))
            self.vel.y = 0
        if self.invuln > 0:
            self.invuln -= dt

    def fire(self, level):
        shots, cooldown, glow = weapon_for_level(level)
        bullets = [Bullet((self.pos.x + dx, self.pos.y - self.size * 0.45), ang, r, dmg, pierce, glow)
                   for dx, ang, r, dmg, pierce in shots]
        return bullets, cooldown

    def flames(self):
        """Positionen der Triebwerke (relativ zur Größe) je nach Stufe."""
        if self.tier >= 3:
            out = [(-0.06, 0.46, 0.8), (0.06, 0.46, 0.8)]
        else:
            out = [(0.0, 0.46, 1.0)]
        if self.tier >= 1:
            out += [(-0.22, 0.37, 0.5), (0.22, 0.37, 0.5)]
        return out

    def draw(self, surf):
        if self.invuln > 0 and int(self.invuln * 12) % 2 == 0:
            return
        x, y = self.pos.x, self.pos.y
        flick = 0.8 + 0.3 * math.sin(self.t * 45) + random.uniform(0, 0.25)
        for fx, fy, k in self.flames():
            bx, by = x + fx * self.size, y + fy * self.size
            L = 26 * flick * k * (1 + 0.1 * self.tier)
            w = 7 * k * (1 + 0.1 * self.tier)
            draw_glow(surf, (bx, by + 8), 22 * k * flick, ORANGE)
            pygame.draw.polygon(surf, ORANGE, [(bx - w, by), (bx + w, by), (bx, by + L)])
            pygame.draw.polygon(surf, (255, 240, 180), [(bx - w / 2, by), (bx + w / 2, by), (bx, by + L * 0.55)])
        surf.blit(self.sprite, self.sprite.get_rect(center=(int(x), int(y))))


# =============================================================================
# ENEMY
# =============================================================================
class Enemy:
    """Zustände: wait -> enter (Einflug) -> to_slot -> formation -> dive -> ...
    plus free (Asteroiden) und leave (Nachzügler ziehen ab)."""

    def __init__(self, kind, level, pos=(0, -100)):
        spec = ENEMY_TYPES[kind]
        self.kind = kind
        if kind == "asteroid":
            self.size = random.choice(spec["size"])
            self.variant = random.randrange(ASTEROID_VARIANTS)
            base_hp = spec["hp"] + self.size // 40
        else:
            self.size = spec["size"]
            base_hp = spec["hp"]
        self.hp = max(1, round(base_hp * (1 + ENEMY_HP_PER_LEVEL * (level - 1))))
        self.max_hp = self.hp
        self.speed_mult = min(ENEMY_SPEED_CAP, 1 + ENEMY_SPEED_PER_LEVEL * (level - 1))
        self.points = spec["points"]
        self.radius = self.size * 0.42
        self.pos = Vector2(pos)
        self.vel = Vector2(random.uniform(-60, 60), spec.get("speed", 150) * self.speed_mult)
        self.state = "free"
        self.formation = None
        self.slot = -1
        self.path = None
        self.path_d = 0.0
        self.path_speed = 0.0
        self.delay = 0.0
        self.facing = 0.0
        self.angle = random.uniform(0, 360)
        self.spin = random.uniform(-80, 80)
        self.hit_flash = 0.0
        self.fire_cd = random.uniform(1.0, 2.5)
        self.dead = False
        self.removed = False

    @property
    def active(self):
        return self.state != "wait"

    def follow(self, path, speed, state):
        self.path, self.path_d, self.path_speed, self.state = path, 0.0, speed, state

    def update(self, dt, game):
        if self.hit_flash > 0:
            self.hit_flash -= dt
        st = self.state
        old = Vector2(self.pos)
        if st == "wait":
            self.delay -= dt
            if self.delay <= 0:
                self.state = "enter"
                self.pos = self.path.pos_at(0)
            return True
        if st in ("enter", "dive"):
            self.path_d += self.path_speed * dt
            self.pos = self.path.pos_at(self.path_d)
            if self.path_d >= self.path.length:
                if st == "enter":
                    self.state = "to_slot"
                else:
                    game.dive_finished(self)
        elif st == "to_slot":
            target = self.formation.slot_pos(self.slot)
            d = target - self.pos
            dist = d.length()
            step = SWARM_ENTRY_SPEED * self.speed_mult * dt
            if dist <= step:
                self.pos = target
                self.state = "formation"
            else:
                self.pos += d * (step / dist)
        elif st == "formation":
            self.pos = self.formation.slot_pos(self.slot)
        elif st == "leave":
            self.pos.y -= 420 * dt
            if self.pos.y < -120:
                return False
        else:                                           # free
            self.pos += self.vel * dt
            if self.kind == "asteroid":
                self.angle += self.spin * dt
                m = self.size / 2
                if (self.pos.x < m and self.vel.x < 0) or (self.pos.x > WIDTH - m and self.vel.x > 0):
                    self.vel.x *= -1
            if self.pos.y > HEIGHT + self.size:
                return False
        if self.kind != "asteroid":                     # Schiff dreht sich in Flugrichtung
            v = self.pos - old
            if st == "formation" or v.length_squared() < (30 * dt) ** 2:
                target = 0.0
            else:
                target = math.degrees(math.atan2(v.x, v.y))
            diff = (target - self.facing + 180) % 360 - 180
            self.facing += diff * min(1.0, 10 * dt)
        return True

    def draw(self, surf):
        if self.state == "wait":
            return
        flash = self.hit_flash > 0
        x, y = int(self.pos.x), int(self.pos.y)
        if self.kind == "asteroid":
            img = rotated_frame(("asteroid", self.variant, self.size),
                                lambda: asteroid_base(self.variant, self.size), self.angle, flash)
        else:
            a = math.radians(self.facing)
            back = Vector2(-math.sin(a), -math.cos(a)) * self.size * 0.45
            draw_glow(surf, (x + back.x, y + back.y), self.size * 0.28 * random.uniform(0.85, 1.1), ORANGE)
            draw_glow(surf, (x, y), self.size * 0.6, ENEMY_GLOW[self.kind])
            img = rotated_frame(self.kind, lambda: enemy_base(self.kind), self.facing, flash)
        surf.blit(img, img.get_rect(center=(x, y)))
        if self.max_hp >= 4 and self.hp < self.max_hp:
            w = self.size * 0.8
            bx, by = self.pos.x - w / 2, self.pos.y - self.size * 0.62
            pygame.draw.rect(surf, (40, 20, 40), (bx, by, w, 5))
            pygame.draw.rect(surf, RED, (bx, by, w * max(0, self.hp) / self.max_hp, 5))


# =============================================================================
# BOSS
# =============================================================================
class Boss:
    W, H = 360, 250
    # Trefferzonen (x, y, Radius) relativ zur Mitte: Rumpf, Flügel, Pylonen
    HITBOXES = [(0, 0, 82), (-95, 5, 50), (95, 5, 50), (-155, -50, 32), (155, -50, 32),
                (-155, 45, 32), (155, 45, 32)]

    def __init__(self, level, number):
        self.number = number
        self.sprite = try_asset("boss", (self.W, self.H)) or pygame.transform.flip(
            render_sprite((self.W, self.H), make_boss_drawer(number), 2), False, True)
        self.flash_sprite = make_flash(self.sprite, (70, 70, 70))     # dezent, sonst verliert man Details
        self.rage_sprite = make_flash(self.sprite, (90, 0, 10))       # rote Tönung in Phase 3
        hp = BOSS_BASE_HP * (1 + BOSS_HP_GROWTH * number) * (1 + ENEMY_HP_PER_LEVEL * (level - 1))
        self.hp = self.max_hp = int(hp)
        self.name = BOSS_NAMES[number % len(BOSS_NAMES)]
        self.pos = Vector2(WIDTH / 2, -self.H / 2 - 30)
        self.state = "enter"                            # enter | fight | dying
        self.t = 0.0
        self.hit_flash = 0.0
        self.timers = dict(fan=2.0, turret=3.0, spiral=4.0, ring=3.0, minion=5.0)
        self.spiral_left = 0.0
        self.spiral_tick = 0.0
        self.spiral_angle = 0.0
        self.death_timer = 0.0
        self.boom_tick = 0.0
        self.removed = False
        self.rate = min(ENEMY_FIRE_RATE_CAP, 1 + ENEMY_FIRE_RATE_PER_LEVEL * (level - 1)) * (1 + 0.15 * number)
        self.bullet_speed = ENEMY_BULLET_SPEED * min(ENEMY_BULLET_SPEED_CAP,
                                                     1 + ENEMY_BULLET_SPEED_PER_LEVEL * (level - 1))

    @property
    def phase(self):
        r = self.hp / self.max_hp
        return 1 if r > 0.66 else (2 if r > 0.33 else 3)

    @property
    def vulnerable(self):
        return self.state == "fight"

    def hitboxes(self):
        for dx, dy, r in self.HITBOXES:
            yield self.pos.x + dx, self.pos.y + dy, r

    def start_dying(self):
        self.state = "dying"
        self.death_timer = 0.0

    def update(self, dt, game):
        self.t += dt
        self.hit_flash -= dt
        if self.state == "enter":
            self.pos.y += max(60.0, (BOSS_Y - self.pos.y) * 1.8) * dt
            if self.pos.y >= BOSS_Y - 1:
                self.pos.y = BOSS_Y
                self.state = "fight"
                self.t = 0.0
            return
        if self.state == "dying":
            self.death_timer += dt
            self.boom_tick -= dt
            if self.boom_tick <= 0:
                self.boom_tick = 0.08
                p = self.pos + Vector2(random.uniform(-self.W * 0.45, self.W * 0.45),
                                       random.uniform(-self.H * 0.4, self.H * 0.4))
                game.explode(p, random.choice([ORANGE, YELLOW, MAGENTA]), count=14, size=5)
                game.add_shake(4)
            if self.death_timer >= BOSS_DEATH_TIME:
                self.removed = True
            return
        ph = self.phase
        self.pos.x = WIDTH / 2 + math.sin(self.t * (0.55 + 0.15 * (ph - 1))) * WIDTH * 0.27
        self.pos.y = BOSS_Y + math.sin(self.t * 1.3) * 22
        self.attack(dt, game, ph)

    def attack(self, dt, game, ph):
        r = self.rate * (1 + 0.25 * (ph - 1))
        for k in self.timers:
            self.timers[k] -= dt * r
        spd = self.bullet_speed
        main = self.pos + Vector2(0, self.H * 0.45)
        if self.timers["fan"] <= 0:                     # gezielter Fächer
            aim = game.aim_from(main)
            n = 5 if ph < 3 else 7
            for i in range(n):
                game.fire_enemy_bullet(main, aim.rotate((i - (n - 1) / 2) * 11), spd * 1.05, "pink")
            self.timers["fan"] = 2.2
        if self.timers["turret"] <= 0:                  # Pylonen feuern gerade
            for side in (-1, 1):
                for dy in (0, 28):
                    game.fire_enemy_bullet(self.pos + Vector2(side * 155, self.H * 0.42 - dy),
                                           (0, 1), spd * 1.2, "needle")
            self.timers["turret"] = 1.6
        if ph >= 2:                                     # Spirale
            if self.spiral_left > 0:
                self.spiral_left -= dt
                self.spiral_tick -= dt
                if self.spiral_tick <= 0:
                    self.spiral_tick = 0.085
                    self.spiral_angle += 13
                    arms = 2 if ph == 2 else 3
                    for k in range(arms):
                        game.fire_enemy_bullet(self.pos, Vector2(0, 1).rotate(self.spiral_angle + k * 360 / arms),
                                               spd * 0.8, "orb")
            elif self.timers["spiral"] <= 0:
                self.spiral_left = 2.4
                self.timers["spiral"] = 6.5
        if ph >= 3:
            if self.timers["ring"] <= 0:                # Ring in alle Richtungen
                for k in range(18):
                    game.fire_enemy_bullet(self.pos, Vector2(0, 1).rotate(k * 20 + self.t * 30), spd * 0.9, "orb")
                self.timers["ring"] = 3.4
            if self.timers["minion"] <= 0:              # schickt kleine Jäger los
                game.spawn_minions(self)
                self.timers["minion"] = 7.0

    def draw(self, surf):
        x, y = self.pos.x, self.pos.y
        pulse = 0.75 + 0.25 * math.sin(self.t * 6)
        for ex in (-0.08, 0.0, 0.08):                   # Triebwerke (oben, Schiff schaut nach unten)
            draw_glow(surf, (x + ex * self.W, y - self.H * 0.47), 26 * pulse, ORANGE)
        for side in (-1, 1):
            draw_glow(surf, (x + side * self.W * 0.43, y), 70 * pulse, (110, 55, 0))
        flash = self.hit_flash > 0 or (self.state == "dying" and int(self.death_timer * 14) % 2 == 0)
        if flash:
            img = self.flash_sprite
        elif self.phase == 3 and self.state == "fight" and int(self.t * 4) % 2 == 0:
            img = self.rage_sprite                      # Wut-Phase: pulsiert rot
        else:
            img = self.sprite
        surf.blit(img, img.get_rect(center=(int(x), int(y))))
        draw_glow(surf, (x, y + self.H * 0.09), 40 * pulse, (20, 110, 140))


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
        self.f_score = make_font(54)
        self.f_title = make_font(64)
        self.f_med = make_font(40)
        self.f_hud = make_font(30)
        self.f_small = make_font(20)
        self.f_tiny = make_font(17)
        self._cache = {}
        self.pause_rect = pygame.Rect(WIDTH - 62, 16, 46, 46)
        cx = WIDTH // 2
        self.menu_buttons = [Button((cx - 170, 650, 340, 80), "START", "start")]
        self.over_buttons = [Button((cx - 190, 760, 380, 76), "NEUSTART", "start"),
                             Button((cx - 190, 850, 380, 64), "MENÜ", "menu", GRAY)]
        self.pause_buttons = [
            Button((cx - 190, 400, 380, 80), "WEITER", "resume", GREEN),
            Button((cx - 190, 500, 380, 80), "NEUSTART", "restart", YELLOW),
            Button((cx - 190, 600, 380, 80), "BEENDEN", "quit", RED)]
        self.vignette = self._make_vignette()

    @staticmethod
    def _make_vignette():
        v = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for i in range(40):
            a = int(140 * (1 - i / 40) ** 2)
            pygame.draw.rect(v, (255, 20, 40, a), (i * 3, i * 3, WIDTH - i * 6, HEIGHT - i * 6), 3)
        return v

    def text(self, surf, txt, font, color, pos, anchor="topleft", glow=False):
        key = (txt, id(font), color, glow)
        entry = self._cache.get(key)
        if entry is None:
            if len(self._cache) > 500:
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
                halo = pygame.Surface(base.get_size()).convert()   # Alpha vorab auf Schwarz verrechnen
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
        r = b.rect.move(0, -2) if hover else b.rect
        pygame.draw.rect(surf, fill, r, border_radius=16)
        if hover:
            draw_glow(surf, r.center, r.width * 0.6, shade(b.color, 0.35))
        pygame.draw.rect(surf, b.color, r, 3, border_radius=16)
        self.text(surf, b.label, self.f_med, WHITE, r.center, "center", glow=hover)

    # --- HUD ---------------------------------------------------------------------
    def draw_hud(self, surf, game, mouse_pos):
        x = 24
        self.text(surf, "SCORE", self.f_tiny, GRAY, (x, 12))
        sr = self.text(surf, fmt(game.score), self.f_score, WHITE, (x, 28), glow=True)
        mult = game.combo_mult()
        if mult > 1:                                    # Combo-Anzeige neben dem Score
            cr = self.text(surf, f"x{mult}", self.f_hud, YELLOW, (sr.right + 14, sr.centery - 4), "midleft", glow=True)
            w = int(46 * max(0.0, game.combo_timer / COMBO_WINDOW))
            pygame.draw.rect(surf, YELLOW, (cr.x, cr.bottom + 2, w, 4), border_radius=2)
        self.text(surf, f"LEVEL {game.level}", self.f_hud, CYAN, (x, 88), glow=True)
        bar = pygame.Rect(x, 126, 270, 14)
        pygame.draw.rect(surf, (20, 24, 52), bar, border_radius=7)
        fill_w = int(bar.width * max(0.0, min(1.0, game.bar_display)))
        if fill_w > 2:
            fill = pygame.Rect(bar.x, bar.y, fill_w, bar.height)
            pygame.draw.rect(surf, CYAN, fill, border_radius=7)
            seg = min(fill_w, 40)
            pygame.draw.rect(surf, MAGENTA, (fill.right - seg, fill.y, seg, fill.height), border_radius=7)
        pygame.draw.rect(surf, (90, 110, 170), bar, 2, border_radius=7)
        self.text(surf, f"{game.kills_in_level}/{kills_needed(game.level)}", self.f_tiny, WHITE,
                  (bar.right + 10, bar.centery), "midleft")
        for i in range(game.player.lives):
            surf.blit(game.player.icon, (x + i * 32, 150))
        self.text(surf, weapon_name(game.level), self.f_tiny, GRAY, (x, 186))
        self.draw_progress(surf, game)
        # Pause-Button
        hover = self.pause_rect.collidepoint(mouse_pos)
        pygame.draw.rect(surf, (40, 60, 110) if hover else (18, 24, 52), self.pause_rect, border_radius=10)
        pygame.draw.rect(surf, CYAN, self.pause_rect, 2, border_radius=10)
        r = self.pause_rect
        pygame.draw.rect(surf, WHITE, (r.x + 14, r.y + 12, 6, 22), border_radius=2)
        pygame.draw.rect(surf, WHITE, (r.x + 26, r.y + 12, 6, 22), border_radius=2)
        if game.sounds.muted:
            self.text(surf, "TON AUS (M)", self.f_tiny, GRAY, (r.right, r.bottom + 8), "topright")

    def draw_progress(self, surf, game):
        """Oben Mitte: Fortschritt bis zum Boss bzw. Boss-Lebensbalken."""
        cx = WIDTH // 2 + 70
        boss = game.boss
        if boss is not None:
            self.text(surf, boss.name, self.f_small, RED, (cx, 22), "center", glow=True)
            bar = pygame.Rect(cx - 210, 42, 420, 16)
            pygame.draw.rect(surf, (40, 10, 20), bar, border_radius=8)
            ghost = int(bar.width * game.boss_bar_display)
            real = int(bar.width * max(0, boss.hp) / boss.max_hp)
            pygame.draw.rect(surf, (255, 220, 220), (bar.x, bar.y, ghost, bar.height), border_radius=8)
            pygame.draw.rect(surf, RED, (bar.x, bar.y, real, bar.height), border_radius=8)
            for f in (0.33, 0.66):                      # Phasen-Markierungen
                mx = bar.x + int(bar.width * f)
                pygame.draw.line(surf, OUTLINE, (mx, bar.y), (mx, bar.bottom), 2)
            pygame.draw.rect(surf, (255, 140, 150), bar, 2, border_radius=8)
            return
        done = min(game.swarms_since_boss, SWARMS_PER_BOSS)
        label = "BOSS!" if game.phase == "warning" else f"SCHWARM {min(done + 1, SWARMS_PER_BOSS)}/{SWARMS_PER_BOSS}"
        self.text(surf, label, self.f_small, WHITE, (cx, 22), "center")
        n = SWARMS_PER_BOSS
        x0 = cx - (n * 30) // 2
        for i in range(n):
            c = (x0 + i * 30, 50)
            pts = [(c[0], c[1] - 8), (c[0] + 8, c[1]), (c[0], c[1] + 8), (c[0] - 8, c[1])]
            pygame.draw.polygon(surf, CYAN if i < done else (40, 50, 90), pts)
            pygame.draw.polygon(surf, (120, 150, 210), pts, 2)
        bx = x0 + n * 30 + 6
        pygame.draw.circle(surf, RED if game.phase == "warning" else (90, 30, 40), (bx, 50), 10)
        pygame.draw.circle(surf, (255, 140, 150), (bx, 50), 10, 2)

    def draw_banner(self, surf, game):
        if game.banner_timer <= 0:
            return
        t = LEVELUP_BANNER_TIME - game.banner_timer
        if t < 0.3:
            scale = 0.3 + 0.8 * (1 - (1 - t / 0.3) ** 3)
        else:
            scale = 1.1 - 0.1 * min(1.0, (t - 0.3) / 0.3)
        alpha = 255 if game.banner_timer > 0.6 else int(255 * game.banner_timer / 0.6)
        cx, cy = WIDTH // 2, 330
        draw_glow(surf, (cx, cy), 260 * scale, shade(MAGENTA, alpha / 255 * 0.45))
        img = pygame.transform.rotozoom(self.f_big.render("LEVEL UP!", True, YELLOW), 0, scale)
        img.set_alpha(alpha)
        surf.blit(img, img.get_rect(center=(cx, cy)))
        sub = self.f_hud.render(f"Level {game.level}  -  {weapon_name(game.level)}", True, WHITE)
        sub.set_alpha(alpha)
        surf.blit(sub, sub.get_rect(center=(cx, cy + 70)))
        if game.banner_note:
            note = self.f_med.render(game.banner_note, True, MAGENTA)
            note.set_alpha(alpha)
            surf.blit(note, note.get_rect(center=(cx, cy + 125)))

    def draw_message(self, surf, game):
        """Schwarm-/Boss-Meldungen in der Bildschirmmitte."""
        m = game.message
        if m is None or m["t"] <= 0:
            return
        age = m["dur"] - m["t"]
        alpha = min(1.0, age / 0.2, m["t"] / 0.4)
        if m["warning"] and int(age * 5) % 2 == 1:
            return                                      # Warnung blinkt
        cy = 520
        img = m["font"].render(m["text"], True, m["color"])
        img.set_alpha(int(255 * alpha))
        surf.blit(img, img.get_rect(center=(WIDTH // 2, cy)))
        if m["sub"]:
            sub = self.f_hud.render(m["sub"], True, WHITE)
            sub.set_alpha(int(255 * alpha))
            surf.blit(sub, sub.get_rect(center=(WIDTH // 2, cy + 56)))

    # --- Bildschirme ---------------------------------------------------------------
    def draw_menu(self, surf, game, mouse_pos):
        self.text(surf, "GALAXY", self.f_huge, CYAN, (WIDTH // 2, 170), "center", glow=True)
        self.text(surf, "SHOOTER", self.f_big, MAGENTA, (WIDTH // 2, 278), "center", glow=True)
        # Schiff-Stufen-Vorschau: zeigt, wie dein Schiff mitwächst
        tier = int(game.time / 1.6) % len(game.menu_ships)
        ship = game.menu_ships[tier]
        bob = math.sin(game.time * 2) * 10
        draw_glow(surf, (WIDTH // 2, 470), 130, (20, 50, 100))
        surf.blit(ship, ship.get_rect(center=(WIDTH // 2, int(470 + bob))))
        self.text(surf, f"Schiff-Stufe {tier + 1}/{len(game.menu_ships)}", self.f_tiny, GRAY,
                  (WIDTH // 2, 580), "center")
        for b in self.menu_buttons:
            self.draw_button(surf, b, mouse_pos)
        if int(game.time * 2) % 2 == 0:
            self.text(surf, "oder LEERTASTE", self.f_small, GRAY, (WIDTH // 2, 752), "center")
        self.text(surf, f"HIGHSCORE  {fmt(game.highscore)}", self.f_hud, YELLOW, (WIDTH // 2, 810), "center", glow=True)
        lines = ["Maus oder WASD / Pfeiltasten steuern  |  Schießen geht automatisch",
                 "P / ESC Pause  |  M Ton an/aus  |  Besiege Schwärme, dann kommt der Boss"]
        for i, ln in enumerate(lines):
            self.text(surf, ln, self.f_small, GRAY, (WIDTH // 2, HEIGHT - 80 + i * 30), "center")

    def draw_pause(self, surf, mouse_pos):
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 12, 175))
        surf.blit(dim, (0, 0))
        self.text(surf, "PAUSE", self.f_big, CYAN, (WIDTH // 2, 290), "center", glow=True)
        for b in self.pause_buttons:
            self.draw_button(surf, b, mouse_pos)
        self.text(surf, "P / ESC = weiter  |  M = Ton", self.f_small, GRAY, (WIDTH // 2, 730), "center")

    def draw_game_over(self, surf, game, mouse_pos):
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((14, 0, 6, 195))
        surf.blit(dim, (0, 0))
        cx = WIDTH // 2
        self.text(surf, "GAME OVER", self.f_big, RED, (cx, 200), "center", glow=True)
        panel = pygame.Rect(cx - 240, 290, 480, 400)
        pygame.draw.rect(surf, PANEL, panel, border_radius=20)
        pygame.draw.rect(surf, (90, 110, 170), panel, 2, border_radius=20)
        self.text(surf, "SCORE", self.f_small, GRAY, (cx, 322), "center")
        self.text(surf, fmt(game.score), self.f_title, WHITE, (cx, 368), "center", glow=True)
        stats = [("LEVEL", str(game.level), CYAN), ("SCHWÄRME", str(game.swarms_cleared), GREEN),
                 ("BOSSE", str(game.bosses_defeated), MAGENTA)]
        for i, (lab, val, col) in enumerate(stats):
            sx = cx - 150 + i * 150
            self.text(surf, lab, self.f_tiny, GRAY, (sx, 440), "center")
            self.text(surf, val, self.f_med, col, (sx, 476), "center", glow=True)
        self.text(surf, "HIGHSCORE", self.f_small, GRAY, (cx, 545), "center")
        self.text(surf, fmt(game.highscore), self.f_med, YELLOW, (cx, 582), "center", glow=True)
        if game.new_highscore and int(game.time * 3) % 2 == 0:
            self.text(surf, "NEUER HIGHSCORE!", self.f_hud, YELLOW, (cx, 650), "center", glow=True)
        for b in self.over_buttons:
            self.draw_button(surf, b, mouse_pos)
        self.text(surf, "oder LEERTASTE", self.f_small, GRAY, (cx, 935), "center")


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
        self.canvas = pygame.Surface((WIDTH, HEIGHT)).convert()
        self.flash_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.stars = Starfield()
        self.sounds = SoundBank()
        self.ui = UI()
        self.player = Player()
        self.menu_ships = [pygame.transform.smoothscale(s, (int(s.get_width() * 1.6),) * 2)
                           for s in self.player.sprites.values()]
        for kind in ENEMY_DRAWERS:                      # Sprites vorab bauen (kein Ruckeln im Spiel)
            enemy_base(kind)
        self.highscore = load_highscore()
        self.running = True
        self.time = 0.0
        self.state = "menu"                # menu | playing | paused | gameover
        self.state_time = 0.0
        self.cursor_visible = True
        self.reset_run()

    # --- Zustand --------------------------------------------------------------
    def reset_run(self):
        self.player.reset()
        self.enemies, self.bullets, self.enemy_bullets = [], [], []
        self.particles, self.popups = [], []
        self.score = 0
        self.level = 1
        self.kills_in_level = 0
        self.bar_display = 0.0
        self.shake = 0.0
        self.flash = (0.0, WHITE, 1.0)
        self.banner_timer = 0.0
        self.banner_note = ""
        self.message = None
        self.death_timer = 0.0
        self.new_highscore = False
        self.combo = 0
        self.combo_timer = 0.0
        # Director (Schwarm/Boss-Ablauf)
        self.phase = "intro"               # intro | swarm | break | warning | boss
        self.phase_timer = 1.4
        self.formation = None
        self.boss = None
        self.boss_bar_display = 1.0
        self.swarm_number = 0
        self.swarms_since_boss = 0
        self.swarms_cleared = 0
        self.bosses_defeated = 0
        self.asteroid_timer = ASTEROID_INTERVAL_BASE

    def set_state(self, state):
        self.state = state
        self.state_time = 0.0

    def start_game(self):
        self.reset_run()
        self.set_state("playing")
        self.show_message("BEREIT?", "Der erste Schwarm kommt ...", CYAN, 1.4)
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

    def show_message(self, text, sub, color, dur, warning=False, big=False):
        font = self.ui.f_big if big else self.ui.f_title
        self.message = dict(text=text, sub=sub, color=color, t=dur, dur=dur, warning=warning, font=font)

    # --- Eingaben -------------------------------------------------------------
    def handle_event(self, e):
        focus_lost = getattr(pygame, "WINDOWFOCUSLOST", None)
        if e.type == pygame.QUIT:
            self.running = False
        elif focus_lost is not None and e.type == focus_lost and self.state == "playing":
            self.set_state("paused")
        elif e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_ESCAPE, pygame.K_p):
                if self.state in ("playing", "paused"):
                    self.toggle_pause()
                elif self.state == "menu" and e.key == pygame.K_ESCAPE:
                    self.running = False
            elif e.key == pygame.K_m:
                self.sounds.muted = not self.sounds.muted
            elif e.key in (pygame.K_SPACE, pygame.K_RETURN):
                if self.state == "menu" or (self.state == "gameover" and self.state_time > 0.5):
                    self.start_game()
        elif e.type == pygame.MOUSEMOTION:
            self.player.control = "mouse"
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.handle_click(e.pos)

    def handle_click(self, pos):
        ui = self.ui
        action = None
        if self.state == "menu":
            action = ui.hit(ui.menu_buttons, pos)
        elif self.state == "gameover" and self.state_time > 0.5:
            action = ui.hit(ui.over_buttons, pos)
        elif self.state == "paused":
            action = ui.hit(ui.pause_buttons, pos)
            if action is None and ui.pause_rect.collidepoint(pos):
                action = "resume"
        elif self.state == "playing" and ui.pause_rect.collidepoint(pos):
            action = "pause"
        if action in ("start", "restart"):
            self.start_game()
        elif action == "resume":
            self.sounds.play("click")
            self.set_state("playing")
        elif action == "pause":
            self.sounds.play("click")
            self.set_state("paused")
        elif action == "menu":
            self.sounds.play("click")
            self.reset_run()
            self.set_state("menu")
        elif action == "quit":
            self.running = False

    # --- Effekte --------------------------------------------------------------
    def add_shake(self, amount):
        self.shake = min(SHAKE_MAX, self.shake + amount)

    def add_flash(self, color, duration):
        self.flash = (duration, color, duration)

    def add_particle(self, p):
        if len(self.particles) < MAX_PARTICLES:
            self.particles.append(p)

    def add_popup(self, pos, text, color):
        if len(self.popups) < 30:
            self.popups.append(FloatText(pos, self.ui.f_small.render(text, True, color)))

    def explode(self, pos, color, count=26, speed=320, size=5, ring=True):
        for _ in range(count):
            a = random.uniform(0, math.tau)
            v = Vector2(math.cos(a), math.sin(a)) * random.uniform(speed * 0.2, speed)
            col = random.choice([color, color, WHITE, YELLOW])
            self.add_particle(Particle(pos, v, random.uniform(0.35, 0.8), col, random.uniform(size * 0.6, size * 1.4)))
        if ring:
            self.add_particle(Particle(pos, (0, 0), 0.4, color, 6, ring=True, grow=size * 7))

    # --- Gegner-Hilfen --------------------------------------------------------
    def aim_from(self, pos):
        if self.player.alive:
            d = self.player.pos - Vector2(pos)
            if d.length_squared() > 1:
                return d.normalize()
        return Vector2(0, 1)

    def fire_enemy_bullet(self, pos, direction, speed, style="orb"):
        if len(self.enemy_bullets) < MAX_ENEMY_BULLETS:
            self.enemy_bullets.append(EnemyBullet(pos, direction, speed, style))

    def enemy_shoot(self, e):
        cfg = ENEMY_FIRE[e.kind]
        pattern = cfg["pattern"]
        if e.kind == "grunt" and self.level >= 6:
            pattern = "aimed"
        aim = Vector2(0, 1) if pattern == "straight" else self.aim_from(e.pos)
        angles = ([-18, 0, 18] if self.level < 8 else [-36, -18, 0, 18, 36]) if pattern == "spread" else [0]
        speed = ENEMY_BULLET_SPEED * min(ENEMY_BULLET_SPEED_CAP, 1 + ENEMY_BULLET_SPEED_PER_LEVEL * (self.level - 1))
        for a in angles:
            self.fire_enemy_bullet(e.pos + Vector2(0, e.size * 0.3), aim.rotate(a), speed)
        rate = min(ENEMY_FIRE_RATE_CAP, 1 + ENEMY_FIRE_RATE_PER_LEVEL * (self.level - 1))
        e.fire_cd = cfg["cooldown"] / rate * random.uniform(0.8, 1.3)

    # --- Schwärme ---------------------------------------------------------------
    def start_swarm(self):
        lv = self.level
        self.swarm_number += 1
        rows = min(2 + (lv - 1) // 3, 4)
        cols = min(5 + (lv - 1) // 2, 8)
        unlocked = [k for k in ("grunt", "scout", "zigzag", "tank") if lv >= ENEMY_TYPES[k]["unlock"]]
        row_choices = [("grunt", "scout"), ("grunt", "zigzag"), ("zigzag", "tank"), ("tank", "zigzag")]
        slots, kinds = [], []
        for r in range(rows):                           # Reihe 0 = vorderste (unten)
            options = [k for k in row_choices[r] if k in unlocked] or ["grunt"]
            kind = random.choice(options)
            step = 2 if kind == "tank" else 1
            for c in range(0, cols, step):
                slots.append(((c - (cols - 1) / 2) * SLOT_DX, (rows - 1 - r) * SLOT_DY))
                kinds.append(kind)
        f = Formation(slots)
        name = random.choice(list(ENTRY_PATHS))
        paths = (entry_path(name, False), entry_path(name, True))
        groups = ([], [])
        for i, (ox, _) in enumerate(slots):
            groups[0 if ox < 0 or (ox == 0 and i % 2) else 1].append(i)
        speed_mult = min(ENEMY_SPEED_CAP, 1 + ENEMY_SPEED_PER_LEVEL * (lv - 1))
        for g, idxs in enumerate(groups):               # zwei gespiegelte Ketten fliegen ein
            for n, i in enumerate(idxs):
                e = Enemy(kinds[i], lv)
                e.formation, e.slot = f, i
                e.follow(paths[g], SWARM_ENTRY_SPEED * speed_mult, "wait")
                e.delay = n * SWARM_ENTRY_GAP
                f.members.append(e)
                self.enemies.append(e)
        self.formation = f
        self.phase = "swarm"
        left = SWARMS_PER_BOSS - self.swarms_since_boss
        sub = "Danach kommt der BOSS!" if left == 1 else f"Noch {left} Schwärme bis zum Boss"
        self.show_message(f"SCHWARM {self.swarm_number}", sub, CYAN, 1.8)

    def start_dive(self, e, from_top=False):
        px = self.player.pos.x if self.player.alive else WIDTH / 2
        speed = DIVE_SPEED * e.speed_mult * ENEMY_TYPES[e.kind]["dive"]
        clamp = lambda x: max(30, min(WIDTH - 30, x))
        if from_top:
            x = random.uniform(80, WIDTH - 80)
            e.pos = Vector2(x, -70)
            pts = [(x, -70), (x, 140), ((x + px) / 2, HEIGHT * 0.45), (px, HEIGHT * 0.78),
                   (clamp(px + random.uniform(-150, 150)), HEIGHT + 100)]
        else:
            p = Vector2(e.pos)
            out = -1 if p.x < WIDTH / 2 else 1          # erst nach außen ausholen (Galaga-Looping)
            pts = [p, p + Vector2(out * 60, -50), p + Vector2(out * 110, 20)]
            if e.kind == "zigzag":                      # Zickzack-Sturzflug
                for k, yf in enumerate((0.40, 0.55, 0.70)):
                    pts.append((clamp(px + (130 if k % 2 == 0 else -130)), HEIGHT * yf))
            elif e.kind == "scout":                     # direkt auf den Spieler
                pts.append((clamp(px), HEIGHT * 0.70))
            else:
                pts += [(clamp(p.x * 0.4 + px * 0.6), HEIGHT * 0.48), (clamp(px - out * 40), HEIGHT * 0.78)]
            pts.append((clamp(px - out * 160), HEIGHT + 100))
        e.follow(FlightPath(pts), speed, "dive")
        e.fire_cd = min(e.fire_cd, random.uniform(0.3, 0.9))

    def dive_finished(self, e):
        f = e.formation
        if f is None or f.leaving:
            e.removed = True
        elif f.released:
            self.start_dive(e, from_top=True)           # Nachzügler greifen immer wieder an
        else:
            e.pos = Vector2(f.slot_pos(e.slot).x, -70)  # von oben zurück auf den Platz
            e.state = "to_slot"

    def spawn_minions(self, boss):
        for side in (-1, 0, 1):
            e = Enemy("scout", self.level, boss.pos + Vector2(side * 100, 60))
            px = self.player.pos.x
            pts = [Vector2(e.pos), e.pos + Vector2(side * 120, 90), (px, HEIGHT * 0.7), (px, HEIGHT + 100)]
            e.follow(FlightPath(pts), DIVE_SPEED * e.speed_mult * 1.2, "dive")
            self.enemies.append(e)

    def spawn_asteroid(self):
        e = Enemy("asteroid", self.level, (random.uniform(80, WIDTH - 80), -60))
        self.enemies.append(e)

    def update_director(self, dt):
        self.phase_timer -= dt
        if self.phase in ("intro", "break"):
            if self.phase_timer <= 0:
                self.start_swarm()
        elif self.phase == "swarm":
            self.update_formation(dt)
        elif self.phase == "warning":
            if self.phase_timer <= 0:
                self.boss = Boss(self.level, self.bosses_defeated)
                self.boss_bar_display = 1.0
                self.phase = "boss"
        elif self.phase == "boss":
            if self.boss.removed:
                self.boss_defeated()
        if self.phase in ("swarm", "break"):
            self.asteroid_timer -= dt
            if self.asteroid_timer <= 0:
                self.spawn_asteroid()
                self.asteroid_timer = max(ASTEROID_INTERVAL_MIN, ASTEROID_INTERVAL_BASE
                                          - ASTEROID_INTERVAL_DECAY * (self.level - 1)) * random.uniform(0.8, 1.3)

    def update_formation(self, dt):
        f = self.formation
        f.t += dt
        f.members = [e for e in f.members if not e.dead and not e.removed]
        alive = f.members
        if not alive:
            self.swarm_cleared(f)
            return
        if not any(e.state in ("wait", "enter") for e in alive):
            f.settled_time += dt
        if f.released:
            f.release_time += dt
            if f.release_time > STRAGGLER_TIMEOUT and not f.leaving:
                f.leaving = True
                for e in alive:
                    if e.state != "dive":
                        e.state = "leave"
            return
        if f.settled_time > 0.5 and len(alive) <= STRAGGLER_COUNT < f.total:
            f.released = True
            for e in alive:
                if e.state in ("formation", "to_slot"):
                    self.start_dive(e)
            return
        if f.settled_time > 1.2:
            f.dive_timer -= dt
            if f.dive_timer <= 0:
                cands = [e for e in alive if e.state == "formation" and e.kind != "tank"]
                k = 1 + (self.level >= 5) + (self.level >= 10)
                for e in random.sample(cands, min(k, len(cands))):
                    self.start_dive(e)
                f.dive_timer = max(DIVE_INTERVAL_MIN, DIVE_INTERVAL_BASE
                                   - DIVE_INTERVAL_DECAY * (self.level - 1)) * random.uniform(0.8, 1.2)

    def swarm_cleared(self, f):
        self.formation = None
        self.swarms_cleared += 1
        self.swarms_since_boss += 1
        bonus = 25 * f.total * self.level
        self.score += bonus
        self.sounds.play("bonus")
        if self.swarms_since_boss >= SWARMS_PER_BOSS:
            self.phase = "warning"
            self.phase_timer = BOSS_WARNING_TIME
            self.enemy_bullets.clear()
            self.show_message("WARNUNG!", "Ein Boss nähert sich", RED, BOSS_WARNING_TIME, warning=True, big=True)
            self.sounds.play("alarm")
        else:
            self.phase = "break"
            self.phase_timer = SWARM_BREAK
            self.show_message("SCHWARM BESIEGT!", f"+{fmt(bonus)} Bonus", GREEN, SWARM_BREAK)

    def boss_defeated(self):
        b = self.boss
        for col, n, sp in ((ORANGE, 90, 650), (YELLOW, 60, 480), (MAGENTA, 50, 380)):
            self.explode(b.pos, col, count=n, speed=sp, size=8)
        self.add_flash(WHITE, 0.6)
        self.add_shake(SHAKE_MAX)
        self.boss = None
        self.bosses_defeated += 1
        self.swarms_since_boss = 0
        extra = self.player.lives < PLAYER_MAX_LIVES
        if extra:
            self.player.lives += 1
        self.phase = "break"
        self.phase_timer = 3.0
        self.show_message("BOSS BESIEGT!", "+1 Leben" if extra else "Maximale Leben erreicht", YELLOW, 3.0, big=True)
        self.sounds.play("bonus")

    # --- Spielregeln ----------------------------------------------------------
    def combo_mult(self):
        return min(COMBO_MAX, 1 + self.combo // COMBO_STEP)

    def add_kills(self, n):
        self.kills_in_level += n
        while self.kills_in_level >= kills_needed(self.level):
            self.kills_in_level -= kills_needed(self.level)
            self.level_up()

    def kill_enemy(self, e):
        e.dead = True
        self.combo += 1
        self.combo_timer = COMBO_WINDOW
        diving = e.state == "dive"
        pts = e.points * (2 if diving else 1) * self.combo_mult()
        self.score += pts
        self.add_popup(e.pos, f"+{pts}", YELLOW if diving or self.combo_mult() > 1 else WHITE)
        color = (255, 170, 190) if e.kind == "asteroid" else ORANGE
        self.explode(e.pos, color, count=14 + int(e.size / 4), size=3 + e.size / 25)
        self.add_shake(3 + e.size / 20)
        self.sounds.play("explode")
        self.add_kills(1)

    def damage_boss(self, b, dmg, pos):
        b.hp -= dmg
        if b.hit_flash < -0.07:                         # Aufblitzen gedrosselt (sonst dauerweiß)
            b.hit_flash = 0.05
        if b.hp <= 0 and b.state == "fight":
            b.hp = 0
            b.start_dying()
            self.enemy_bullets.clear()
            pts = BOSS_POINTS * (b.number + 1) * self.combo_mult()
            self.score += pts
            self.add_popup(b.pos, f"+{fmt(pts)}", YELLOW)
            self.sounds.play("boom")
            self.add_kills(BOSS_KILL_VALUE)
            for e in self.enemies:                      # Begleiter fliehen mit dem Boss
                if e.kind == "scout" and e.formation is None:
                    e.removed = True

    def level_up(self):
        self.level += 1
        self.banner_timer = LEVELUP_BANNER_TIME
        self.banner_note = ""
        self.add_flash(WHITE, 0.45)
        self.add_shake(10)
        self.sounds.play("levelup")
        tier = player_tier(self.level)
        if tier != self.player.tier:
            self.player.set_tier(tier)
            self.banner_note = "SCHIFF-UPGRADE!"
            self.add_shake(16)
            self.explode(self.player.pos, MAGENTA, count=60, speed=560, size=7)
        for r, g in ((8, 90), (6, 160), (4, 240)):
            self.add_particle(Particle(self.player.pos, (0, 0), 0.7, CYAN, r, ring=True, grow=g * 2))
        self.explode(self.player.pos, YELLOW, count=40, speed=500, ring=False)

    def hurt_player(self, pos, enemy=None):
        p = self.player
        p.lives -= 1
        p.invuln = INVULN_TIME
        self.combo = 0
        if enemy is not None:
            enemy.dead = True
        self.enemy_bullets.clear()
        self.explode(pos, ORANGE, count=24)
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
        targets = [e for e in self.enemies if e.active and not e.dead and e.pos.y > -e.radius]
        boss = self.boss if self.boss is not None and self.boss.vulnerable else None
        for b in self.bullets:
            for e in targets:
                if e.dead or e in b.hit:
                    continue
                rr = b.radius + e.radius
                if abs(b.pos.y - e.pos.y) > rr or abs(b.pos.x - e.pos.x) > rr:
                    continue                            # schneller Vorab-Test
                if (b.pos - e.pos).length_squared() <= rr * rr:
                    b.hit.add(e)
                    e.hp -= b.damage
                    e.hit_flash = 0.08
                    self.add_particle(Particle(b.pos, (random.uniform(-120, 120), random.uniform(-220, -40)),
                                               0.25, b.color, 3))
                    if e.hp <= 0:
                        self.kill_enemy(e)
                    if not b.pierce:
                        b.alive = False
                        break
            if boss is not None and b.alive and boss not in b.hit:
                for hx, hy, hr in boss.hitboxes():
                    if (b.pos.x - hx) ** 2 + (b.pos.y - hy) ** 2 <= (hr + b.radius) ** 2:
                        b.hit.add(boss)
                        self.add_particle(Particle(b.pos, (random.uniform(-150, 150), -120), 0.25, b.color, 3))
                        self.damage_boss(boss, b.damage, b.pos)
                        if not b.pierce:
                            b.alive = False
                        break
        p = self.player
        if not p.alive or p.invuln > 0:
            return
        for e in targets:
            if not e.dead and (e.pos - p.pos).length_squared() <= (e.radius + p.hit_radius) ** 2:
                self.hurt_player(e.pos, e)
                return
        if boss is not None:
            for hx, hy, hr in boss.hitboxes():
                if (p.pos.x - hx) ** 2 + (p.pos.y - hy) ** 2 <= (hr + p.hit_radius) ** 2:
                    self.hurt_player(p.pos)
                    return
        for b in self.enemy_bullets:
            if (b.pos - p.pos).length_squared() <= (b.radius + p.hit_radius) ** 2:
                self.hurt_player(b.pos)
                return

    # --- Update ---------------------------------------------------------------
    def update(self, dt):
        self.time += dt
        self.state_time += dt
        self.update_cursor()
        if self.state == "paused":
            return
        self.stars.update(dt)
        if self.state == "menu":
            return
        if self.state == "playing":
            self.update_playing(dt)
        else:
            self.update_world_effects(dt)

    def update_cursor(self):
        """Mauszeiger im Spiel ausblenden, wenn das Schiff der Maus folgt."""
        want = not (self.state == "playing" and self.player.control == "mouse"
                    and not self.ui.pause_rect.collidepoint(pygame.mouse.get_pos()))
        if want != self.cursor_visible:
            pygame.mouse.set_visible(want)
            self.cursor_visible = want

    def update_world_effects(self, dt):
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.life > 0]
        for p in self.popups:
            p.update(dt)
        self.popups = [p for p in self.popups if p.life > 0]
        self.shake = max(0.0, self.shake - SHAKE_DECAY * dt)
        t, col, total = self.flash
        self.flash = (max(0.0, t - dt), col, total)
        self.banner_timer = max(0.0, self.banner_timer - dt)
        if self.message is not None:
            self.message["t"] -= dt
        target = self.kills_in_level / kills_needed(self.level)
        self.bar_display += (target - self.bar_display) * (1 - math.exp(-8 * dt))
        if self.boss is not None:
            r = max(0, self.boss.hp) / self.boss.max_hp
            self.boss_bar_display += (r - self.boss_bar_display) * (1 - math.exp(-3 * dt))

    def update_playing(self, dt):
        p = self.player
        if p.alive:
            mouse_pos = pygame.mouse.get_pos()
            mouse_ok = pygame.mouse.get_focused() and not self.ui.pause_rect.collidepoint(mouse_pos)
            p.update(dt, pygame.key.get_pressed(), mouse_pos, mouse_ok)
            p.cooldown -= dt
            if p.cooldown <= 0:
                new, cooldown = p.fire(self.level)
                self.bullets.extend(new)
                p.cooldown = cooldown
                self.sounds.play("shoot")
        else:
            self.death_timer += dt
            if self.death_timer >= GAME_OVER_DELAY:
                self.end_game()
        if self.combo_timer > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self.combo = 0

        self.update_director(dt)
        if self.boss is not None:
            self.boss.update(dt, self)
        for b in self.bullets:
            b.update(dt)
        for b in self.enemy_bullets:
            b.update(dt)
        for e in self.enemies:
            if not e.update(dt, self):
                e.removed = True
        if p.alive:
            for e in self.enemies:
                cfg = ENEMY_FIRE.get(e.kind)
                if cfg and self.level >= cfg["unlock"] and e.state in ("formation", "dive", "to_slot"):
                    e.fire_cd -= dt
                    if e.fire_cd <= 0 and 30 < e.pos.y < HEIGHT * 0.7:
                        self.enemy_shoot(e)
        self.handle_collisions()
        self.bullets = [b for b in self.bullets if b.alive]
        self.enemy_bullets = [b for b in self.enemy_bullets if b.alive]
        self.enemies = [e for e in self.enemies if not e.dead and not e.removed]
        self.update_world_effects(dt)

    # --- Zeichnen ---------------------------------------------------------------
    def draw_world(self):
        c = self.canvas
        self.stars.draw(c)
        if self.boss is not None:
            self.boss.draw(c)
        for e in self.enemies:
            e.draw(c)
        for b in self.bullets:
            b.draw(c)
        if self.player.alive and self.state != "menu":
            self.player.draw(c)
        for b in self.enemy_bullets:
            b.draw(c)
        for p in self.particles:
            p.draw(c)
        for p in self.popups:
            p.draw(c)

    def draw(self):
        mouse_pos = pygame.mouse.get_pos()
        self.draw_world()
        ox = oy = 0
        if self.shake > 0.5:
            ox = int(random.uniform(-self.shake, self.shake))
            oy = int(random.uniform(-self.shake, self.shake))
            self.screen.fill((0, 0, 0))
        self.screen.blit(self.canvas, (ox, oy))

        t, col, total = self.flash
        if t > 0:
            self.flash_surf.fill((*col, int(150 * t / total)))
            self.screen.blit(self.flash_surf, (0, 0))
        if self.state != "menu" and self.player.alive and self.player.lives == 1:
            self.ui.vignette.set_alpha(int(110 + 90 * math.sin(self.time * 5)))
            self.screen.blit(self.ui.vignette, (0, 0))   # Warnung: letztes Leben

        if self.state == "menu":
            self.ui.draw_menu(self.screen, self, mouse_pos)
        else:
            self.ui.draw_hud(self.screen, self, mouse_pos)
            if self.state != "gameover":
                self.ui.draw_message(self.screen, self)
                self.ui.draw_banner(self.screen, self)
            if self.state == "paused":
                self.ui.draw_pause(self.screen, mouse_pos)
            elif self.state == "gameover":
                self.ui.draw_game_over(self.screen, self, mouse_pos)
        pygame.display.flip()

    # --- Hauptschleife ----------------------------------------------------------
    def run(self):
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
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
