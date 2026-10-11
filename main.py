import math
import random
import os
import json
import gc

gc.set_threshold(30000, 30, 30)    # far fewer collector pauses while playing

from kivy.config import Config
Config.set('graphics', 'multisamples', '0')
Config.set('graphics', 'maxfps', '0')   # no Kivy cap: the game schedules itself at the chosen FPS

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.text import Label as CoreLabel
from kivy.graphics import (Canvas, Color, Rectangle, Ellipse, Line, Triangle, Quad,
                           PushMatrix, PopMatrix, Rotate, Scale, Translate,
                           Fbo, ClearColor, ClearBuffers)
from kivy.graphics.texture import Texture
from kivy.uix.widget import Widget

VH = 720.0
GRAV = -1550.0
JUMP = 652.8            # +2 %
RUN0, RUN_MAX = 360.0, 560.0
MAX_CARRY = 820.0
MAX_SWING = 850.0
HW = 17.0  # Increased player size (non-customizable)
CLIMB = 270.0
STREET = 36.0
TILE = 64.0
HMIN, HMAX = 130.0, 470.0

SWING_REACH_X = 520.0
SWING_REACH_D = 560.0
ZIP_DIST = 430.0      # length of the straight-line air zip
ZIP_V0, ZIP_VMAX = 700.0, 1500.0
DETAIL = 2
QUALITY_ORDER = ('low', 'medium', 'high')
# bake  = texture resolution of baked buildings (x screen scale, capped)
# blur  = poster blur (poster is painted at 1/blur size and scaled back up)
# post  = poster density, fx = max particles, sky = far flyers (0 none, 1 plane, 2 all)
# amb   = which animated roof / window effects are drawn, lay = far skyline texture scale
QUALITY = {
    'low': dict(bake=0.5, blur=6.0, stars=0, clouds=0, post=0.25, fx=40, sky=0,
                amb=('beacon', 'neon'), animals=False, swfx=False, lay=0.3, lwin=False),
    'medium': dict(bake=0.8, blur=5.0, stars=30, clouds=3, post=0.7, fx=90, sky=1,
                   amb=('beacon', 'neon', 'tv', 'glow', 'fan', 'lights'),
                   animals=False, swfx=True, lay=0.45, lwin=True),
    'high': dict(bake=1.0, blur=4.5, stars=55, clouds=5, post=1.0, fx=150, sky=2,
                 amb=('beacon', 'neon', 'tv', 'glow', 'fan', 'lights', 'smoke'),
                 animals=True, swfx=True, lay=0.6, lwin=True),
}
FPS_OPTIONS = (25, 30, 45, 60, 90, 120)
MAX_STEP = 1.0 / 50.0     # physics sub-step: game speed never depends on the frame rate
POSTER_BLUR = 4.5         # default; the quality level picks the real value (blurrier posters)
POSTER_PAD = 6.0

RED = (0.88, 0.09, 0.11, 1)
RED2 = (0.6, 0.05, 0.09, 1)
BLUE = (0.08, 0.2, 0.65, 1)  # Classic suit blue tone
DARK = (0.12, 0.1, 0.16, 1)
SUIT_RED = (0.88, 0.06, 0.09, 1)
SUIT_RED_D = (0.58, 0.04, 0.07, 1)
SUIT_DK = (0.07, 0.07, 0.10, 1)       # black legs / waist
SUIT_DK_D = (0.04, 0.04, 0.06, 1)
SUIT_NAVY = (0.11, 0.15, 0.30, 1)     # navy shoulders / upper arms
SUIT_NAVY_D = (0.07, 0.09, 0.19, 1)
SUIT_WHITE = (0.94, 0.94, 0.98, 1)

WARM = [(1.0, 0.74, 0.3), (1.0, 0.84, 0.5), (0.95, 0.62, 0.25), (1.0, 0.9, 0.65)]
NEON_COLS = [(1.0, 0.2, 0.7), (0.2, 0.95, 1.0), (0.6, 1.0, 0.3), (1.0, 0.6, 0.15), (0.7, 0.4, 1.0)]
SIGN_WORDS = ['BAR', 'HOTEL', 'PIZZA', 'CAFE', 'CLUB', 'OPEN', 'SUSHI', 'TACOS',
              'MOTEL', 'DINER', 'JAZZ', 'ARCADE', 'NOODLE', 'LIVE']
BOARD_WORDS = ['EAT', 'BUY', 'GO', 'FUN', 'COLA', 'PIZZA', 'WEB', 'NEW', 'WIN']
POSTER_WORDS = {'gig': ['LIVE', 'JAZZ', 'ROCK', 'DJ', 'TOUR'],
                'movie': ['HERO', 'NIGHT', 'NEON', 'CITY', 'RUN'],
                'sale': ['SALE', '50%', 'OPEN', 'NEW!'],
                'wanted': ['WANTED'],
                'web': ['WEB', 'RUNNER'],
                'flyers': ['LOST', 'BAND', 'FREE']}

STYLE = {
    'brick':      ('brick',    (1.0, 1.0, 1.08),   (0.70, 0.09, 0.12), (0.95, 0.30, 0.26)),
    'glass':      ('glass',    (1.0, 1.0, 1.0),    (0.12, 0.35, 0.50), (0.45, 0.85, 0.95)),
    'concrete':   ('concrete', (1.0, 1.0, 1.05),   (0.24, 0.24, 0.30), (0.62, 0.63, 0.70)),
    'deco':       ('sand',     (1.0, 0.95, 0.9),   (0.55, 0.40, 0.15), (0.95, 0.80, 0.40)),
    'industrial': ('metal',    (1.0, 1.0, 1.05),   (0.22, 0.22, 0.28), (0.95, 0.75, 0.15)),
    'apartment':  ('stucco',   (1.0, 0.95, 0.95),  (0.42, 0.20, 0.20), (0.90, 0.55, 0.40)),
    'neon':       ('dark',     (1.0, 1.0, 1.1),    (0.10, 0.08, 0.18), (0.90, 0.20, 0.80)),
    'loft':       ('brick',    (1.18, 0.88, 0.78), (0.30, 0.12, 0.12), (0.80, 0.45, 0.35)),
    'ribbon':     ('concrete', (0.88, 1.0, 1.15),  (0.14, 0.16, 0.22), (0.45, 0.75, 0.95)),
}

PALS = [((0.82, 0.84, 0.92), (0.55, 0.58, 0.74), (0.90, 0.30, 0.30)),
        ((0.95, 0.85, 0.50), (0.75, 0.60, 0.30), (0.20, 0.30, 0.60)),
        ((0.55, 0.80, 0.85), (0.30, 0.50, 0.60), (0.95, 0.50, 0.20)),
        ((0.90, 0.55, 0.75), (0.65, 0.35, 0.55), (0.20, 0.20, 0.40))]
SWING_KINDS = (('blimp', 24), ('balloon', 24), ('heli', 20), ('drone', 20), ('ufo', 12))


def lerp(a, b, t):
    return a + (b - a) * t


def C(c, a=1.0):
    return (c[0], c[1], c[2], a)


def shade(c, k):
    return (c[0] * k, c[1] * k, c[2] * k, c[3] if len(c) > 3 else 1.0)


def _pose(**kw):
    d = dict(f1x=-5.0, f1y=2.0, f2x=6.0, f2y=2.0, h1x=9.0, h1y=24.0,
             h2x=-6.0, h2y=22.0, lean=1.0, sq=1.0)
    d.update(kw)
    return d


POSE_BLEND = {'zip': 0.07, 'swing': 0.11, 'run': 0.09, 'climb': 0.10, 'wall': 0.10,
              'tuck': 0.07, 'air_up': 0.08, 'air_fall': 0.10}


def force_landscape():
    for cls in ('org.kivy.android.PythonActivity',
                'org.renpy.android.PythonSDLActivity'):
        try:
            from jnius import autoclass
            autoclass(cls).mActivity.setRequestedOrientation(0)
            return
        except Exception:
            pass


def make_sky():
    stops = [(0.0, (232, 122, 112)), (0.25, (150, 70, 150)),
             (0.55, (70, 40, 125)), (1.0, (12, 10, 42))]
    n = 64
    buf = bytearray()
    for i in range(n):
        t = i / (n - 1.0)
        col = [0, 0, 0]
        for k in range(len(stops) - 1):
            (t0, c0), (t1, c1) = stops[k], stops[k + 1]
            if t0 <= t <= t1:
                u = (t - t0) / (t1 - t0)
                col = [int(lerp(c0[j], c1[j], u)) for j in range(3)]
                break
        buf += bytes(col + [255])
    tex = Texture.create(size=(1, n), colorfmt='rgba')
    tex.blit_buffer(bytes(buf), colorfmt='rgba', bufferfmt='ubyte')
    return tex


def _tex(fn, seed, size=32):
    rnd = random.Random(seed)
    buf = bytearray()
    for y in range(size):
        for x in range(size):
            c = fn(x, y, rnd)
            buf += bytes((max(0, min(255, int(c[0]))), max(0, min(255, int(c[1]))),
                          max(0, min(255, int(c[2]))), 255))
    tex = Texture.create(size=(size, size), colorfmt='rgba')
    tex.blit_buffer(bytes(buf), colorfmt='rgba', bufferfmt='ubyte')
    tex.wrap = 'repeat'
    tex.mag_filter = 'nearest'
    return tex


def f_brick(x, y, rnd):
    row = y // 8
    off = 8 if row % 2 else 0
    if y % 8 == 0 or (x + off) % 16 == 0:
        return (30, 30, 38)
    base = 66 + ((row * 7 + (x + off) // 16 * 13) % 5) * 5 + rnd.randint(-4, 4)
    return (base, base - 2, base + 6)


def f_glass(x, y, rnd):
    if x % 8 == 0 or y % 8 == 0:
        return (14, 22, 36)
    k = 46 + y * 1.1 + rnd.randint(-3, 3)
    hi = 22 if (x + y) % 32 < 4 else 0
    return (k * 0.6 + hi, k * 0.95 + hi, k * 1.45 + hi)


def f_concrete(x, y, rnd):
    if y % 16 == 0:
        return (52, 52, 60)
    if x % 16 == 0 and (y // 16) % 2 == 0:
        return (60, 60, 68)
    v = 92 + rnd.randint(-7, 7) + (4 if (x // 4 + y // 4) % 5 == 0 else 0)
    return (v, v, v + 8)


def f_sand(x, y, rnd):
    if x % 8 == 0:
        return (88, 72, 50)
    v = 140 + rnd.randint(-8, 8) - (14 if y % 16 < 2 else 0)
    return (v, v * 0.88, v * 0.66)


def f_metal(x, y, rnd):
    v = (104, 108, 120) if x % 4 < 2 else (80, 84, 96)
    if y % 16 == 0 and x % 8 < 2:
        v = (50, 50, 58)
    n = rnd.randint(-4, 4)
    return (v[0] + n, v[1] + n, v[2] + n)


def f_stucco(x, y, rnd):
    v = 128 + rnd.randint(-10, 10)
    if (x * 7 + y * 13) % 41 == 0:
        v -= 28
    return (v, v * 0.74, v * 0.68)


def f_dark(x, y, rnd):
    v = 38 + rnd.randint(-3, 3)
    if y % 12 == 0 or (x + (6 if (y // 12) % 2 else 0)) % 12 == 0:
        v -= 10
    return (v, v - 2, v + 16)


def make_walls():
    return {'brick': _tex(f_brick, 5), 'glass': _tex(f_glass, 6), 'concrete': _tex(f_concrete, 7),
            'sand': _tex(f_sand, 8), 'metal': _tex(f_metal, 9), 'stucco': _tex(f_stucco, 10),
            'dark': _tex(f_dark, 11)}


def make_layer(rng, hmin, hmax, dots):
    items = []
    x = 0.0
    while x < 1900:
        w = rng.uniform(70, 150)
        h = rng.uniform(hmin, hmax)
        win = []
        if dots:
            for _ in range(int(w * h / 9000)):
                win.append((rng.uniform(8, w - 14), rng.uniform(14, h - 14)))
        items.append((x, w, h, win))
        x += w + rng.uniform(-10, 20)
    return items, x


class Bld:
    def __init__(self, x, w, h, rng, style='brick'):
        self.x, self.w, self.h = x, w, h
        self.style = style
        self.seed = rng.randint(1, 10 ** 9)
        self.tint = rng.uniform(0.78, 1.0)
        self.anim = []
        self.animals = []
        self.plain = False
        self.cv = None
        self.fbo = None
        self.visible = False


class Swing:
    def __init__(self, kind, x, y, rng):
        self.kind = kind
        self.bx, self.by = x, y
        self.ax, self.ay = x, y
        self.ph = rng.uniform(0, 6.283)
        self.rl = rng.choice((28.0, 38.0))   # two heights -> baked art is shared
        self.pal = rng.randint(0, 3)
        self.sx = rng.uniform(5, 14)
        self.sy = rng.uniform(3, 7)
        self.cv = None
        self.tr = None
        self.visible = False


class Player:
    def __init__(self):
        self.x, self.y = 120.0, 220.0
        self.vx = RUN0
        self.vy = 0.0
        self.mode = 'run'
        self.wall = None
        self.anchor = None
        self.L = 0.0
        self.coyote = 0.0
        self.cut = False
        self.rel_t = 0.0
        self.rel_anchor = None
        self.zip_target = None
        self.zip_t = 0.0
        self.flip = False
        self.rot = 0.0
        self.land_t = 0.0
        self.web_t = 9.0
        self.web_hit = True
        self.dust_t = 0.0
        self.wall_t = 0.0
        # animation state
        self.pose = None
        self.prev = None
        self.pose_name = ''
        self.tr = 0.0
        self.tr_len = 0.1
        self.ang = 0.0
        self.org = 20.0
        self.sq = 1.0
        self.cyc = 0.0


def ik2(sx, sy, tx, ty, l1, l2, bend):
    """Two-bone IK. Returns (joint_x, joint_y, end_x, end_y); end is clamped to reach."""
    dx, dy = tx - sx, ty - sy
    d = math.hypot(dx, dy)
    mx = l1 + l2 - 0.05
    if d > mx:
        k = mx / d
        dx, dy, d = dx * k, dy * k, mx
        tx, ty = sx + dx, sy + dy
    if d < 0.5:
        d = 0.5
    a = (l1 * l1 - l2 * l2 + d * d) / (2.0 * d)
    h = math.sqrt(max(0.0, l1 * l1 - a * a))
    ux, uy = dx / d, dy / d
    return sx + ux * a - uy * h * bend, sy + uy * a + ux * h * bend, tx, ty


class SpiderRig:
    """Spider-Man (red / black, navy sleeves, big white eye, black webbing) built ONCE as
    retained graphics instructions. Each frame only their numbers change."""
    LEG, ARM, HIP = 12.0, 10.0, 22.0

    def __init__(self, canvas):
        self.hand = (0.0, 40.0)
        with canvas:
            PushMatrix()
            self.hide = Translate(0, 0)
            self.rot = Rotate(angle=0, origin=(0, 0))
            # ---- far arm
            Color(*SUIT_NAVY_D)
            self.fa_u = Line(points=[0, 0, 0, 0], width=5.0, cap='round')
            Color(*SUIT_RED_D)
            self.fa_f = Line(points=[0, 0, 0, 0], width=4.4, cap='round')
            self.fa_h = Ellipse(pos=(0, 0), size=(6.2, 6.2))
            # ---- far leg
            Color(*SUIT_DK_D)
            self.fl_t = Line(points=[0, 0, 0, 0], width=7.0, cap='round')
            self.fl_s = Line(points=[0, 0, 0, 0], width=6.4, cap='round')
            Color(0.62, 0.62, 0.68, 1)
            self.fl_so = Ellipse(pos=(0, 0), size=(11, 4))
            Color(*SUIT_RED_D)
            self.fl_b = Line(points=[0, 0, 0, 0], width=6.6, cap='round')
            # ---- torso: black waist, red chest, navy shoulder yoke, red belt
            Color(*SUIT_DK)
            self.to_lo = Quad(points=[0] * 8)
            Color(*SUIT_RED)
            self.to_up = Quad(points=[0] * 8)
            Color(*SUIT_NAVY)
            self.to_sh = Quad(points=[0] * 8)
            Color(*SUIT_RED)
            self.belt = Line(points=[0, 0, 0, 0], width=2.4)
            Color(0.05, 0.03, 0.07, 1)
            self.tw_1 = Line(points=[0, 0, 0, 0], width=0.9)
            self.tw_2 = Line(points=[0, 0, 0, 0], width=0.9)
            self.tw_3 = Line(points=[0, 0, 0, 0], width=0.9)
            self.em_b = Ellipse(pos=(0, 0), size=(3.0, 5.4))      # black spider emblem
            self.em_1 = Line(points=[0] * 6, width=1.0)
            self.em_2 = Line(points=[0] * 6, width=1.0)
            # ---- head / mask (big head, one large slanted white lens, black web lines)
            Color(*SUIT_RED)
            self.head = Ellipse(pos=(0, 0), size=(16.4, 17.6))
            Color(0.05, 0.03, 0.07, 1)
            self.mk_1 = Line(points=[0] * 4, width=0.9)
            self.mk_2 = Line(points=[0] * 6, width=0.9)
            self.mk_3 = Line(points=[0] * 6, width=0.9)
            Color(1, 1, 1, 1)
            self.eye = Quad(points=[0] * 8)
            Color(0.05, 0.03, 0.07, 1)
            self.eye_o = Line(points=[0] * 8, width=1.0, close=True)
            # ---- near leg: black pants, red boots, white sole
            Color(*SUIT_DK)
            self.nl_t = Line(points=[0, 0, 0, 0], width=7.4, cap='round')
            self.nl_s = Line(points=[0, 0, 0, 0], width=6.6, cap='round')
            Color(*SUIT_WHITE)
            self.nl_so = Ellipse(pos=(0, 0), size=(11, 4))
            Color(*SUIT_RED)
            self.nl_b = Line(points=[0, 0, 0, 0], width=7.0, cap='round')
            # ---- near arm: navy sleeve, red forearm, red fist
            Color(*SUIT_NAVY)
            self.na_u = Line(points=[0, 0, 0, 0], width=5.4, cap='round')
            Color(*SUIT_RED)
            self.na_f = Line(points=[0, 0, 0, 0], width=4.8, cap='round')
            self.na_h = Ellipse(pos=(0, 0), size=(6.8, 6.8))
            PopMatrix()

    def _leg(self, x, hy, tx, ty, t, s, so, b):
        kx, ky, ax, ay = ik2(x, hy, tx, ty, self.LEG, self.LEG, 1.0)
        t.points = [x, hy, kx, ky]
        s.points = [kx, ky, ax, ay]
        b.points = [kx + (ax - kx) * 0.45, ky + (ay - ky) * 0.45, ax, ay]
        so.pos = (ax - 3.4, ay - 3.8)

    def _arm(self, sx, sy, tx, ty, u, f, h):
        ex, ey, hx, hy = ik2(sx, sy, tx, ty, self.ARM, self.ARM, -1.0)
        u.points = [sx, sy, ex, ey]
        f.points = [ex, ey, hx, hy]
        h.pos = (hx - h.size[0] / 2.0, hy - h.size[1] / 2.0)
        return hx, hy

    def apply(self, x, y, po, ang, org, show):
        self.hide.y = 0.0 if show else -5000.0
        self.rot.angle = ang
        self.rot.origin = (x, y + org)
        lean = po['lean']
        hy = y + self.HIP * po['sq']
        shx, shy = x + lean * 0.85, hy + 16.0
        nx, ny = x + lean, hy + 18.0
        # far limbs
        self._leg(x, hy, x + po['f2x'], y + po['f2y'] + 2.8, self.fl_t, self.fl_s, self.fl_so, self.fl_b)
        self._arm(shx - 1.5, shy - 1.0, x + po['h2x'], y + po['h2y'], self.fa_u, self.fa_f, self.fa_h)
        # torso
        blx, brx = x - 5.8, x + 5.8
        tlx, trx, ty_ = nx - 6.8, nx + 7.2, ny - 1.5
        k = 0.40
        mlx, mrx, my = blx + (tlx - blx) * k, brx + (trx - brx) * k, hy + (ty_ - hy) * k
        self.to_lo.points = [blx, hy, brx, hy, mrx, my, mlx, my]
        self.to_up.points = [mlx, my, mrx, my, trx, ty_, tlx, ty_]
        k2 = 0.72
        yl, yr, yy = mlx + (tlx - mlx) * k2, mrx + (trx - mrx) * k2, my + (ty_ - my) * k2
        self.to_sh.points = [yl, yy, yr, yy, trx, ty_, tlx, ty_]
        self.belt.points = [mlx, my, mrx, my]
        ex, ey = x + (nx - x) * 0.60 + 1.2, hy + (ny - hy) * 0.60 + 0.5
        self.tw_1.points = [ex - 1.0, ey + 4.0, tlx + 1.5, yy - 0.5]
        self.tw_2.points = [ex + 1.0, ey + 4.0, trx - 1.5, yy - 0.5]
        self.tw_3.points = [ex, ey - 3.0, (mlx + mrx) * 0.5, my + 0.6]
        self.em_b.pos = (ex - 1.5, ey - 2.7)
        self.em_1.points = [ex - 5.0, ey + 4.2, ex, ey + 1.0, ex + 5.0, ey + 4.2]
        self.em_2.points = [ex - 5.0, ey - 4.2, ex, ey - 1.0, ex + 5.0, ey - 4.2]
        # head
        cx, cy = nx + 1.8, ny + 8.2
        self.head.pos = (cx - 8.2, cy - 8.8)
        self.mk_1.points = [cx - 0.6, cy + 8.8, cx + 0.4, cy - 8.8]
        self.mk_2.points = [cx - 8.0, cy + 1.2, cx, cy + 0.2, cx + 8.2, cy + 1.6]
        self.mk_3.points = [cx - 5.5, cy + 7.2, cx, cy + 2.4, cx + 5.5, cy + 7.2]
        eye = [cx + 0.8, cy + 0.2, cx + 8.0, cy + 3.4, cx + 6.8, cy + 7.6, cx + 0.8, cy + 4.4]
        self.eye.points = eye
        self.eye_o.points = eye
        # near limbs
        self._leg(x, hy, x + po['f1x'], y + po['f1y'] + 2.8, self.nl_t, self.nl_s, self.nl_so, self.nl_b)
        self.hand = self._arm(shx, shy, x + po['h1x'], y + po['h1y'], self.na_u, self.na_f, self.na_h)


class Game(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.sc, self.W = 1.0, 1280.0
        self.tcache = {}
        self.sky = make_sky()
        self.walls = make_walls()
        r = random.Random(7)
        self.far = make_layer(r, 160, 430, False)
        self.mid = make_layer(r, 110, 320, True)
        self.settings = {
            'particles': True,
            'quality': 'medium',
            'sound_fx': True,
            'night_mode': False,
            'fps': 60,
            'show_fps': False,
        }
        self.ptex = {}
        self.pfbo = []
        self.swtex = {}
        self.lfbo = []
        self.star_ins, self.cloud_ins = [], []
        self.hud_key = None
        self.frame = 0
        self._web_dirty = False
        self._fx_dirty = False
        self.best = self.load_best()     # also restores saved settings
        self.fps_t, self.fps_n, self.fps_val = 0.0, 0, 60.0
        self._ev = None

        self.state = 'main_menu'
        self.tm = 0.0
        self.dt = 1 / 60.0
        self.dead_t = 0.0
        self.jump_touches = set()
        self.web_touches = set()
        self.web_down = False
        self.buf = 0.0
        self.tap_end = -9.0
        self.press_time = 0.0
        self.zip_cd = 0.0
        self.fx = []
        self.shown = 0.0
        self.layers = []
        self.stars, self.clouds = [], []
        self.cam_y = 0.0
        self.shake = 0.0
        self.swing_hint = None

        c = self.canvas
        c.add(PushMatrix())
        self.scale = Scale(1, 1, 1)
        c.add(self.scale)
        self.bg = Canvas()
        c.add(self.bg)
        self.sky_dyn = Canvas()          # retained stars + clouds (only numbers change)
        c.add(self.sky_dyn)
        self.sky_fx = Canvas()           # the few far flyers, culled to the screen
        c.add(self.sky_fx)
        c.add(PushMatrix())
        self.cam_tr = Translate(0, 0)
        c.add(self.cam_tr)
        self.back = Canvas()
        c.add(self.back)
        self.world = Canvas()
        c.add(self.world)
        self.amb = Canvas()
        c.add(self.amb)
        self.web_cv = Canvas()          # web strands (rebuilt each frame, tiny)
        c.add(self.web_cv)
        self.pl_cv = Canvas()           # the player: retained instructions, never cleared
        c.add(self.pl_cv)
        self.rig = SpiderRig(self.pl_cv)
        self.fx_cv = Canvas()
        c.add(self.fx_cv)
        c.add(PopMatrix())
        self.hud = Canvas()
        c.add(self.hud)
        c.add(PopMatrix())

        self.build_ground()
        self.apply_size(Window.size)
        self.build_bg()
        self.reset_world()
        Window.bind(size=self.on_win)
        Window.bind(on_keyboard=self.on_key)
        self.set_fps(self.settings['fps'])

    def save_path(self):
        try:
            app = App.get_running_app()
            base = app.user_data_dir if app else os.path.dirname(os.path.abspath(__file__))
            return os.path.join(base, 'web_runner_best.json')
        except Exception:
            return 'web_runner_best.json'

    def load_best(self):
        try:
            with open(self.save_path()) as f:
                d = json.load(f)
        except Exception:
            return 0
        try:
            s = d.get('settings', {})
            for k in ('particles', 'sound_fx', 'show_fps'):
                if k in s:
                    self.settings[k] = bool(s[k])
            if s.get('quality') in QUALITY:
                self.settings['quality'] = s['quality']
            if s.get('fps') in FPS_OPTIONS:
                self.settings['fps'] = int(s['fps'])
        except Exception:
            pass
        try:
            return int(d['best'])
        except Exception:
            return 0

    def save_best(self):
        try:
            with open(self.save_path(), 'w') as f:
                json.dump({'best': self.best, 'settings': self.settings}, f)
        except Exception:
            pass

    def set_fps(self, fps):
        if fps not in FPS_OPTIONS:
            fps = 60
        self.settings['fps'] = fps
        if self._ev is not None:
            self._ev.cancel()
        self._ev = Clock.schedule_interval(self.update, 1.0 / fps)

    def q(self):
        return QUALITY.get(self.settings.get('quality', 'medium'), QUALITY['medium'])

    def settings_rows(self):
        s = self.settings
        return [('FRAME RATE', 'fps', 500, None),
                ('FPS COUNTER', 'show_fps', 428, s['show_fps']),
                ('PARTICLES', 'particles', 356, s['particles']),
                ('QUALITY', 'quality', 284, None),
                ('SOUND FX', 'sound_fx', 212, s['sound_fx'])]

    def toggle_setting(self, key):
        s = self.settings
        if key == 'fps':
            i = FPS_OPTIONS.index(s['fps']) if s['fps'] in FPS_OPTIONS else 3
            self.set_fps(FPS_OPTIONS[(i + 1) % len(FPS_OPTIONS)])
        elif key == 'quality':
            i = QUALITY_ORDER.index(s['quality']) if s['quality'] in QUALITY_ORDER else 1
            s['quality'] = QUALITY_ORDER[(i + 1) % len(QUALITY_ORDER)]
            self.apply_quality()
        else:
            s[key] = not s[key]
        self.save_best()

    def apply_quality(self):
        self.build_bg()
        self.rebake()

    def rebake(self):
        """Re-bake every building / swing object (quality change, resize, app resume)."""
        try:
            self.ptex.clear()
            self.swtex.clear()
            del self.pfbo[:]
            for b in self.bl:
                if b.visible and b.cv is not None:
                    self.world.remove(b.cv)
                b.visible = False
                self.build_bld(b)
            for o in self.swings:
                if o.visible and o.cv is not None:
                    self.world.remove(o.cv)
                o.visible = False
                self.make_swing_cv(o)
            self.update_visibility()
        except Exception:
            pass

    def prewarm(self):
        for size_ in (16, 20, 22, 24, 26, 38, 54):
            for ch in '0123456789/:':
                self.glyph(ch, size_)
        for size_ in (11, 14, 15, 16, 18, 20, 24, 26, 38, 54):
            for ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789%!$&-':
                self.glyph(ch, size_)

    def apply_size(self, size):
        self.sc = max(0.1, size[1] / VH)
        self.W = size[0] / self.sc
        self.scale.xyz = (self.sc, self.sc, 1)
        self.tcache.clear()
        self.hud_key = None
        self.prewarm()

    def on_win(self, win, size):
        self.apply_size(size)
        self.build_bg()
        self.rebake()
        self.fill_world()

    def on_key(self, win, key, *a):
        if key == 27:
            if self.state in ('play', 'paused'):
                self.toggle_pause()
                return True
            if self.state in ('settings', 'dead'):
                self.state = 'main_menu'
                return True
            return False
        return False

    def layer_tex(self, items, period, col, wcol, base, qs):
        """Bake a whole parallax skyline strip into ONE texture (a few quads instead of hundreds)."""
        hmax = max(h for (_x, _w, h, _win) in items)
        th = int(base + hmax + 70)
        fbo = Fbo(size=(int(math.ceil(period * qs)), int(math.ceil(th * qs))))
        with fbo:
            ClearColor(0, 0, 0, 0)
            ClearBuffers()
            PushMatrix()
            Scale(qs, qs, 1)
            Color(*col)
            for (x, bw, bh, win) in items:
                Rectangle(pos=(x, 0), size=(bw, base + bh + 60))
            if wcol:
                Color(*wcol)
                for (x, bw, bh, win) in items:
                    for dx, dy in win:
                        Rectangle(pos=(x + dx, base + dy + 60), size=(4, 5))
            PopMatrix()
        fbo.draw()
        self.lfbo.append(fbo)
        tex = fbo.texture
        tex.mag_filter = 'linear'
        tex.min_filter = 'linear'
        return tex, th

    def build_bg(self):
        self.bg.clear()
        self.sky_dyn.clear()
        del self.lfbo[:]
        self.layers = []
        W = self.W
        qd = self.q()
        rr = random.Random(11)
        with self.bg:
            Color(1, 1, 1, 1)
            Rectangle(texture=self.sky, pos=(0, 0), size=(W, VH))
            Color(1, 0.95, 0.8, 0.12)
            Ellipse(pos=(W * 0.7 - 20, 540), size=(94, 94))
            Color(0.96, 0.92, 0.82, 1)
            Ellipse(pos=(W * 0.7, 560), size=(54, 54))
            Color(0.8, 0.75, 0.66, 1)
            Ellipse(pos=(W * 0.7 + 12, 585), size=(12, 12))
            Ellipse(pos=(W * 0.7 + 30, 570), size=(9, 9))
            for layer, par, col, wcol, base in (
                    (self.far, 0.12, (0.23, 0.16, 0.42, 1), None, 60),
                    (self.mid, 0.28, (0.14, 0.1, 0.3, 1), (1, 0.75, 0.35, 0.8), 30)):
                items, period = layer
                tex, th = self.layer_tex(items, period, col, wcol if qd['lwin'] else None,
                                         base, qd['lay'])
                n = int(math.ceil(W / period)) + 1
                PushMatrix()
                tr = Translate(0, 0)
                Color(1, 1, 1, 1)
                for k in range(n):
                    Rectangle(texture=tex, pos=(k * period, -60), size=(period + 1, th))
                PopMatrix()
                self.layers.append((tr, par, period))
            Color(0.04, 0.03, 0.08, 1)
            Rectangle(pos=(0, 0), size=(W, 14))
        # retained stars and clouds: created once, only their numbers change afterwards
        self.star_ins, self.cloud_ins = [], []
        with self.sky_dyn:
            for _ in range(qd['stars']):
                sx, sy = rr.uniform(0, W), rr.uniform(300, 712)
                ph, sz = rr.uniform(0, 6.28), rr.choice((1.5, 2, 2, 3))
                col = Color(1, 1, 0.95, 0.5)
                rect = Rectangle(pos=(sx, sy), size=(sz, sz))
                self.star_ins.append((col, rect, sx, sy, ph))
            for _ in range(qd['clouds']):
                cx0, cyy = rr.uniform(0, W + 500), rr.uniform(360, 640)
                k, spd = rr.uniform(0.7, 1.4), rr.uniform(5, 14)
                PushMatrix()
                tr = Translate(0, 0)
                Color(0.78, 0.55, 0.8, 0.16)
                Ellipse(pos=(0, 0), size=(150 * k, 30 * k))
                Ellipse(pos=(30 * k, 10 * k), size=(90 * k, 28 * k))
                Ellipse(pos=(-20 * k, 4 * k), size=(70 * k, 20 * k))
                PopMatrix()
                self.cloud_ins.append((tr, cx0, cyy, spd))

    def build_ground(self):
        """Road strip: 3 retained rectangles; the dashes are one repeating texture."""
        buf = bytearray()
        for x in range(64):
            buf += bytes((204, 191, 102, 178) if 6 <= x < 34 else (0, 0, 0, 0))
        tex = Texture.create(size=(64, 1), colorfmt='rgba')
        tex.blit_buffer(bytes(buf), colorfmt='rgba', bufferfmt='ubyte')
        tex.wrap = 'repeat'
        tex.mag_filter = 'nearest'
        self.dash_tex = tex
        with self.back:
            Color(0.05, 0.045, 0.09, 1)
            self.g_road = Rectangle(pos=(0, 0), size=(100, 22))
            Color(0.3, 0.28, 0.4, 1)
            self.g_edge = Rectangle(pos=(0, 22), size=(100, 2))
            Color(1, 1, 1, 1)
            self.g_dash = Rectangle(texture=tex, pos=(0, 10), size=(100, 2))

    def txt_w(self, s, size):
        tot = 0.0
        for ch in s:
            tot += size * 0.3 if ch == ' ' else self.glyph(ch, size).width / self.sc
        return tot

    def ptxt(self, s, cx, y, maxw, color):
        for size in (20, 14, 11):
            if self.txt_w(s, size) <= maxw:
                self.txt(s, size, color, cx, y, 'c')
                return size
        return 0

    def blocked(self, posters, rx, ry, rw, rh, m=4):
        for q in posters:
            if (rx < q[0] + q[2] + m and rx + rw > q[0] - m and
                    ry < q[1] + q[3] + m and ry + rh > q[1] - m):
                return True
        return False

    def place_posters(self, b, r):
        st = b.style
        dens = {'brick': 1.0, 'apartment': 1.2, 'concrete': 1.0, 'neon': 0.8,
                'deco': 0.5, 'industrial': 0.8, 'glass': 0.0, 'loft': 0.8, 'ribbon': 0.3}[st]
        out = []

        def free(px, py, pw, ph):
            return all(px + pw + 10 < q[0] or px > q[0] + q[2] + 10 or
                       py + ph + 10 < q[1] or py > q[1] + q[3] + 10 for q in out)

        if st == 'neon' and b.h > 150:
            for _ in range(r.choice((1, 1, 2))):
                for _t in range(8):
                    sd = r.randint(0, 9999)
                    word = random.Random(sd).choice(SIGN_WORDS)
                    ph = len(word) * 17 + 8
                    if b.h < ph + 70 or b.w < 80:
                        break
                    px = r.choice((6.0, b.w - 30.0, r.uniform(20, b.w - 44)))
                    py = r.uniform(40, b.h - ph - 26)
                    if free(px, py, 24, ph):
                        out.append((px, py, 24, ph, 'sign', sd))
                        break
        n = min(9, int(b.w * b.h / 52000.0 * dens * self.q()['post'] + r.random()))
        kinds = ['gig', 'movie', 'sale', 'wanted', 'web', 'flyers', 'graf']
        sizes = [(30, 42), (38, 54), (46, 66), (56, 80), (70, 48)]
        for _ in range(n):
            for _t in range(8):
                pw, ph = r.choice(sizes)
                if b.h < ph + 60 or b.w < pw + 24:
                    continue
                px = r.uniform(10, b.w - pw - 10)
                py = r.uniform(12, b.h - ph - 22)
                if free(px, py, pw, ph):
                    out.append((px, py, pw, ph, r.choice(kinds), r.randint(0, 9999)))
                    break
        return out

    def draw_poster(self, b, q):
        px, py, pw, ph, kind, sd = q
        x, y = b.x + px, py
        if kind == 'sign':
            r = random.Random(sd)
            word = r.choice(SIGN_WORDS)
            col = r.choice(NEON_COLS)
            Color(0.05, 0.04, 0.1, 1)
            Rectangle(pos=(x, y), size=(pw, ph))
            Color(col[0], col[1], col[2], 1)
            Line(rectangle=(x, y, pw, ph), width=1.6)
            for i, ch in enumerate(word):
                self.txt(ch, 14, (col[0], col[1], col[2], 1), x + pw / 2.0,
                         y + ph - 6 - (i + 1) * 17 + 2, 'c')
            b.anim.append(('neon', x, y, pw, ph, col, r.uniform(1.5, 4)))
            return
        tex = self.poster_tex(kind, pw, ph, sd % 6)
        if tex is not None:
            bl = self.q()['blur']
            Color(1, 1, 1, 0.9)
            Rectangle(texture=tex, pos=(x - POSTER_PAD, y - POSTER_PAD),
                      size=(tex.width * bl, tex.height * bl))
        else:                                    # fallback: plain soft patch
            Color(0.6, 0.5, 0.6, 0.45)
            Rectangle(pos=(x, y), size=(pw, ph))

    def poster_tex(self, kind, pw, ph, v):
        """Paint the poster once into a small offscreen buffer and reuse it.
        Drawing it at 1/3 size and scaling it back up with linear filtering = blur."""
        key = (kind, int(pw), int(ph), v)
        if key in self.ptex:
            return self.ptex[key]
        tex = None
        bl = self.q()['blur']
        try:
            w = int(math.ceil((pw + 2 * POSTER_PAD) / bl))
            h = int(math.ceil((ph + 2 * POSTER_PAD) / bl))
            fbo = Fbo(size=(w, h))
            with fbo:
                ClearColor(0, 0, 0, 0)
                ClearBuffers()
                PushMatrix()
                Scale(1.0 / bl, 1.0 / bl, 1)
                self.paint_poster(POSTER_PAD, POSTER_PAD, pw, ph, kind, random.Random(v * 977 + 13))
                PopMatrix()
            fbo.draw()
            self.pfbo.append(fbo)
            tex = fbo.texture
            tex.mag_filter = 'linear'
            tex.min_filter = 'linear'
        except Exception:
            tex = None
        self.ptex[key] = tex
        return tex

    def paint_poster(self, x, y, pw, ph, kind, r):
        if kind == 'graf':
            cc = r.choice(NEON_COLS)
            Color(cc[0], cc[1], cc[2], 0.85)
            pts = []
            for i in range(6):
                pts += [x + pw * i / 5.0, y + ph * (0.25 + 0.5 * (i % 2)) + r.uniform(-4, 4)]
            Line(points=pts, width=3)
            Color(1, 1, 1, 0.8)
            Line(points=pts, width=1)
            Color(cc[0], cc[1], cc[2], 0.7)
            Ellipse(pos=(x + pw * 0.15, y - 3), size=(5, 9))
            Ellipse(pos=(x + pw * 0.62, y - 6), size=(4, 12))
            return
        Color(0, 0, 0, 0.35)
        Rectangle(pos=(x + 2, y - 2), size=(pw, ph))
        cx = x + pw / 2.0
        if kind == 'gig':
            c1 = r.choice(((0.85, 0.2, 0.5), (0.2, 0.6, 0.9), (0.95, 0.6, 0.15), (0.5, 0.3, 0.9)))
            Color(*C(c1))
            Rectangle(pos=(x, y), size=(pw, ph))
            Color(0, 0, 0, 0.35)
            Rectangle(pos=(x, y), size=(pw, ph * 0.28))
            d = min(pw * 0.6, ph * 0.42)
            Color(1, 1, 1, 0.85)
            Ellipse(pos=(cx - d / 2, y + ph * 0.32), size=(d, d))
            Color(*C(c1))
            Ellipse(pos=(cx - d * 0.22, y + ph * 0.32 + d * 0.28), size=(d * 0.44, d * 0.44))
            self.ptxt(r.choice(POSTER_WORDS['gig']), cx, y + ph * 0.7 + d * 0.2, pw - 6, (1, 0.95, 0.4, 1))
            Color(1, 1, 1, 0.8)
            for i in range(3):
                Rectangle(pos=(x + 4 + i * (pw - 8) / 3.0, y + 4), size=((pw - 8) / 3.0 - 2, 3))
        elif kind == 'movie':
            Color(0.08, 0.06, 0.18, 1)
            Rectangle(pos=(x, y), size=(pw, ph))
            d = min(pw * 0.55, ph * 0.4)
            mc = r.choice(((1, 0.8, 0.4), (0.8, 0.9, 1), (1, 0.5, 0.4)))
            Color(*C(mc))
            Ellipse(pos=(x + pw * 0.2, y + ph * 0.42), size=(d, d))
            Color(0.22, 0.1, 0.38, 1)
            Triangle(points=[x, y, x + pw * 0.5, y + ph * 0.34, x + pw, y])
            Color(0.15, 0.06, 0.28, 1)
            Triangle(points=[x + pw * 0.3, y, x + pw * 0.75, y + ph * 0.24, x + pw, y])
            self.ptxt(r.choice(POSTER_WORDS['movie']), cx, y + 4, pw - 6, (1, 0.85, 0.4, 1))
        elif kind == 'sale':
            Color(1, 0.85, 0.15, 1)
            Rectangle(pos=(x, y), size=(pw, ph))
            R = min(pw, ph) * 0.47
            sx0, sy0 = cx, y + ph * 0.5
            Color(0.9, 0.15, 0.15, 1)
            for k in range(10):
                a = k * math.pi / 5.0
                Triangle(points=[sx0 + math.cos(a - 0.17) * R * 0.62, sy0 + math.sin(a - 0.17) * R * 0.62,
                                 sx0 + math.cos(a + 0.17) * R * 0.62, sy0 + math.sin(a + 0.17) * R * 0.62,
                                 sx0 + math.cos(a) * R, sy0 + math.sin(a) * R])
            Ellipse(pos=(sx0 - R * 0.62, sy0 - R * 0.62), size=(R * 1.24, R * 1.24))
            self.ptxt(r.choice(POSTER_WORDS['sale']), sx0, sy0 - 8, R * 1.1, (1, 1, 0.85, 1))
        elif kind == 'wanted':
            Color(0.9, 0.82, 0.6, 1)
            Rectangle(pos=(x, y), size=(pw, ph))
            Color(0.35, 0.28, 0.2, 1)
            Line(rectangle=(x + 2, y + 2, pw - 4, ph - 4), width=1)
            self.ptxt('WANTED', cx, y + ph - 20, pw - 8, (0.3, 0.1, 0.08, 1))
            hd = min(pw * 0.36, ph * 0.3)
            Color(0.25, 0.2, 0.18, 1)
            Ellipse(pos=(cx - hd / 2, y + ph * 0.34), size=(hd, hd * 1.1))
            Triangle(points=[cx - hd * 0.9, y + ph * 0.14, cx + hd * 0.9, y + ph * 0.14, cx, y + ph * 0.4])
            Color(0.4, 0.3, 0.2, 1)
            Rectangle(pos=(x + 6, y + 5), size=(pw - 12, 2))
            Rectangle(pos=(x + 10, y + 9), size=(pw - 20, 2))
        elif kind == 'web':
            Color(0.75, 0.08, 0.12, 1)
            Rectangle(pos=(x, y), size=(pw, ph))
            wx0, wy0 = cx, y + ph * 0.6
            Color(1, 1, 1, 0.8)
            for k in range(8):
                a = k * math.pi / 4.0
                Line(points=[wx0, wy0, wx0 + math.cos(a) * pw * 0.6, wy0 + math.sin(a) * ph * 0.5], width=1)
            for f in (0.3, 0.55, 0.8):
                pts = []
                for k in range(8):
                    a = k * math.pi / 4.0
                    pts += [wx0 + math.cos(a) * pw * 0.6 * f, wy0 + math.sin(a) * ph * 0.5 * f]
                Line(points=pts, close=True, width=1)
            Color(0.1, 0.03, 0.06, 0.55)
            Rectangle(pos=(x, y), size=(pw, ph * 0.25))
            self.ptxt('WEB', cx, y + 3, pw - 6, (1, 1, 1, 1))
        else:
            for i in range(3):
                fc = r.choice(((1, 1, 0.9), (0.9, 0.5, 0.6), (0.5, 0.85, 0.9)))
                fx_ = x + r.uniform(0, pw * 0.3)
                fy_ = y + i * ph * 0.3
                fw, fh = pw * 0.7, ph * 0.38
                Color(*C(fc))
                Rectangle(pos=(fx_, fy_), size=(fw, fh))
                Color(0.15, 0.12, 0.2, 0.8)
                for k in range(3):
                    Rectangle(pos=(fx_ + 3, fy_ + 4 + k * 5), size=(fw * r.uniform(0.4, 0.85), 1.5))

        Color(0.92, 0.88, 0.72, 0.55)
        Rectangle(pos=(x - 2, y + ph - 3), size=(9, 5))
        Rectangle(pos=(x + pw - 7, y + ph - 3), size=(9, 5))
        Color(0.95, 0.95, 0.9, 0.9)
        Triangle(points=[x + pw, y, x + pw - 9, y, x + pw, y + 10])
        Color(0, 0, 0, 0.25)
        Triangle(points=[x + pw - 9, y, x + pw, y + 10, x + pw - 9, y + 10])
        Color(0, 0, 0, 0.18)
        Rectangle(pos=(x, y + ph * r.uniform(0.3, 0.7)), size=(pw, 1))


    def window(self, b, r, wx, wy, ww, wh, lit_p=0.42, neon=False):
        lit = r.random() < lit_p
        Color(0.13, 0.13, 0.19, 1)
        Rectangle(pos=(wx - 2, wy - 2), size=(ww + 4, wh + 4))
        if lit:
            if r.random() < 0.13:
                col = (0.45, 0.7, 1.0)
                b.anim.append(('tv', wx, wy, ww, wh))
            else:
                col = r.choice(WARM)
            Color(*C(col))
            Rectangle(pos=(wx, wy), size=(ww, wh))
            q = r.random()
            if q < 0.3:
                Color(0.75, 0.2, 0.28, 0.85)
                Rectangle(pos=(wx, wy), size=(ww * 0.3, wh))
                Rectangle(pos=(wx + ww * 0.7, wy), size=(ww * 0.3, wh))
            elif q < 0.45:
                Color(0.12, 0.07, 0.05, 0.85)
                Ellipse(pos=(wx + ww / 2 - 3, wy + wh * 0.46), size=(6, 6))
                Rectangle(pos=(wx + ww / 2 - 5, wy + 1), size=(10, wh * 0.45))
        else:
            Color(0.06, 0.07, 0.12, 1)
            Rectangle(pos=(wx, wy), size=(ww, wh))
            Color(0.3, 0.42, 0.62, 0.22)
            Triangle(points=[wx, wy + wh * 0.35, wx + ww * 0.7, wy + wh, wx, wy + wh])
            if r.random() < 0.2:
                Color(0.2, 0.22, 0.32, 0.9)
                for k in range(1, 5):
                    Rectangle(pos=(wx, wy + k * wh / 5.0), size=(ww, 1.5))
        Color(0.13, 0.13, 0.19, 1)
        Rectangle(pos=(wx + ww / 2 - 1, wy), size=(2, wh))
        Rectangle(pos=(wx, wy + wh * 0.58), size=(ww, 2))
        Color(0.46, 0.46, 0.54, 1)
        Rectangle(pos=(wx - 3, wy - 6), size=(ww + 6, 3))
        Color(0.3, 0.3, 0.38, 1)
        Rectangle(pos=(wx - 2, wy + wh + 2), size=(ww + 4, 2))
        if neon:
            nc = NEON_COLS[int(wx) % len(NEON_COLS)]
            Color(nc[0], nc[1], nc[2], 0.75)
            Line(rectangle=(wx - 2, wy - 2, ww + 4, wh + 4), width=1)
        elif r.random() < 0.08:
            Color(0.15, 0.55, 0.25, 1)
            Ellipse(pos=(wx + 2, wy - 5), size=(10, 9))
            Color(0.55, 0.3, 0.2, 1)
            Rectangle(pos=(wx + 3, wy - 6), size=(8, 3))
        return lit

    def bd_brick(self, b, r, posters, neon=False):
        x, w, h = b.x, b.w, b.h
        ww, wh = r.choice((18, 22, 28)), r.choice((30, 34, 40))
        sx = ww + r.choice((18, 24, 30))
        sy = wh + r.choice((32, 38, 44))
        cols = max(1, int((w - 20) // sx))
        mx = (w - cols * sx) / 2.0 + (sx - ww) / 2.0
        dy = 40
        while dy + wh < h - 24:
            for c in range(cols):
                if self.blocked(posters, mx + c * sx, dy, ww, wh):
                    continue
                self.window(b, r, x + mx + c * sx, dy, ww, wh, 0.42, neon)
            dy += sy

    def bd_loft(self, b, r, posters):
        """Warehouse-conversion look: tall arched windows."""
        x, w, h = b.x, b.w, b.h
        ww, wh = 26, 40
        sx, sy = ww + r.choice((20, 26)), wh + r.choice((30, 36))
        cols = max(1, int((w - 20) // sx))
        mx = (w - cols * sx) / 2.0 + (sx - ww) / 2.0
        dy = 36
        while dy + wh + ww / 2.0 < h - 22:
            for c in range(cols):
                px = mx + c * sx
                if self.blocked(posters, px - 4, dy - 4, ww + 8, wh + ww / 2.0 + 8):
                    continue
                wx = x + px
                lit = r.random() < 0.45
                Color(0.12, 0.1, 0.15, 1)
                Rectangle(pos=(wx - 2, dy - 2), size=(ww + 4, wh + 2))
                Ellipse(pos=(wx - 2, dy + wh - ww / 2.0), size=(ww + 4, ww + 2))
                if lit:
                    Color(*C(r.choice(WARM)))
                else:
                    Color(0.06, 0.07, 0.12, 1)
                Rectangle(pos=(wx, dy), size=(ww, wh))
                Ellipse(pos=(wx, dy + wh - ww / 2.0), size=(ww, ww))
                Color(0.12, 0.1, 0.15, 1)
                Rectangle(pos=(wx + ww / 2.0 - 1, dy), size=(2, wh + ww / 2.0))
                Rectangle(pos=(wx, dy + wh * 0.45), size=(ww, 2))
                Color(0.5, 0.45, 0.5, 1)
                Rectangle(pos=(wx - 3, dy - 5), size=(ww + 6, 3))
            dy += sy

    def bd_ribbon(self, b, r, posters):
        """Modern office block: long horizontal bands of glass."""
        x, w, h = b.x, b.w, b.h
        fh = r.choice((34, 40, 46))
        bh = fh * 0.55
        dy = 30
        while dy + bh < h - 22:
            Color(0.07, 0.09, 0.14, 1)
            Rectangle(pos=(x + 6, dy), size=(w - 12, bh))
            seg = 22
            for i in range(int((w - 12) // seg)):
                px = 6 + i * seg
                if self.blocked(posters, px, dy, seg, bh):
                    continue
                if r.random() < 0.4:
                    Color(*C(r.choice(WARM), 0.9))
                else:
                    Color(0.3, 0.5, 0.7, 0.25)
                Rectangle(pos=(x + px + 1, dy + 1), size=(seg - 2, bh - 2))
            Color(0.55, 0.58, 0.66, 1)
            Rectangle(pos=(x, dy - 4), size=(w, 3))
            dy += fh

    def face_scaffold(self, b, r):
        """Construction scaffolding on the facade (static, baked into the building texture)."""
        x, w, h = b.x, b.w, b.h
        sw = min(w - 30, r.uniform(70, 140))
        if sw < 40:
            return
        sx0 = x + r.uniform(14, max(14.0, w - sw - 14))
        sh = min(h - 50, r.choice((80, 120, 160)))
        n = int(sw // 35) + 1
        Color(0.25, 0.24, 0.28, 0.95)
        for i in range(n + 1):
            Line(points=[sx0 + i * sw / n, 20, sx0 + i * sw / n, 20 + sh], width=1.6)
        for i in range(n):
            Line(points=[sx0 + i * sw / n, 20, sx0 + (i + 1) * sw / n, 60], width=1.0)
        Color(0.55, 0.45, 0.25, 1)
        for k in range(int(sh // 40) + 1):
            Rectangle(pos=(sx0 - 3, 20 + k * 40), size=(sw + 6, 4))

    def bd_neon(self, b, r, posters):
        self.bd_brick(b, r, posters, neon=True)

        aw = min(b.w - 20, r.uniform(80, 160))
        ax_ = b.x + r.uniform(10, max(10, b.w - aw - 10))
        if not self.blocked(posters, ax_ - b.x, 14, aw, 22):
            nc = r.choice(NEON_COLS)
            n = int(aw // 14)
            for i in range(n):
                Color(*C(nc if i % 2 else (0.9, 0.9, 0.95)))
                Rectangle(pos=(ax_ + i * 14, 24), size=(14, 12))
                Triangle(points=[ax_ + i * 14, 24, ax_ + i * 14 + 14, 24, ax_ + i * 14 + 7, 18])

    def bd_apartment(self, b, r, posters):
        x, w, h = b.x, b.w, b.h
        ww, wh = r.choice((20, 24)), r.choice((34, 38))
        sx = ww + r.choice((28, 36))
        sy = wh + r.choice((40, 46))
        cols = max(1, int((w - 64) // sx))
        mx = (w - cols * sx) / 2.0 + (sx - ww) / 2.0
        dy = 48
        while dy + wh < h - 26:
            for c in range(cols):
                wx = mx + c * sx
                if self.blocked(posters, wx - 6, dy - 10, ww + 12, wh + 10):
                    continue
                self.window(b, r, x + wx, dy, ww, wh, 0.45)
                q = r.random()
                if q < 0.5:
                    Color(0.35, 0.35, 0.42, 1)
                    Rectangle(pos=(x + wx - 6, dy - 10), size=(ww + 12, 4))
                    Color(0.2, 0.2, 0.26, 1)
                    for k in range(5):
                        Rectangle(pos=(x + wx - 5 + k * (ww + 10) / 4.0, dy - 6), size=(1.5, 8))
                    Rectangle(pos=(x + wx - 6, dy + 2), size=(ww + 12, 1.5))
                    if r.random() < 0.5:
                        Color(0.15, 0.55, 0.25, 1)
                        Ellipse(pos=(x + wx - 3, dy + 3), size=(9, 8))
                        Color(0.7, 0.3, 0.25, 1)
                        Rectangle(pos=(x + wx - 2, dy + 1), size=(7, 3))
                elif q < 0.65:
                    lc = r.choice(((0.9, 0.9, 0.95), (0.9, 0.4, 0.4), (0.4, 0.7, 0.9), (0.95, 0.85, 0.3)))
                    Color(0.7, 0.7, 0.75, 1)
                    Line(points=[x + wx - 8, dy + wh * 0.7, x + wx + ww + 14, dy + wh * 0.62], width=1)
                    Color(*C(lc))
                    Rectangle(pos=(x + wx - 2, dy + wh * 0.4), size=(6, 12))
                    Rectangle(pos=(x + wx + 8, dy + wh * 0.38), size=(7, 12))
                elif q < 0.78:
                    Color(0.62, 0.64, 0.7, 1)
                    Rectangle(pos=(x + wx + ww + 3, dy + 4), size=(11, 9))
                    Color(0.25, 0.26, 0.3, 1)
                    Rectangle(pos=(x + wx + ww + 5, dy + 6), size=(7, 5))
            dy += sy

        fx_ = x + (6 if r.random() < 0.5 else w - 40)
        yy = 48 - 10
        d = 1
        Color(0.14, 0.14, 0.18, 1)
        while yy + sy < h - 20:
            Rectangle(pos=(fx_, yy), size=(34, 3))
            Line(points=[fx_, yy + 3, fx_, yy + 16, fx_ + 34, yy + 16, fx_ + 34, yy + 3], width=1.2)
            if d > 0:
                Line(points=[fx_ + 4, yy + 3, fx_ + 30, yy + sy], width=1.4)
            else:
                Line(points=[fx_ + 30, yy + 3, fx_ + 4, yy + sy], width=1.4)
            d = -d
            yy += sy

    def bd_concrete(self, b, r, posters):
        x, w, h = b.x, b.w, b.h
        fh = r.choice((44, 52, 60))
        wh = fh * 0.5
        dy = 34
        while dy + wh < h - 24:
            sgx = 14
            while sgx + 30 < w - 14:
                sw = r.choice((34, 46, 58))
                if sgx + sw > w - 14:
                    sw = w - 14 - sgx
                if not self.blocked(posters, sgx, dy, sw, wh):
                    lit = r.random() < 0.4
                    Color(0.12, 0.12, 0.18, 1)
                    Rectangle(pos=(x + sgx - 1, dy - 1), size=(sw + 2, wh + 2))
                    if lit:
                        Color(*C(r.choice(WARM)))
                    else:
                        Color(0.06, 0.07, 0.12, 1)
                    Rectangle(pos=(x + sgx, dy), size=(sw, wh))
                    if not lit:
                        Color(0.3, 0.42, 0.62, 0.2)
                        Rectangle(pos=(x + sgx, dy + wh * 0.5), size=(sw, wh * 0.5))
                    Color(0.12, 0.12, 0.18, 1)
                    for k in range(1, int(sw // 14) + 1):
                        Rectangle(pos=(x + sgx + k * 14 - 1, dy), size=(1.5, wh))
                sgx += sw + 8
            Color(0.2, 0.2, 0.26, 1)
            Rectangle(pos=(x, dy - 7), size=(w, 3))
            Color(0.55, 0.56, 0.62, 0.5)
            Rectangle(pos=(x, dy - 4), size=(w, 1))
            dy += fh

    def bd_glass(self, b, r, posters):
        x, w, h = b.x, b.w, b.h
        cols, rows = int(w // 16), int(h // 16)
        for rw in range(1, rows):
            if r.random() < 0.55:
                for c in range(cols):
                    if r.random() < 0.7:
                        if r.random() < 0.8:
                            Color(*C(r.choice(WARM), 0.95))
                        else:
                            Color(0.55, 0.8, 1.0, 0.9)
                        Rectangle(pos=(x + c * 16 + 1, rw * 16 + 1), size=(14, 14))
        Color(0.04, 0.09, 0.16, 0.9)
        for c in range(0, cols + 1, 4):
            Rectangle(pos=(x + c * 16 - 1, 0), size=(2, h))
        Color(1, 1, 1, 0.06)
        Quad(points=[x + w * 0.05, 0, x + w * 0.3, 0, x + w * 0.7, h, x + w * 0.45, h])
        Color(1, 1, 1, 0.045)
        Quad(points=[x + w * 0.45, 0, x + w * 0.55, 0, x + w * 0.95, h, x + w * 0.85, h])

    def bd_deco(self, b, r, posters):
        x, w, h = b.x, b.w, b.h
        n = max(1, int(w // 46))
        step = (w - 20.0) / n
        Color(0.78, 0.66, 0.4, 0.5)
        for i in range(n + 1):
            Rectangle(pos=(x + 10 + i * step - 3, 0), size=(6, h - 10))
        for i in range(n):
            cx = x + 10 + (i + 0.5) * step
            dy = 40
            while dy + 46 < h - 24:
                if not self.blocked(posters, cx - x - 10, dy - 4, 20, 58):
                    Color(0.85, 0.7, 0.3, 1)
                    Rectangle(pos=(cx - 9, dy - 2), size=(18, 46))
                    Triangle(points=[cx - 9, dy + 44, cx + 9, dy + 44, cx, dy + 54])
                    if r.random() < 0.4:
                        Color(*C(r.choice(WARM)))
                    else:
                        Color(0.07, 0.08, 0.13, 1)
                    Rectangle(pos=(cx - 7, dy), size=(14, 42))
                    Triangle(points=[cx - 7, dy + 42, cx + 7, dy + 42, cx, dy + 50])
                    Color(0.85, 0.7, 0.3, 1)
                    Rectangle(pos=(cx - 1, dy), size=(2, 44))
                dy += 62

    def bd_industrial(self, b, r, posters):
        x, w, h = b.x, b.w, b.h
        wy = h - 50
        if wy > 90:
            i = 0
            while 14 + i * 62 + 44 < w - 10:
                wx = 14 + i * 62
                if not self.blocked(posters, wx, wy, 44, 20):
                    Color(0.08, 0.08, 0.12, 1)
                    Rectangle(pos=(x + wx, wy), size=(44, 20))
                    if r.random() < 0.45:
                        Color(0.9, 0.8, 0.45, 0.9)
                        Rectangle(pos=(x + wx + 2, wy + 2), size=(40, 16))
                    Color(0.35, 0.37, 0.45, 1)
                    for k in range(1, 6):
                        Rectangle(pos=(x + wx + k * 7, wy), size=(1.2, 20))
                i += 1
        nd = max(1, int(w // 280))
        dh = min(86.0, h - 40)
        for i in range(nd):
            dx = (i + 0.5) * w / nd - 52
            if self.blocked(posters, dx, 0, 104, dh):
                continue
            Color(0.2, 0.2, 0.26, 1)
            Rectangle(pos=(x + dx, 0), size=(104, dh))
            Color(0.13, 0.13, 0.18, 1)
            for k in range(1, int(dh // 8)):
                Rectangle(pos=(x + dx, k * 8), size=(104, 1.5))
            Color(0.95, 0.75, 0.15, 1)
            for k in range(0, 104, 16):
                Quad(points=[x + dx + k, dh, x + dx + k + 8, dh, x + dx + k + 4, dh + 8, x + dx + k - 4, dh + 8])

        Color(0.35, 0.37, 0.44, 1)
        for _ in range(2):
            px = x + r.uniform(20, w - 30)
            Line(points=[px, 0, px, h - 30, px + 14, h - 30, px + 14, h - 8], width=3.5)
            Color(0.8, 0.2, 0.2, 1)
            Rectangle(pos=(px - 4, h * 0.45), size=(8, 6))
            Color(0.35, 0.37, 0.44, 1)

    def d_water(self, b, r, dx):
        top = b.h
        Color(0.12, 0.1, 0.14, 1)
        Line(points=[dx, top, dx + 8, top + 26], width=2)
        Line(points=[dx + 44, top, dx + 36, top + 26], width=2)
        Color(0.36, 0.24, 0.18, 1)
        Rectangle(pos=(dx, top + 26), size=(44, 34))
        Color(0.22, 0.16, 0.15, 1)
        for k in range(1, 4):
            Rectangle(pos=(dx, top + 26 + k * 8), size=(44, 1.5))
        Triangle(points=[dx - 3, top + 60, dx + 47, top + 60, dx + 22, top + 80])

    def d_antenna(self, b, r, dx):
        top = b.h
        Color(0.15, 0.13, 0.18, 1)
        Line(points=[dx, top, dx, top + 62], width=1.5)
        Line(points=[dx - 8, top + 46, dx + 8, top + 46], width=1.5)
        Line(points=[dx - 5, top + 54, dx + 5, top + 54], width=1.5)
        b.anim.append(('beacon', dx, top + 63, (1.0, 0.2, 0.2), r.uniform(1.0, 1.8)))

    def d_ac(self, b, r, dx):
        top = b.h
        Color(0.3, 0.31, 0.36, 1)
        Rectangle(pos=(dx, top), size=(34, 18))
        Color(0.18, 0.19, 0.23, 1)
        Ellipse(pos=(dx + 3, top + 3), size=(12, 12))
        Ellipse(pos=(dx + 19, top + 3), size=(12, 12))
        b.anim.append(('fan', dx + 9, top + 9, 5.0))
        b.anim.append(('fan', dx + 25, top + 9, 5.0))

    def d_chimney(self, b, r, dx):
        top = b.h
        Color(0.35, 0.2, 0.18, 1)
        Rectangle(pos=(dx, top), size=(14, 30))
        Color(0.2, 0.12, 0.12, 1)
        Rectangle(pos=(dx - 2, top + 30), size=(18, 5))
        b.anim.append(('smoke', dx + 7, top + 36, 1.0, r.uniform(0, 1)))

    def d_dish(self, b, r, dx):
        top = b.h
        Color(0.3, 0.3, 0.36, 1)
        Rectangle(pos=(dx + 10, top), size=(5, 9))
        Color(0.8, 0.82, 0.9, 1)
        Ellipse(pos=(dx + 1, top + 8), size=(24, 24))
        Color(0.45, 0.47, 0.55, 1)
        Ellipse(pos=(dx + 4, top + 11), size=(18, 18))
        Color(0.3, 0.3, 0.36, 1)
        Line(points=[dx + 13, top + 20, dx + 24, top + 36], width=1.5)
        Ellipse(pos=(dx + 22, top + 34), size=(4, 4))

    def d_billboard(self, b, r, dx):
        top = b.h
        sd = r.randint(0, 9999)
        rr = random.Random(sd)
        word = rr.choice(BOARD_WORDS)
        bc = rr.choice(NEON_COLS)
        Color(0.14, 0.13, 0.18, 1)
        Line(points=[dx + 14, top, dx + 14, top + 22], width=3)
        Line(points=[dx + 82, top, dx + 82, top + 22], width=3)
        Rectangle(pos=(dx, top + 20), size=(96, 54))
        Color(0.05, 0.04, 0.09, 1)
        Rectangle(pos=(dx + 4, top + 24), size=(88, 46))
        Color(bc[0] * 0.35, bc[1] * 0.35, bc[2] * 0.35, 1)
        Rectangle(pos=(dx + 4, top + 24), size=(88, 16))
        self.ptxt(word, dx + 48, top + 40, 80, C(bc))
        Color(1, 0.95, 0.6, 1)
        for k in range(4):
            Ellipse(pos=(dx + 10 + k * 24, top + 76), size=(4, 4))
        b.anim.append(('glow', dx + 4, top + 24, 88, 46, bc, r.uniform(2, 5)))

    def d_solar(self, b, r, dx):
        top = b.h
        for i in range(3):
            px = dx + i * 22
            Color(0.1, 0.18, 0.4, 1)
            Quad(points=[px, top + 3, px + 20, top + 3, px + 20, top + 20, px, top + 24])
            Color(0.5, 0.65, 0.9, 0.7)
            Line(points=[px + 10, top + 3, px + 10, top + 22], width=1)
            Line(points=[px, top + 14, px + 20, top + 12], width=1)
            Color(0.2, 0.2, 0.25, 1)
            Rectangle(pos=(px + 9, top), size=(2, 4))

    def d_garden(self, b, r, dx):
        top = b.h
        Color(0.3, 0.2, 0.15, 1)
        Rectangle(pos=(dx, top), size=(50, 8))
        for i in range(5):
            Color(0.12 + 0.05 * (i % 2), 0.5 + 0.1 * (i % 3), 0.22, 1)
            Ellipse(pos=(dx + i * 10 - 2, top + 5), size=(14, 12 + (i % 2) * 6))
        Color(0.95, 0.5, 0.6, 1)
        Ellipse(pos=(dx + 8, top + 14), size=(4, 4))
        Ellipse(pos=(dx + 30, top + 16), size=(4, 4))
        b.anim.append(('lights', dx - 4, top + 34, dx + 54, 9, r.uniform(0, 5)))
        Color(0.35, 0.3, 0.3, 1)
        Line(points=[dx - 4, top, dx - 4, top + 34], width=1.5)
        Line(points=[dx + 54, top, dx + 54, top + 34], width=1.5)

    def d_helipad(self, b, r, dx):
        top = b.h
        Color(0.18, 0.18, 0.24, 1)
        Ellipse(pos=(dx, top - 2), size=(92, 12))
        Color(0.95, 0.85, 0.2, 1)
        Line(ellipse=(dx + 3, top, 86, 8), width=1.2)
        Rectangle(pos=(dx + 34, top + 1), size=(3, 6))
        Rectangle(pos=(dx + 55, top + 1), size=(3, 6))
        Rectangle(pos=(dx + 36, top + 3), size=(20, 2))
        for k in range(4):
            b.anim.append(('beacon', dx + 4 + k * 28, top + 4, (0.3, 1.0, 0.4), 1.4))

    def d_stack(self, b, r, dx):
        top = b.h
        hh = r.uniform(70, 110)
        Color(0.3, 0.3, 0.36, 1)
        Rectangle(pos=(dx, top), size=(22, hh))
        n = int(hh // 16)
        for k in range(n):
            Color(*(C((0.85, 0.2, 0.2)) if k % 2 == 0 else C((0.9, 0.9, 0.92))))
            Rectangle(pos=(dx, top + hh - (k + 1) * 16), size=(22, 8))
        Color(0.18, 0.18, 0.22, 1)
        Rectangle(pos=(dx - 2, top + hh), size=(26, 4))
        b.anim.append(('smoke', dx + 11, top + hh + 6, 1.5, r.uniform(0, 1)))
        b.anim.append(('beacon', dx + 11, top + hh + 8, (1.0, 0.25, 0.2), 1.3))

    def d_tank(self, b, r, dx):
        top = b.h
        Color(0.55, 0.57, 0.64, 1)
        Rectangle(pos=(dx, top), size=(46, 36))
        Ellipse(pos=(dx, top + 30), size=(46, 12))
        Color(0.4, 0.42, 0.5, 1)
        Ellipse(pos=(dx, top - 6), size=(46, 12))
        Color(0.3, 0.32, 0.4, 1)
        for k in range(1, 4):
            Rectangle(pos=(dx, top + k * 9), size=(46, 1.5))
        Color(0.25, 0.25, 0.3, 1)
        Line(points=[dx + 36, top + 36, dx + 36, top + 54, dx + 24, top + 54], width=2)

    def d_crane(self, b, r, dx):
        top = b.h
        m = dx + 46
        Color(0.9, 0.7, 0.15, 1)
        Line(points=[m, top, m, top + 120], width=3)
        Line(points=[m + 8, top, m + 8, top + 120], width=3)
        for k in range(0, 120, 20):
            Line(points=[m, top + k, m + 8, top + k + 20], width=1.2)
        Line(points=[m - 40, top + 124, m + 66, top + 124], width=3)
        Line(points=[m + 4, top + 150, m - 40, top + 124], width=1.2)
        Line(points=[m + 4, top + 150, m + 66, top + 124], width=1.2)
        Color(0.25, 0.25, 0.3, 1)
        Rectangle(pos=(m - 40, top + 110), size=(14, 14))
        Color(0.6, 0.6, 0.66, 1)
        Line(points=[m + 56, top + 124, m + 56, top + 94], width=1)
        Rectangle(pos=(m + 52, top + 90), size=(8, 5))
        b.anim.append(('beacon', m + 4, top + 152, (1.0, 0.25, 0.2), 1.2))

    def d_saw(self, b, r, dx):
        top = b.h
        n = max(1, int((b.w - 30) // 52))
        x0 = b.x + (b.w - n * 52) / 2.0
        for i in range(n):
            px = x0 + i * 52
            Color(0.2, 0.21, 0.27, 1)
            Triangle(points=[px, top, px + 52, top, px + 52, top + 26])
            Color(0.55, 0.75, 0.85, 0.6)
            Quad(points=[px + 52, top, px + 52, top + 26, px + 49, top + 24, px + 49, top])

    def d_crown(self, b, r, dx):
        top, w = b.h, b.w
        cx = b.x + w / 2.0
        if b.style == 'glass':
            steps = [(0.62, 26)]
            bc, tc = (0.1, 0.22, 0.32), (0.45, 0.85, 0.95)
        else:
            steps = [(0.80, 18), (0.54, 22), (0.30, 26)]
            bc, tc = (0.5, 0.42, 0.28), (0.95, 0.8, 0.4)
        yy = top + 2
        for k, (fw, fh) in enumerate(steps):
            sw = w * fw
            Color(*C(bc))
            Rectangle(pos=(cx - sw / 2, yy), size=(sw, fh))
            Color(*C(tc))
            Rectangle(pos=(cx - sw / 2 - 2, yy + fh - 2), size=(sw + 4, 3))
            Color(*C(WARM[k % 4]))
            for j in range(3):
                Rectangle(pos=(cx - sw / 2 + sw * (j + 0.5) / 3.0 - 2, yy + 6), size=(4, fh - 12))
            yy += fh
        ah = r.uniform(55, 85)
        Color(0.75, 0.75, 0.82, 1)
        Line(points=[cx, yy, cx, yy + ah], width=2)
        Triangle(points=[cx - 3, yy + 2, cx + 3, yy + 2, cx, yy + 22])
        b.anim.append(('beacon', cx, yy + ah + 2, (1.0, 0.25, 0.2), 1.0))

    def roof_decor(self, b, r):
        x, w, top, st = b.x, b.w, b.h, b.style
        used = []

        def spot(wd):
            for _ in range(14):
                o = r.uniform(10, max(10.0, w - wd - 10))
                if all(o + wd + 14 < u0 or o > u1 + 14 for u0, u1 in used):
                    used.append((o, o + wd))
                    return x + o
            return None

        def add(kind, wd):
            dx = spot(wd)
            if dx is not None:
                getattr(self, 'd_' + kind)(b, r, dx)

        if w >= 220:
            if r.random() < 0.36:
                dx = spot(56)
                if dx is not None:
                    for i in range(r.randint(3, 6)):
                        b.animals.append({'k': 'pig', 'x': dx + 4 + i * r.uniform(7, 10), 'y': top,
                                          'ph': r.uniform(0, 6.28), 'st': None,
                                          'vx': r.uniform(70, 150), 'vy': r.uniform(110, 230)})
            if r.random() < 0.26:
                dx = spot(90)
                if dx is not None:
                    b.animals.append({'k': 'cat', 'x': dx + 6, 'y': top, 'ph': r.uniform(0, 6.28),
                                      'run': False, 'ex': dx + 76})
        big = w >= 300
        if st == 'brick':
            if w >= 260 and r.random() < 0.30: add('water', 46)
            if r.random() < 0.35: add('antenna', 16)
            if w >= 200 and r.random() < 0.40: add('ac', 34)
            if r.random() < 0.22: add('chimney', 18)
            if r.random() < 0.25: add('dish', 26)
            if w >= 240 and r.random() < 0.15: add('garden', 58)
        elif st == 'apartment':
            if r.random() < 0.6: add('dish', 26)
            if w >= 200 and r.random() < 0.4: add('ac', 34)
            if w >= 260 and r.random() < 0.25: add('water', 46)
            if r.random() < 0.25: add('chimney', 18)
            if w >= 240 and r.random() < 0.3: add('garden', 58)
        elif st == 'concrete':
            add('ac', 34)
            if w >= 500: add('ac', 34)
            if big and r.random() < 0.18: add('helipad', 94)
            if r.random() < 0.4: add('antenna', 16)
            if big and r.random() < 0.3: add('solar', 62)
            if big and r.random() < 0.2: add('billboard', 98)
            if big and r.random() < 0.22: add('crane', 114)
        elif st == 'glass':
            if w >= 150 and r.random() < 0.8:
                self.d_crown(b, r, 0)
                used.append((w * 0.1, w * 0.9))
            elif big and r.random() < 0.5:
                add('helipad', 94)
            if big and r.random() < 0.2: add('solar', 62)
            add('antenna', 16)
        elif st == 'deco':
            if w >= 150:
                self.d_crown(b, r, 0)
                used.append((w * 0.1, w * 0.9))
        elif st == 'industrial':
            if r.random() < 0.7: self.d_saw(b, r, 0)
            for _ in range(r.choice((1, 1, 2))): add('stack', 22)
            if big and r.random() < 0.5: add('tank', 46)
            if big and r.random() < 0.3: add('billboard', 98)
        else:
            if big and r.random() < 0.18: add('crane', 114)
            if w >= 200 and r.random() < 0.7: add('billboard', 98)
            if r.random() < 0.3: add('antenna', 16)
            if r.random() < 0.3: add('ac', 34)
            if r.random() < 0.2: add('dish', 26)

    def bake_scale(self, fw, fh):
        s = self.q()['bake'] * min(self.sc, 1.5)
        return max(0.25, min(s, 2000.0 / max(fw, 1.0), 2000.0 / max(fh, 1.0)))

    def build_bld(self, b):
        """Paint everything that never moves (wall, windows, posters, roof props) ONCE into a
        single texture; the building is then a single textured quad on screen."""
        r = random.Random(b.seed)
        b.anim = []
        b.animals = []
        x, w, top = b.x, b.w, b.h
        S = STYLE[b.style]
        posters = self.place_posters(b, r)
        tw, th = w / TILE, top / TILE
        t = b.tint
        PADX, PADT = 8.0, 190.0
        fw, fh = w + 2 * PADX, top + PADT
        qs = self.bake_scale(fw, fh)
        fbo = Fbo(size=(int(math.ceil(fw * qs)), int(math.ceil(fh * qs))))
        with fbo:
            ClearColor(0, 0, 0, 0)
            ClearBuffers()
            PushMatrix()
            Scale(qs, qs, 1)
            Translate(PADX - x, 0, 0)
            Color(t * S[1][0], t * S[1][1], min(1.0, t * S[1][2]), 1)
            Rectangle(texture=self.walls[S[0]], pos=(x, 0), size=(w, top),
                      tex_coords=(0, 0, tw, 0, tw, th, 0, th))
            getattr(self, 'bd_' + b.style)(b, r, posters)
            for q in posters:
                self.draw_poster(b, q)
            Color(*C(S[2]))
            Rectangle(pos=(x - 4, top - 7), size=(w + 8, 9))
            Color(*C(S[3]))
            Rectangle(pos=(x - 4, top + 1), size=(w + 8, 2))
            if b.style == 'deco':
                Color(*C(S[3], 0.9))
                for k in range(int(w // 22)):
                    Rectangle(pos=(x + 6 + k * 22, top - 14), size=(8, 6))
            Color(0.15, 0.95, 0.95, 0.85)
            Line(points=[x, 0, x, top - 7], width=1.5)
            Line(points=[x + w, 0, x + w, top - 7], width=1.5)
            if (not b.plain and b.h > 150 and r.random() < 0.2 and
                    b.style in ('brick', 'apartment', 'concrete', 'loft', 'ribbon')):
                self.face_scaffold(b, r)
            if not b.plain:
                self.roof_decor(b, r)
            PopMatrix()
        fbo.draw()
        tex = fbo.texture
        tex.mag_filter = 'linear'
        tex.min_filter = 'linear'
        cv = Canvas()
        with cv:
            Color(1, 1, 1, 1)
            Rectangle(texture=tex, pos=(x - PADX, 0), size=(fw, fh))
        b.fbo = fbo
        b.cv = cv

    def sw_blimp(self, o):
        rl = o.rl
        A, B, K = PALS[o.pal]
        hy = rl + 14
        Color(0.3, 0.3, 0.36, 1)
        Line(points=[-20, rl + 12, -34, hy + 6], width=1.5)
        Line(points=[20, rl + 12, 34, hy + 6], width=1.5)
        Color(*C(K))
        Triangle(points=[-112, hy + 56, -142, hy + 84, -88, hy + 66])
        Triangle(points=[-112, hy + 20, -142, hy - 8, -88, hy + 10])
        Color(*C(B))
        Ellipse(pos=(-125, hy), size=(250, 76))
        Color(*C(A))
        Ellipse(pos=(-125, hy + 14), size=(250, 62))
        Color(1, 1, 1, 0.22)
        Ellipse(pos=(-90, hy + 56), size=(170, 10))
        Color(*C(K))
        Rectangle(pos=(-18, hy + 8), size=(10, 60))
        Rectangle(pos=(48, hy + 9), size=(8, 58))
        Color(0.08, 0.08, 0.16, 1)
        Rectangle(pos=(-50, hy + 27), size=(100, 24))
        self.txt('WEB RUN', 14, (1, 0.85, 0.3, 1), 0, hy + 29, 'c')
        Color(0.25, 0.27, 0.34, 1)
        Rectangle(pos=(-24, rl), size=(48, 14))
        Color(1, 0.85, 0.45, 1)
        for k in range(4):
            Rectangle(pos=(-18 + k * 10, rl + 4), size=(6, 6))
        Color(0.3, 0.3, 0.36, 1)
        Rectangle(pos=(-134, hy + 34), size=(9, 10))

    def sw_balloon(self, o):
        rl = o.rl
        A, B, K = PALS[o.pal]
        by_ = rl + 18
        Color(0.45, 0.35, 0.25, 1)
        Line(points=[-12, by_, -22, by_ + 28], width=1.2)
        Line(points=[12, by_, 22, by_ + 28], width=1.2)
        Line(points=[0, by_, 0, by_ + 28], width=1)
        Color(0.52, 0.33, 0.18, 1)
        Rectangle(pos=(-13, rl), size=(26, 18))
        Color(0.35, 0.22, 0.12, 1)
        for i in range(1, 4):
            Rectangle(pos=(-13 + i * 6.5, rl), size=(1.5, 18))
        Rectangle(pos=(-13, rl + 8), size=(26, 1.5))
        Color(0.2, 0.2, 0.25, 1)
        Rectangle(pos=(-3, rl + 18), size=(6, 8))
        ey = rl + 34
        Color(*C(B))
        Quad(points=[-18, ey - 6, 18, ey - 6, 14, ey + 4, -14, ey + 4])
        Color(*C(A))
        Ellipse(pos=(-56, ey), size=(112, 122))
        Color(*C(K))
        Ellipse(pos=(-40, ey), size=(80, 122))
        Color(*C(A))
        Ellipse(pos=(-22, ey), size=(44, 122))
        Color(*C(K))
        Ellipse(pos=(-8, ey), size=(16, 122))
        Color(0, 0, 0, 0.16)
        Ellipse(pos=(8, ey + 4), size=(44, 112))
        Color(1, 1, 1, 0.2)
        Ellipse(pos=(-46, ey + 60), size=(16, 46))
        Color(0.25, 0.25, 0.3, 1)
        Line(points=[0, ey + 120, 0, ey + 138], width=1.5)
        Color(*C(K))
        Triangle(points=[0, ey + 138, 16, ey + 132, 0, ey + 126])

    def sw_heli(self, o):
        rl = o.rl
        A, B, K = PALS[o.pal]
        by_ = rl + 16
        Color(0.2, 0.2, 0.26, 1)
        Line(points=[-36, rl, 34, rl, 40, rl + 6], width=3)
        Line(points=[-22, rl, -18, by_], width=2)
        Line(points=[22, rl, 18, by_], width=2)
        Color(*C(B))
        Quad(points=[-40, by_ + 12, -40, by_ + 28, -104, by_ + 32, -104, by_ + 26])
        Triangle(points=[-96, by_ + 28, -110, by_ + 52, -86, by_ + 28])
        Ellipse(pos=(-48, by_), size=(96, 40))
        Color(*C(A))
        Ellipse(pos=(-44, by_ + 8), size=(88, 30))
        Color(*C(K))
        Rectangle(pos=(-40, by_ + 14), size=(66, 4))
        Color(0.45, 0.8, 0.95, 0.85)
        Ellipse(pos=(6, by_ + 14), size=(36, 24))
        Color(1, 1, 1, 0.35)
        Ellipse(pos=(12, by_ + 28), size=(14, 6))
        Color(0.2, 0.2, 0.26, 1)
        Rectangle(pos=(-3, by_ + 38), size=(6, 12))

    def sw_drone(self, o):
        rl = o.rl
        A, B, K = PALS[o.pal]
        Color(0.2, 0.21, 0.28, 1)
        Rectangle(pos=(-30, rl), size=(60, 22))
        Color(*C(K))
        Rectangle(pos=(-30, rl + 14), size=(60, 4))
        Color(0.12, 0.13, 0.18, 1)
        Ellipse(pos=(-9, rl - 7), size=(18, 14))
        Color(0.3, 0.8, 1, 0.9)
        Ellipse(pos=(-3, rl - 3), size=(6, 6))
        Color(0.28, 0.29, 0.36, 1)
        Line(points=[-30, rl + 16, -66, rl + 30], width=3)
        Line(points=[30, rl + 16, 66, rl + 30], width=3)
        Line(points=[-24, rl + 18, -38, rl + 40], width=2.5)
        Line(points=[24, rl + 18, 38, rl + 40], width=2.5)
        Color(0.15, 0.15, 0.2, 1)
        for mx, my in ((-66, rl + 30), (66, rl + 30), (-38, rl + 40), (38, rl + 40)):
            Rectangle(pos=(mx - 5, my - 4), size=(10, 8))
        Line(points=[0, rl + 22, 0, rl + 38], width=1.5)

    def sw_ufo(self, o):
        rl = o.rl
        A, B, K = PALS[o.pal]
        Color(0.25, 0.28, 0.36, 1)
        Ellipse(pos=(-14, rl - 4), size=(28, 14))
        Color(0.35, 0.38, 0.48, 1)
        Ellipse(pos=(-40, rl + 2), size=(80, 24))
        Color(*C(B))
        Ellipse(pos=(-72, rl + 10), size=(144, 34))
        Color(*C(A))
        Ellipse(pos=(-72, rl + 18), size=(144, 28))
        Color(1, 1, 1, 0.22)
        Ellipse(pos=(-54, rl + 36), size=(90, 6))
        Color(0.5, 0.95, 0.9, 0.55)
        Ellipse(pos=(-27, rl + 34), size=(54, 40))
        Color(0.35, 0.85, 0.45, 0.95)
        Ellipse(pos=(-8, rl + 38), size=(16, 18))
        Color(0.05, 0.1, 0.05, 1)
        Ellipse(pos=(-5, rl + 45), size=(4, 5))
        Ellipse(pos=(1, rl + 45), size=(4, 5))
        Color(1, 1, 1, 0.3)
        Ellipse(pos=(-20, rl + 56), size=(14, 8))

    def swing_tex(self, o):
        """The static art of an orb carrier is baked once per (kind, palette, height) and shared."""
        key = (o.kind, o.pal, int(o.rl))
        tex = self.swtex.get(key)
        if tex is not None:
            return tex
        qs = max(0.3, self.q()['bake'] * min(self.sc, 1.5))
        fbo = Fbo(size=(int(math.ceil(320 * qs)), int(math.ceil(260 * qs))))
        with fbo:
            ClearColor(0, 0, 0, 0)
            ClearBuffers()
            PushMatrix()
            Scale(qs, qs, 1)
            Translate(160, 30, 0)
            getattr(self, 'sw_' + o.kind)(o)
            PopMatrix()
        fbo.draw()
        self.pfbo.append(fbo)
        tex = fbo.texture
        tex.mag_filter = 'linear'
        tex.min_filter = 'linear'
        self.swtex[key] = tex
        return tex

    def make_swing_cv(self, o):
        tex = self.swing_tex(o)
        cv = Canvas()
        with cv:
            PushMatrix()
            o.tr = Translate(o.ax, o.ay)
            Color(1, 1, 1, 1)
            Rectangle(texture=tex, pos=(-160, -30), size=(320, 260))
            PopMatrix()
        o.cv = cv

    def add_swing(self, x, y, force=False):
        if not force and x - self.last_swx < 300:
            return
        rng = self.rng
        tot = sum(w for _, w in SWING_KINDS)
        v = rng.uniform(0, tot)
        kind = SWING_KINDS[0][0]
        for k, w in SWING_KINDS:
            v -= w
            if v <= 0:
                kind = k
                break
        o = Swing(kind, x, y, rng)
        self.make_swing_cv(o)
        self.swings.append(o)
        self.last_swx = max(self.last_swx, x)

    def reset_world(self):
        self.rng = random.Random()
        self.world.clear()
        b0 = Bld(-300, 1500, 430, self.rng, 'concrete')   # start on a high roof
        b0.plain = True
        self.bl = [b0]
        self.swings = []
        self.last_swx = -1e9
        self.build_bld(b0)
        self.p = Player()
        self.p.y = b0.h
        self.x0 = self.p.x
        self.cam_x = self.p.x - self.W * 0.2
        self.cam_y = max(0.0, min(340.0, self.p.y + 40 - 340.0))
        self.shake = 0.0
        self.stam = 100.0
        self.cool = 0.0
        self.buf = 0.0
        self.zip_cd = 0.0
        self.fx = []
        self.tap_end = -9.0
        self.web_down = False
        self.swing_hint = None
        self.jump_touches.clear()
        self.web_touches.clear()
        self.fill_world()
        self.update_visibility()

    def start(self):
        self.reset_world()
        self.state = 'play'

    def clear_touches(self):
        self.jump_touches.clear()
        self.web_touches.clear()
        self.web_down = False

    def toggle_pause(self):
        if self.state == 'play':
            self.state = 'paused'
            self.clear_touches()
        elif self.state == 'paused':
            self.state = 'play'

    def auto_pause(self):
        if self.state == 'play':
            self.toggle_pause()

    def dist(self):
        return max(0.0, (self.p.x - self.x0) / 25.0)

    def speed(self):
        return min(RUN_MAX, RUN0 + self.dist() * 0.08)

    def fill_world(self, budget=99):
        n = 0
        while n < budget and self.bl[-1].x + self.bl[-1].w < self.cam_x + self.W + 900:
            self.spawn()      # during play at most one spawn (one bake) per frame
            n += 1

    def update_visibility(self):
        left = self.cam_x - 30.0
        right = self.cam_x + self.W + 30.0
        bottom = self.cam_y
        top = self.cam_y + VH
        for b in self.bl:
            visible = (b.x - 8.0 <= right and b.x + b.w + 8.0 >= left and b.h + 190.0 >= bottom)
            if visible and not b.visible and b.cv is not None:
                self.world.add(b.cv)
                b.visible = True
            elif not visible and b.visible and b.cv is not None:
                self.world.remove(b.cv)
                b.visible = False
        for o in self.swings:
            r = 150.0
            visible = (left - r <= o.ax <= right + r and
                       bottom - r <= o.ay <= top + r)
            if visible and not o.visible and o.cv is not None:
                self.world.add(o.cv)
                o.visible = True
            elif not visible and o.visible and o.cv is not None:
                self.world.remove(o.cv)
                o.visible = False

    def pick_style(self, rng, w, nh, last):
        if w >= 600 and nh <= 270:
            opts = (('industrial', 40), ('concrete', 20), ('brick', 14), ('apartment', 10),
                    ('neon', 8), ('deco', 8))
        elif nh >= 300:
            opts = (('glass', 34), ('deco', 24), ('concrete', 16), ('brick', 10),
                    ('neon', 8), ('apartment', 8))
        elif w < 200:
            opts = (('brick', 30), ('apartment', 30), ('neon', 20), ('deco', 10), ('concrete', 10))
        else:
            opts = (('brick', 24), ('apartment', 22), ('concrete', 16), ('neon', 12),
                    ('glass', 10), ('deco', 8), ('industrial', 8 if w >= 300 else 0))
        opts = opts + (('loft', 12), ('ribbon', 12 if nh >= 250 else 6))
        tot = sum(o[1] for o in opts)
        for _ in range(2):
            v = rng.uniform(0, tot)
            pick = opts[0][0]
            for name, wt in opts:
                v -= wt
                if v <= 0 and wt > 0:
                    pick = name
                    break
            if pick != last.style or rng.random() < 0.4:
                break
        return pick

    def spawn_group(self, base):
        """Multi-part structures: stair-steps up / down, twin towers with an alley, pillar fields."""
        rng = self.rng
        U = rng.uniform
        mode = rng.choice(('up', 'down', 'twin', 'pillars', 'up', 'down'))
        n = rng.choice((2, 3)) if mode in ('up', 'down') else (1 if mode == 'twin' else 3)
        last = base
        for i in range(n):
            if mode == 'up':
                gap, w, nh = 0.0, U(110, 190), last.h + U(50, 95)
            elif mode == 'down':
                gap, w, nh = 0.0, U(110, 190), last.h - U(50, 100)
            elif mode == 'twin':
                gap, w, nh = U(45, 70), U(150, 260), last.h + U(-30, 130)
            else:
                gap, w = U(95, 150), U(85, 115)
                nh = last.h + (U(80, 160) if i % 2 == 0 else -U(50, 110))
            nh = max(HMIN, min(HMAX, nh))
            nb = Bld(last.x + last.w + gap, w, nh, rng, self.pick_style(rng, w, nh, last))
            self.bl.append(nb)
            self.build_bld(nb)
            last = nb

    def spawn(self):
        last, rng = self.bl[-1], self.rng
        U = rng.uniform
        md = (last.x - self.x0) / 25.0
        dd = min(1.0, md / 3000.0)
        spd = min(RUN_MAX, RUN0 + md * 0.08)
        jmax = spd * 0.8 - 40
        swing = rng.random() < 0.45 + 0.3 * dd
        if swing:
            gap = U(jmax + 120, jmax + 320 + 380 * dd)      # longer holes
        else:
            gap = U(120, jmax * 0.97)
        r = rng.random()
        if swing:
            kind = 'wide' if r < 0.38 else ('huge' if r < 0.5 else ('mid' if r < 0.8 else 'block'))
        else:
            if r < 0.09: kind = 'tower'
            elif r < 0.15: kind = 'skinny'
            elif r < 0.21: kind = 'shed'
            elif r < 0.29: kind = 'huge'
            elif r < 0.56: kind = 'wide'
            elif r < 0.83: kind = 'mid'
            else: kind = 'block'
        if kind == 'tower':
            w, nh = U(150, 230), last.h + U(150, 260)
        elif kind == 'skinny':
            w, nh = U(105, 150), last.h + U(110, 300)
        elif kind == 'shed':
            w, nh = U(130, 190), last.h + U(-110, 30)
        elif kind == 'huge':
            w, nh = U(1100, 1500), U(HMIN, 250)
        elif kind == 'wide':
            w, nh = U(520, 1100), U(HMIN, 300)
        elif kind == 'mid':
            w, nh = U(300, 520), last.h + U(-160, 90)
        else:
            w, nh = U(190, 300), last.h + U(-120, 120)
        nh = max(HMIN, min(HMAX, nh))
        if swing:
            nh = min(nh, last.h + 40)
        elif 40 < nh - last.h <= 150:
            gap = min(gap, jmax * 0.7)
        ge = last.x + last.w
        style = self.pick_style(rng, w, nh, last)
        nb = Bld(ge + gap, w, nh, rng, style)
        hi = max(last.h, nh)
        if swing:
            n = int(gap // 330) + 1
            for i in range(n):
                self.add_swing(ge + gap * (i + 0.4) / n + 30, min(860.0, hi + U(330, 410)), True)
        self.bl.append(nb)
        self.build_bld(nb)
        if not swing and w < 700 and rng.random() < 0.3:
            self.spawn_group(nb)
        if w >= 600 and rng.random() < 0.55:
            n = int(w // 380)
            for i in range(n):
                self.add_swing(nb.x + w * (i + 0.5) / n, min(860.0, nh + U(330, 410)))

    def on_touch_down(self, t):
        lx, ly = t.x / self.sc, t.y / self.sc
        cxm = self.W / 2
        if self.state == 'main_menu':
            if math.hypot(lx - cxm, ly - 330) <= 92:
                self.start()
            elif math.hypot(lx - (cxm + 185), ly - 330) <= 58:
                self.state = 'settings'
            return True
        elif self.state == 'settings':
            if math.hypot(lx - cxm, ly - 150) <= 50:
                self.state = 'main_menu'
            elif cxm - 170 <= lx <= cxm + 170:
                for _lb, key, ry, _on in self.settings_rows():
                    if ry <= ly <= ry + 62:
                        self.toggle_setting(key)
                        break
            return True

        if self.state in ('play', 'paused') and lx > self.W - 120 and ly > 610:
            self.toggle_pause()
            return True
        elif self.state == 'paused':
            if math.hypot(lx - cxm, ly - 340) <= 74:
                self.state = 'play'
            elif math.hypot(lx - (cxm - 150), ly - 340) <= 60:
                self.start()
            elif math.hypot(lx - (cxm + 150), ly - 340) <= 60:
                self.go_menu()
        elif self.state == 'dead':
            if self.dead_t > 0.6:
                if math.hypot(lx - (cxm - 90), ly - 235) <= 56:
                    self.start()
                elif math.hypot(lx - (cxm + 90), ly - 235) <= 56:
                    self.go_menu()
        elif self.state == 'play':
            jump_button = math.hypot(lx - 125.0, ly - 115.0) <= 88.0
            web_button = math.hypot(lx - (self.W - 125.0), ly - 115.0) <= 88.0
            if jump_button or (lx < self.W * 0.5 and ly < 250):
                self.jump_touches.add(t.uid)
                self.on_jump_press()
            elif web_button or (lx >= self.W * 0.5 and ly < 250):
                self.web_touches.add(t.uid)
                self.web_down = True
                self.on_web_press()
            elif lx < self.W * 0.5:
                self.jump_touches.add(t.uid)
                self.on_jump_press()
            else:
                self.web_touches.add(t.uid)
                self.web_down = True
                self.on_web_press()
        return True

    def on_touch_up(self, t):
        if t.uid in self.jump_touches:
            self.jump_touches.discard(t.uid)
            if not self.jump_touches and self.state == 'play':
                self.on_jump_release()
        if t.uid in self.web_touches:
            self.web_touches.discard(t.uid)
            if not self.web_touches:
                self.web_down = False
                if self.state == 'play':
                    self.on_web_release()
        return True

    def add_splat(self, obj, size=17.0):
        """Classic Spider-Man web splat. Follows the object it stuck to."""
        self.fx.append(['asplat', obj.ax, obj.ay, 0.0, 0.0, 0.0, 0.9, size,
                        (random.uniform(0.0, 1.5), obj)])

    def fx_add(self, kind, x, y, vx=0.0, vy=0.0, life=0.4, size=6.0, col=(1, 1, 1)):
        if not self.settings['particles']:
            return
        cap = self.q()['fx']
        if len(self.fx) > cap:
            del self.fx[:max(5, cap // 6)]
        self.fx.append([kind, x, y, vx, vy, 0.0, life, size, col])

    def burst(self, x, y, n, col, speed=240.0, up=0.0):
        if not self.settings['particles']:
            return
        for _ in range(n):
            a = random.uniform(0, 6.283)
            s = random.uniform(0.3, 1.0) * speed
            self.fx_add('spark', x, y, math.cos(a) * s, math.sin(a) * s + up,
                        random.uniform(0.2, 0.45), 2, col)

    def dust(self, x, y, n, spread=120.0, size=6.0, life=0.45):
        if not self.settings['particles']:
            return
        for _ in range(n):
            self.fx_add('dust', x + random.uniform(-10, 10), y + random.uniform(0, 3),
                        random.uniform(-spread, spread), random.uniform(10, 60),
                        life * random.uniform(0.7, 1.2), size * random.uniform(0.7, 1.3), (0.78, 0.72, 0.84))

    def step_fx(self, dt):
        keep = []
        for f in self.fx:
            f[5] += dt
            if f[5] >= f[6]:
                continue
            f[1] += f[3] * dt
            f[2] += f[4] * dt
            if f[0] == 'spark':
                f[4] -= 600 * dt
            elif f[0] == 'dust':
                k = max(0.0, 1 - 2.5 * dt)
                f[3] *= k
                f[4] = f[4] * k + 14 * dt
            keep.append(f)
        self.fx = keep

    def jump(self):
        p = self.p
        p.vy = JUMP
        p.vx = max(p.vx, self.speed())
        if p.mode == 'run':
            self.dust(p.x, p.y + 1, 6, 130, 6)
            p.flip, p.rot = True, 0.0
        p.mode = 'air'
        p.coyote, p.cut, p.wall = 0.0, True, None
        self.buf = 0.0

    def on_jump_press(self):
        p = self.p
        if p.mode == 'run' or (p.mode == 'air' and p.coyote > 0 and p.wall is None):
            self.jump()
        elif p.mode == 'air':
            self.buf = 0.08

    def on_jump_release(self):
        p = self.p
        if p.mode == 'air' and p.cut and p.vy > 150:
            p.vy *= 0.5
            p.cut = False

    def on_web_press(self):
        p = self.p
        m = p.mode
        dbl = (self.tm - self.tap_end) < 0.28
        self.press_time = self.tm
        if dbl and (m == 'swing' or (m == 'air' and p.wall is None and p.coyote <= 0)):
            self.tap_end = -9.0
            if self.start_zip():
                return
        if m == 'air':
            if p.wall is not None:
                if self.cool <= 0 and self.stam > 5:
                    p.mode = 'climb'
                    p.flip = False
            elif p.coyote <= 0 and self.cool <= 0 and self.stam > 3:
                self.try_attach()
        elif m == 'climb':
            p.mode = 'air'

    def on_web_release(self):
        if self.tm - self.press_time < 0.22:
            self.tap_end = self.tm
        else:
            self.tap_end = -9.0
        if self.p.mode == 'swing':
            self.detach()

    def detach(self):
        p = self.p
        if p.mode == 'swing':
            p.rel_t = 0.3
            p.rel_anchor = (p.anchor.ax, p.anchor.ay)
            p.mode = 'air'
            if p.vy > 60 and math.hypot(p.vx, p.vy) > 380:
                p.flip, p.rot = True, 0.0
            self.burst(p.anchor.ax, p.anchor.ay, 5, (1, 1, 1), 90, 40)

    def aim_zip(self):
        """Straight-line zip target, along the current travel direction (clamped)."""
        p = self.p
        y0 = p.y + 40
        ang = math.atan2(p.vy, p.vx) if p.vx > 1 else 0.25
        ang = max(-0.3, min(0.65, ang))
        tx = p.x + math.cos(ang) * ZIP_DIST
        ty = max(STREET + 50.0, y0 + math.sin(ang) * ZIP_DIST)
        return (tx, ty, 'line')

    def start_zip(self):
        p = self.p
        if self.zip_cd > 0 or self.cool > 0 or self.stam < 25:
            return False
        tgt = self.aim_zip()
        dx, dy = tgt[0] - p.x, tgt[1] - (p.y + 40)
        d = math.hypot(dx, dy) or 1.0
        p.vx, p.vy = dx / d * ZIP_V0, dy / d * ZIP_V0
        p.mode = 'zip'
        p.zip_target = tgt
        p.zip_t = 0.0
        p.cut = False
        p.wall = None
        p.rel_t = 0.0
        p.flip = False
        self.stam -= 25
        self.zip_cd = 1.2
        self.fx_add('ring', p.x, p.y + 40, 0, 0, 0.3, 10)
        self.burst(p.x, p.y + 40, 8, (0.5, 1, 1), 220)
        return True

    def collide(self, p, prev_y, spd):
        p.wall = None
        res = None
        for b in self.bl:
            if b.x > p.x + 120:
                break
            if b.x + b.w < p.x - 120:
                continue
            if p.x + HW > b.x - 0.5 and p.x - HW < b.x + b.w and p.y < b.h:
                if prev_y >= b.h - 0.5 and p.vy <= 0:
                    p.y, p.vy = b.h, 0.0
                    p.vx = max(spd, min(p.vx, MAX_CARRY))
                    p.mode, p.wall, p.cut = 'run', None, False
                    return 'land'
                if p.x < b.x + b.w * 0.5:
                    if b.h - p.y < 42:
                        p.y, p.x, p.vy, p.vx = b.h, b.x + HW + 8, 0.0, spd
                        p.mode, p.wall, p.cut = 'run', None, False
                        return 'land'
                    p.x, p.vx, p.wall = b.x - HW, 0.0, b
                    res = 'wall'
                else:
                    p.x = b.x + b.w + HW
        return res

    def swing_candidate(self):
        p = self.p
        best, bd = None, 1e9
        for o in self.swings:
            dx, dy = o.ax - p.x, o.ay - (p.y + 40)
            if dx > -40 and dy > 60 and dx < SWING_REACH_X:
                d = math.hypot(dx, dy)
                if d < SWING_REACH_D and d < bd:
                    best, bd = o, d
        return best, bd

    def try_attach(self):
        p = self.p
        best, bd = self.swing_candidate()
        if best is None:
            return
        nx, ny = (p.x - best.ax) / bd, (p.y + 40 - best.ay) / bd
        tx, ty = -ny, nx
        sp = math.hypot(p.vx, p.vy)
        vt = p.vx * tx + p.vy * ty
        sgn = 1.0 if vt >= 0 else -1.0
        mag = max(abs(vt), 0.85 * sp)
        if tx * sgn < 0:
            sgn = -sgn
        p.vx, p.vy = tx * sgn * mag, ty * sgn * mag
        p.anchor, p.L, p.mode, p.cut = best, bd, 'swing', False
        p.rel_t = 0.0
        p.flip = False
        p.web_t, p.web_hit = 0.0, False

    def on_land(self, vy):
        p = self.p
        k = min(1.0, vy / 700.0)
        p.land_t = 0.10 + 0.12 * k
        p.flip, p.rot = False, 0.0
        self.dust(p.x, p.y + 1, int(4 + 8 * k), 90 + 160 * k, 5 + 5 * k, 0.5)
        if k > 0.4:
            self.fx_add('shock', p.x, p.y + 2, 0, 0, 0.32, 8)
        if vy > 650:
            self.shake = max(self.shake, 3.0 + 4.0 * k)

    def die(self):
        if self.state != 'play':
            return
        self.state = 'dead'
        self.dead_t = 0.0
        self.clear_touches()
        self.burst(self.p.x, max(self.p.y, STREET) + 20, 22, (1, 0.3, 0.3), 320, 120)
        self.burst(self.p.x, max(self.p.y, STREET) + 20, 10, (1, 1, 1), 200, 80)
        self.shake = 9.0
        d = int(self.dist())
        if d > self.best:
            self.best = d
            self.save_best()

    def step(self, dt):
        p = self.p
        self.cool = max(0.0, self.cool - dt)
        self.buf = max(0.0, self.buf - dt)
        self.zip_cd = max(0.0, self.zip_cd - dt)
        p.rel_t = max(0.0, p.rel_t - dt)
        p.land_t = max(0.0, p.land_t - dt)
        p.web_t += dt
        spd = self.speed()
        m = p.mode
        if m == 'run' and self.buf > 0:
            self.jump()
            m = p.mode
        prev_y = p.y
        pre_vy = 0.0

        if m == 'run':
            if p.vx <= spd:
                p.vx = spd
            else:
                p.vx = max(spd, p.vx - 150 * dt)
            p.x += p.vx * dt
            bf = self.bld_under(p.x + HW)
            if bf is not None and bf.h > p.y + 0.5:          # taller block right in front
                if bf.h - p.y < 42:
                    p.y = bf.h
                else:
                    p.x = bf.x - HW - 0.5
                    p.vx = 0.0
                    p.mode, p.vy, p.coyote, p.cut = 'air', 0.0, 0.0, False
                    p.wall = bf
            bu = self.bld_under(p.x)
            if bu is None or bu.h < p.y - 0.5:               # gap, or stepped down
                p.mode, p.vy, p.coyote, p.cut = 'air', 0.0, 0.12, False
            self.stam = min(100.0, self.stam + 32 * dt)
            p.dust_t -= dt
            if p.dust_t <= 0 and p.mode == 'run':
                p.dust_t = 0.07
                self.fx_add('dust', p.x - 12, p.y + 2, -70 - random.uniform(0, 50), random.uniform(8, 30),
                            0.38, random.uniform(4, 7), (0.78, 0.72, 0.84))
        elif m == 'air':
            p.coyote = max(0.0, p.coyote - dt)
            p.vy += GRAV * dt
            if p.wall is not None and p.vy < -230:
                p.vy = -230
            p.x += p.vx * dt
            p.y += p.vy * dt
            if p.flip:
                p.rot += 9.5 * dt
                if p.rot >= 6.2832:
                    p.flip, p.rot = False, 0.0
            pre_vy = abs(p.vy)
            self.collide(p, prev_y, spd)
            if p.wall is not None:
                p.flip, p.rot = False, 0.0
                p.wall_t -= dt
                if p.wall_t <= 0:
                    p.wall_t = 0.05
                    self.fx_add('dust', p.x + 8, p.y + random.uniform(10, 50), 20, 10, 0.3, 4, (0.8, 0.75, 0.85))
            self.stam = min(100.0, self.stam + (18 if p.wall is None else 6) * dt)
            if (p.mode == 'air' and self.web_down and p.wall is None and p.coyote <= 0
                    and self.cool <= 0 and self.stam > 3):
                self.try_attach()
        elif m == 'climb':
            w = p.wall
            p.vx = p.vy = 0.0
            p.y += CLIMB * dt
            self.stam -= 20 * dt
            p.wall_t -= dt
            if w is None:
                p.mode = 'air'
            elif p.y >= w.h - 2:
                p.y, p.x, p.vx = w.h, w.x + HW + 8, spd
                p.mode, p.wall = 'run', None
                self.dust(p.x, p.y + 1, 5, 90, 5)
            elif self.stam <= 0:
                self.stam, self.cool = 0.0, 2.0
                p.mode = 'air'
        elif m == 'swing':
            ax, ay = p.anchor.ax, p.anchor.ay
            if not p.web_hit and p.web_t >= 0.1:
                p.web_hit = True
                self.add_splat(p.anchor)
                self.burst(ax, ay, 4, (1, 1, 1), 100)
            p.vy += GRAV * dt
            sp0 = math.hypot(p.vx, p.vy)
            if sp0 > 1:
                p.vx += p.vx / sp0 * 220 * dt
                p.vy += p.vy / sp0 * 220 * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            dx, dy = p.x - ax, p.y + 40 - ay
            d = math.hypot(dx, dy) or 1.0
            if d > p.L:
                nx, ny = dx / d, dy / d
                p.x = ax + nx * p.L
                p.y = ay + ny * p.L - 40
                vr = p.vx * nx + p.vy * ny
                if vr > 0:
                    p.vx -= nx * vr
                    p.vy -= ny * vr
            sp = math.hypot(p.vx, p.vy)
            if sp > MAX_SWING:
                p.vx *= MAX_SWING / sp
                p.vy *= MAX_SWING / sp
            self.stam -= 10 * dt
            pre_vy = abs(p.vy)
            r = self.collide(p, prev_y, spd)
            if p.mode == 'swing' and r == 'wall':
                if self.cool <= 0 and self.stam > 5:
                    p.mode = 'climb'
                    p.rel_t = 0.0
                else:
                    self.detach()
            if self.stam <= 0:
                self.stam, self.cool = 0.0, 2.0
                if p.mode == 'swing':
                    self.detach()
        elif m == 'zip':
            p.zip_t += dt
            v = min(ZIP_VMAX, ZIP_V0 + p.zip_t * 6000)
            tx, ty = p.zip_target[0], p.zip_target[1]
            dx, dy = tx - p.x, ty - (p.y + 40)
            d = math.hypot(dx, dy)
            ux, uy = (dx / d, dy / d) if d > 1e-6 else (1.0, 0.0)
            mv = v * dt
            ending = d <= mv + 4
            if ending:
                p.x, p.y = tx, ty - 40
            else:
                p.x += ux * mv
                p.y += uy * mv
                p.vx, p.vy = ux * v, uy * v
                self.fx_add('ghost', p.x, p.y, 0, 0, 0.22, math.atan2(uy, ux), (0.5, 0.85, 1.0))
                self.fx_add('spark', p.x - ux * 14, p.y + 40 - uy * 14, random.uniform(-40, 40),
                            random.uniform(-40, 40), 0.25, 2, (0.5, 1, 1))
            pre_vy = abs(p.vy)
            r = self.collide(p, prev_y, spd)
            if p.mode == 'run':                      # landed on a roof mid-zip
                p.zip_target = None
                self.fx_add('ring', p.x, p.y + 40, 0, 0, 0.3, 10)
            elif r == 'wall':                        # slammed into a wall: cling to it
                p.zip_target = None
                p.mode = 'air'
                p.vy = max(p.vy, 0.0) * 0.3
                p.coyote = 0.0
                self.burst(p.x + HW, p.y + 40, 8, (0.5, 1, 1), 200)
            elif ending:
                sp2 = min(MAX_CARRY, v * 0.6)
                p.vx, p.vy = ux * sp2, uy * sp2
                p.mode = 'air'
                p.coyote = 0.0
                p.zip_target = None
                self.fx_add('ring', tx, ty, 0, 0, 0.3, 10)
                self.burst(tx, ty, 10, (0.5, 1, 1), 260)

        if m in ('air', 'swing', 'zip') and p.mode == 'run':
            self.on_land(max(pre_vy, 200.0))
        elif m == 'climb' and p.mode == 'run':
            p.land_t = 0.1

        if self.cool > 0:
            self.stam = min(100.0, self.stam + 30 * dt)

        if p.y < STREET:
            self.die()

        self.cam_x = p.x - self.W * 0.2
        tgt = max(0.0, min(340.0, p.y + 40 - 340.0))
        self.cam_y += (tgt - self.cam_y) * min(1.0, dt * 3.5)
        self.fill_world(1)
        self.cleanup()

    def bld_under(self, x):
        for b in self.bl:
            if b.x <= x <= b.x + b.w:
                return b
        return None

    def cleanup(self):
        while len(self.bl) > 2 and self.bl[0].x + self.bl[0].w < self.cam_x - 300:
            b = self.bl.pop(0)
            if b.visible and b.cv is not None:
                self.world.remove(b.cv)
                b.visible = False
            b.cv = None
            b.fbo = None
        while self.swings and self.swings[0].ax < self.cam_x - 420:
            o = self.swings.pop(0)
            if o.visible and o.cv is not None:
                self.world.remove(o.cv)
                o.visible = False
            o.cv = None

    def update_objs(self):
        t = self.tm
        lo, hi = self.cam_x - 450.0, self.cam_x + self.W + 750.0
        for o in self.swings:
            if o.bx < lo or o.bx > hi:
                continue
            o.ax = o.bx + math.sin(t * 0.5 + o.ph) * o.sx
            o.ay = o.by + math.sin(t * 0.8 + o.ph * 1.3) * o.sy
            o.tr.x, o.tr.y = o.ax, o.ay

    def sim(self, dt):
        self.tm += dt
        self.update_objs()
        if self.state == 'play':
            self.step(dt)
        else:
            if self.state == 'dead':
                self.dead_t += dt
            self.fill_world(1)
        if self.state != 'paused':
            self.step_fx(dt)
        self.shake *= max(0.0, 1 - 11 * dt)

    def update(self, dt):
        # Real frame time, split into small physics steps: 25 fps and 120 fps play the same.
        dt = min(dt, 0.1)
        self.dt = dt
        self.frame += 1
        self.fps_t += dt
        self.fps_n += 1
        if self.fps_t >= 0.5:
            self.fps_val = self.fps_n / self.fps_t
            self.fps_t, self.fps_n = 0.0, 0
        n = max(1, int(math.ceil(dt / MAX_STEP - 1e-6)))
        h = dt / n
        for _ in range(n):
            self.sim(h)
        self.update_visibility()
        if self.state != 'paused':
            self.update_anim(dt)
        p = self.p
        self.swing_hint = None
        if (self.state == 'play' and p.mode == 'air' and p.wall is None and p.coyote <= 0
                and self.cool <= 0 and self.stam > 3):
            self.swing_hint = self.swing_candidate()[0]
        if self.state in ('play', 'paused'):
            tgt = CLIMB if p.mode == 'climb' else math.hypot(p.vx, p.vy)
        else:
            tgt = 0.0
        self.shown += (tgt - self.shown) * min(1.0, dt * 10)
        self.render()

    def render(self):
        sh = self.shake
        ox = random.uniform(-sh, sh) if sh > 0.3 else 0.0
        oy = random.uniform(-sh, sh) if sh > 0.3 else 0.0
        self.cam_tr.x = -self.cam_x + ox
        self.cam_tr.y = -self.cam_y + oy
        for tr, par, period in self.layers:
            tr.x = -((self.cam_x * par) % period)
            tr.y = -self.cam_y * par * 0.5
        self.draw_sky()
        self.draw_back()
        self.draw_amb()
        self.draw_dyn()
        self.draw_hud()

    # ------------------------------------------------------------------
    # Spider-Man animation: named poses blended smoothly between states
    # ------------------------------------------------------------------
    def pose_name(self):
        p = self.p
        if self.state in ('main_menu', 'settings'):
            return 'idle'
        m = p.mode
        if m in ('run', 'climb', 'swing', 'zip'):
            return m
        if p.wall is not None:
            return 'wall'
        if p.flip:
            return 'tuck'
        if p.vy > 120:
            return 'air_up'
        if p.vy < -120:
            return 'air_fall'
        return 'air_mid'

    def pose_target(self, name):
        """Local pose targets (feet / hands relative to the feet position); the rig solves the joints."""
        p = self.p
        c = p.cyc
        if name == 'idle':
            b = math.sin(self.tm * 2.4)
            return _pose(f1x=-6, f1y=2, f2x=7, f2y=2, h1x=7, h1y=21 + b, h2x=-5, h2y=20 + b,
                         lean=1.0, sq=0.955 + 0.02 * b)
        if name == 'run':
            s1, cs = math.sin(c), math.cos(c)
            a1 = -s1                                  # arms swing against the legs
            return _pose(f1x=s1 * 11, f1y=max(0.0, cs) * 9,
                         f2x=-s1 * 11, f2y=max(0.0, -cs) * 9,
                         h1x=5 + a1 * 10, h1y=23 + max(0.0, a1) * 7,
                         h2x=5 - a1 * 10, h2y=23 + max(0.0, -a1) * 7,
                         lean=5.0, sq=0.93 + 0.07 * abs(cs))
        if name == 'air_up':       # leap: lead knee up, reaching forward
            return _pose(f1x=9, f1y=14, f2x=-9, f2y=5, h1x=15, h1y=44, h2x=-9, h2y=33, lean=3.0)
        if name == 'air_mid':      # apex: knees tucked, arms out
            return _pose(f1x=8, f1y=11, f2x=-1, f2y=9, h1x=15, h1y=32, h2x=-10, h2y=32, lean=2.0)
        if name == 'air_fall':     # dropping: legs reach for the roof, arms up for balance
            return _pose(f1x=7, f1y=4, f2x=-5, f2y=7, h1x=15, h1y=47, h2x=-12, h2y=44, lean=1.0)
        if name == 'tuck':         # flip: curled into a ball
            return _pose(f1x=7, f1y=15, f2x=2, f2y=12, h1x=10, h1y=21, h2x=6, h2y=19, lean=4.0, sq=0.9)
        if name == 'wall':
            return _pose(f1x=13, f1y=7, f2x=12, f2y=18, h1x=17, h1y=44, h2x=16, h2y=35, lean=6.0)
        if name == 'climb':
            k = math.sin(c)
            return _pose(f1x=13, f1y=6 + k * 5, f2x=12, f2y=17 - k * 5,
                         h1x=17, h1y=44 + k * 5, h2x=16, h2y=34 - k * 5, lean=6.0)
        if name == 'swing':
            sg = math.tanh(p.vx / 120.0)
            u = max(0.0, min(1.0, 0.5 + p.vy / 900.0))   # rising = knees tuck, falling = stretch out
            wob = math.sin(self.tm * 5.0) * 1.5
            h1x, h1y = 12.0, 54.0
            a = p.anchor
            if a is not None:
                # the web hand sits exactly on the line (body pivot -> anchor), so the strand
                # leaves the glove and reaches the hook in a perfectly straight line
                pvx, pvy = p.x, p.y + 40.0
                wx, wy = a.ax - pvx, a.ay - pvy
                d = math.hypot(wx, wy) or 1.0
                tx, ty = pvx + wx / d * 13.0, pvy + wy / d * 13.0
                ox, oy = p.x, p.y + p.org
                th = math.radians(-p.ang)
                ct, st = math.cos(th), math.sin(th)
                ddx, ddy = tx - ox, ty - oy
                h1x = ox + ddx * ct - ddy * st - p.x
                h1y = oy + ddx * st + ddy * ct - p.y
            return _pose(f1x=-(14 - 8 * u) * sg, f1y=3 + 9 * u + wob,
                         f2x=-(7 - 3 * u) * sg, f2y=1 + 5 * u - wob,
                         h1x=h1x, h1y=h1y,
                         h2x=-10 * sg + 3, h2y=30 - 6 * u,
                         lean=-1.5 * sg, sq=0.98)
        # zip: superhero flight, body axis along the (straight) travel line
        return _pose(f1x=-2, f1y=3, f2x=2, f2y=1, h1x=3, h1y=57, h2x=-1, h2y=54, lean=0.0)

    def update_anim(self, dt):
        p = self.p
        name = self.pose_name()
        m = p.mode
        rate = 14.0 + p.vx * 0.02 if name == 'run' else (14.0 if name == 'climb' else 6.0)
        p.cyc += rate * dt
        # --- body rotation first (the swing hand needs the final angle)
        rate_a = 14.0
        tang = 0.0
        if m == 'swing' and p.anchor is not None:
            d = math.hypot(p.x - p.anchor.ax, p.y + 40 - p.anchor.ay) or 1.0
            tang = math.degrees(math.asin(max(-1.0, min(1.0, (p.x - p.anchor.ax) / d)))) * 0.8
        elif m == 'zip':
            tang = math.degrees(math.atan2(p.vy, p.vx)) - 90.0
            rate_a = 24.0
        elif p.flip and m == 'air':
            tang = math.degrees(p.rot)
            rate_a = 28.0
        diff = ((tang - p.ang + 180.0) % 360.0) - 180.0
        step = diff * (1.0 - math.exp(-dt * rate_a))
        vmax = (1500.0 if m == 'zip' else 1000.0) * dt      # cap turn speed so nothing snaps
        p.ang += max(-vmax, min(vmax, step))
        p.ang = ((p.ang + 180.0) % 360.0) - 180.0
        p.org += ((40.0 if m == 'swing' else 20.0) - p.org) * (1.0 - math.exp(-dt * 20.0))
        # --- smooth pose blending
        if name != p.pose_name:
            p.prev = dict(p.pose) if p.pose else None
            old = p.pose_name
            p.pose_name = name
            p.tr_len = 0.16 if old == 'zip' else POSE_BLEND.get(name, 0.12)
            p.tr = p.tr_len
        tgt = self.pose_target(name)
        if p.tr > 0 and p.prev:
            p.tr = max(0.0, p.tr - dt)
            u = 1.0 - p.tr / p.tr_len
            u = u * u * (3 - 2 * u)
            p.pose = {k: p.prev[k] + (tgt[k] - p.prev[k]) * u for k in tgt}
        else:
            p.pose = tgt
        # --- landing squash, eased in and out
        sqt = 1.0 - 0.18 * min(1.0, p.land_t / 0.2) if p.land_t > 0 else 1.0
        p.sq += (sqt - p.sq) * (1.0 - math.exp(-dt * (40.0 if sqt < p.sq else 14.0)))

    def hand_pos(self):
        """World position of the web glove (rig hand, rotated with the body)."""
        p = self.p
        hx, hy = self.rig.hand
        a = math.radians(p.ang)
        ox, oy = p.x, p.y + p.org
        dx, dy = hx - ox, hy - oy
        ca, sa = math.cos(a), math.sin(a)
        return ox + dx * ca - dy * sa, oy + dx * sa + dy * ca

    def draw_dyn(self):
        p = self.p
        if p.pose is None:
            self.update_anim(0.0)
        show = self.state != 'dead' or self.dead_t < 0.05
        # the player: just update numbers on the retained instructions
        po = dict(p.pose)
        po['sq'] = po['sq'] * p.sq
        self.rig.apply(p.x, p.y, po, p.ang, p.org, show)
        c = self.web_cv
        web_on = show and ((p.mode == 'swing' and p.anchor is not None) or
                           (p.mode == 'zip' and p.zip_target is not None) or
                           (p.rel_t > 0 and p.rel_anchor is not None))
        if web_on or self._web_dirty:          # nothing to redraw while no web is out
            c.clear()
            if web_on:
                with c:
                    hx, hy = self.hand_pos()
                    if p.mode == 'swing' and p.anchor is not None:
                        fr = min(1.0, p.web_t / 0.1) if not p.web_hit else 1.0
                        self.draw_web(hx, hy, p.anchor.ax, p.anchor.ay, frac=fr, thick=1.8)
                    elif p.mode == 'zip' and p.zip_target is not None:
                        self.draw_web(hx, hy, p.zip_target[0], p.zip_target[1], thick=2.0)
                    elif p.rel_t > 0 and p.rel_anchor is not None:
                        self.draw_web(hx, hy, p.rel_anchor[0], p.rel_anchor[1], alpha=p.rel_t / 0.3,
                                      sag=6.0 * (1 - p.rel_t / 0.3), thick=1.4)
            self._web_dirty = bool(web_on)
        if self.fx or self._fx_dirty:
            f = self.fx_cv
            f.clear()
            with f:
                self.draw_fx()
            self._fx_dirty = bool(self.fx)

    def draw_buttons(self):
        r = 66.0
        cy = 115.0
        jx = 125.0
        down = bool(self.jump_touches)
        Color(0.2, 0.14, 0.02, 0.92 if down else 0.72)
        Ellipse(pos=(jx - r, cy - r), size=(2 * r, 2 * r))
        Color(1, 0.8, 0.2, 0.95)
        Line(circle=(jx, cy, r), width=3)
        Color(1, 0.9, 0.5, 1)
        Line(points=[jx - 24, cy - 6, jx, cy + 18, jx + 24, cy - 6], width=5)
        Line(points=[jx - 24, cy - 28, jx, cy - 4, jx + 24, cy - 28], width=5)
        self.txt('JUMP', 18, (1, 1, 1, 0.95), jx, 22, 'c')

        wx = self.W - 125.0
        Color(0.04, 0.1, 0.32, 0.92 if self.web_down else 0.72)
        Ellipse(pos=(wx - r, cy - r), size=(2 * r, 2 * r))
        Color(0.3, 0.6, 1, 0.98)
        Line(circle=(wx, cy, r), width=3)
        if self.cool > 0:
            Color(0.5, 0.5, 0.55, 1)
        else:
            Color(0.85, 0.95, 1, 1)
        for k in range(8):
            a = k * math.pi / 4
            Line(points=[wx, cy, wx + math.cos(a) * r * 0.8,
                         cy + math.sin(a) * r * 0.8], width=1.3)
        for f in (0.3, 0.55, 0.8):
            pts = []
            for k in range(8):
                a = k * math.pi / 4
                pts.extend([wx + math.cos(a) * r * f, cy + math.sin(a) * r * f])
            Line(points=pts, close=True, width=1.3)
        self.txt('WEB / ZIP', 15, (1, 1, 1, 0.95), wx, 22, 'c')

    def draw_hud(self):
        c = self.hud
        st = self.state
        key = (st, int(self.dist()), self.best, int(self.shown * 0.1) // 2, int(self.stam),
               self.cool > 0, bool(self.jump_touches), self.web_down,
               int(min(1.0, self.dead_t) * 20) if st == 'dead' else 0,
               int(round(self.fps_val)) if self.settings['show_fps'] else 0,
               tuple(self.settings.values()), self.W)
        if key == self.hud_key:
            return
        self.hud_key = key
        c.clear()
        W = self.W
        with c:
            if st in ('play', 'paused', 'dead'):
                d = int(self.dist())
                self.txt(str(d), 38, (1, 1, 1, 1), 22, 664)
                self.txt('M', 20, (1, 1, 1, 0.7), 30 + 24 * len(str(d)), 666)
                self.txt('BEST ' + str(max(self.best, d)), 14, (1, 0.9, 0.5, 0.9), 24, 644)
                spd = (int(self.shown * 0.1) // 2) * 2
                self.txt(str(spd) + ' KM/H', 16, (0.6, 1, 1, 0.95), W - 24, 626, 'r')
                bw = 160.0
                bx = W - 24 - bw
                Color(0, 0, 0, 0.45)
                Rectangle(pos=(bx - 2, 602), size=(bw + 4, 14))
                f = max(0.0, min(1.0, self.stam / 100.0))
                if self.cool > 0:
                    Color(0.9, 0.25, 0.2, 0.9)
                elif f < 0.25:
                    Color(1, 0.7, 0.2, 0.95)
                else:
                    Color(0.3, 0.95, 1, 0.9)
                Rectangle(pos=(bx, 604), size=(bw * f, 10))
                Color(1, 1, 1, 0.8)
                Rectangle(pos=(W - 52, 654), size=(8, 28))
                Rectangle(pos=(W - 36, 654), size=(8, 28))
                if st in ('play', 'paused'):
                    self.draw_buttons()
            if self.settings['show_fps'] and st in ('play', 'paused', 'dead', 'settings'):
                self.txt('FPS ' + str(int(round(self.fps_val))), 14, (0.6, 1, 0.6, 0.95), W / 2, 668, 'c')

            if st == 'main_menu':
                self.menu_main(W)
            elif st == 'settings':
                self.menu_settings(W)
            if st == 'paused':
                self.menu_pause(W)
            elif st == 'dead':
                self.menu_dead(W)

    # ------------------------------------------------------------------
    # Menus: round icon buttons, no button text
    # ------------------------------------------------------------------
    def btn(self, cx, cy, r, col, ring=(1, 1, 1, 0.9)):
        Color(0, 0, 0, 0.35)
        Ellipse(pos=(cx - r - 3, cy - r - 5), size=(2 * r + 6, 2 * r + 6))
        Color(*col)
        Ellipse(pos=(cx - r, cy - r), size=(2 * r, 2 * r))
        Color(1, 1, 1, 0.16)
        Ellipse(pos=(cx - r * 0.78, cy + r * 0.12), size=(r * 1.56, r * 0.8))
        Color(*ring)
        Line(circle=(cx, cy, r), width=2.2)

    def ic_play(self, cx, cy, s, col=(1, 1, 1, 1)):
        Color(*col)
        Triangle(points=[cx - s * 0.38, cy - s * 0.55, cx - s * 0.38, cy + s * 0.55, cx + s * 0.62, cy])

    def ic_pause(self, cx, cy, s, col=(1, 1, 1, 1)):
        Color(*col)
        Rectangle(pos=(cx - s * 0.42, cy - s * 0.5), size=(s * 0.28, s))
        Rectangle(pos=(cx + s * 0.14, cy - s * 0.5), size=(s * 0.28, s))

    def ic_restart(self, cx, cy, s, col=(1, 1, 1, 1)):
        Color(*col)
        R = s * 0.55
        pts = []
        a = 70.0
        while a >= -220.0:
            rr = math.radians(a)
            pts += [cx + math.cos(rr) * R, cy + math.sin(rr) * R]
            a -= 15.0
        Line(points=pts, width=max(2.4, s * 0.16), cap='round')
        a = math.radians(-220.0)
        ex, ey = cx + math.cos(a) * R, cy + math.sin(a) * R
        dx, dy = math.sin(a), -math.cos(a)
        px, py = -dy, dx
        hl, hw = s * 0.42, s * 0.30
        Triangle(points=[ex + dx * hl, ey + dy * hl, ex + px * hw, ey + py * hw, ex - px * hw, ey - py * hw])

    def ic_home(self, cx, cy, s, col=(1, 1, 1, 1)):
        Color(*col)
        Triangle(points=[cx - s * 0.62, cy + s * 0.05, cx + s * 0.62, cy + s * 0.05, cx, cy + s * 0.62])
        Rectangle(pos=(cx - s * 0.42, cy - s * 0.5), size=(s * 0.84, s * 0.55))
        Color(0.1, 0.1, 0.14, 0.9)
        Rectangle(pos=(cx - s * 0.12, cy - s * 0.5), size=(s * 0.24, s * 0.36))

    def ic_gear(self, cx, cy, s, col=(1, 1, 1, 1)):
        Color(*col)
        for k in range(8):
            a = k * math.pi / 4.0
            Line(points=[cx + math.cos(a) * s * 0.4, cy + math.sin(a) * s * 0.4,
                         cx + math.cos(a) * s * 0.66, cy + math.sin(a) * s * 0.66], width=max(3.0, s * 0.24))
        Ellipse(pos=(cx - s * 0.5, cy - s * 0.5), size=(s, s))
        Color(0.14, 0.17, 0.3, 1)
        Ellipse(pos=(cx - s * 0.2, cy - s * 0.2), size=(s * 0.4, s * 0.4))

    def ic_back(self, cx, cy, s, col=(1, 1, 1, 1)):
        Color(*col)
        Line(points=[cx + s * 0.15, cy + s * 0.55, cx - s * 0.5, cy, cx + s * 0.15, cy - s * 0.55],
             width=max(3.0, s * 0.2), cap='round')
        Line(points=[cx - s * 0.5, cy, cx + s * 0.6, cy], width=max(3.0, s * 0.2), cap='round')

    def menu_main(self, W):
        Color(0, 0, 0, 0.62)
        Rectangle(pos=(0, 0), size=(W, VH))
        self.txt('WEB RUNNER', 54, (1, 0.25, 0.25, 1), W / 2, 510, 'c')
        self.txt('BEST ' + str(self.best) + ' M', 16, (1, 0.9, 0.5, 0.9), W / 2, 462, 'c')
        self.btn(W / 2, 330, 80, (0.13, 0.55, 0.25, 0.95))
        self.ic_play(W / 2 + 4, 330, 56)
        self.btn(W / 2 + 185, 330, 46, (0.2, 0.25, 0.5, 0.95))
        self.ic_gear(W / 2 + 185, 330, 40)

    def menu_settings(self, W):
        Color(0, 0, 0, 0.78)
        Rectangle(pos=(0, 0), size=(W, VH))
        self.txt('SETTINGS', 38, (1, 1, 1, 1), W / 2, 600, 'c')
        rx = W / 2 + 150
        for label, key, ry, on in self.settings_rows():
            Color(0.1, 0.12, 0.2, 0.93)
            Rectangle(pos=(W / 2 - 170, ry), size=(340, 62))
            Color(0.3, 0.6, 1, 1)
            Rectangle(pos=(W / 2 - 170, ry), size=(5, 62))
            self.txt(label, 18, (1, 1, 1, 1), W / 2 - 150, ry + 22)
            if key == 'fps':
                self.txt(str(self.settings['fps']), 24, (0.6, 1, 1, 1), rx, ry + 20, 'r')
            elif key == 'quality':
                lvl = QUALITY_ORDER.index(self.settings['quality']) if self.settings['quality'] in QUALITY_ORDER else 1
                for i in range(3):
                    if i <= lvl:
                        Color(0.3, 0.95, 1, 1)
                    else:
                        Color(0.3, 0.33, 0.42, 1)
                    Rectangle(pos=(rx - 54 + i * 20, ry + 18), size=(14, 12 + i * 8))
            else:
                x0, x1 = rx - 56, rx
                if on:
                    Color(0.15, 0.6, 0.28, 1)
                else:
                    Color(0.35, 0.37, 0.45, 1)
                Ellipse(pos=(x0, ry + 20), size=(22, 22))
                Ellipse(pos=(x1 - 22, ry + 20), size=(22, 22))
                Rectangle(pos=(x0 + 11, ry + 20), size=(x1 - x0 - 22, 22))
                Color(1, 1, 1, 1)
                Ellipse(pos=((x1 - 20) if on else (x0 + 2), ry + 22), size=(18, 18))
        self.btn(W / 2, 150, 40, (0.2, 0.25, 0.5, 0.95))
        self.ic_back(W / 2 - 2, 150, 34)

    def menu_pause(self, W):
        cx = W / 2
        Color(0, 0, 0, 0.6)
        Rectangle(pos=(0, 0), size=(W, VH))
        Color(0.07, 0.09, 0.17, 0.96)
        Rectangle(pos=(cx - 250, 250), size=(500, 230))
        Color(0.3, 0.6, 1, 0.9)
        Line(rectangle=(cx - 250, 250, 500, 230), width=2)
        self.ic_pause(cx, 445, 24, (0.7, 0.9, 1, 0.9))
        self.btn(cx - 150, 340, 50, (0.75, 0.5, 0.1, 0.95))
        self.ic_restart(cx - 150, 340, 40)
        self.btn(cx, 340, 64, (0.13, 0.55, 0.25, 0.95))
        self.ic_play(cx + 4, 340, 46)
        self.btn(cx + 150, 340, 50, (0.2, 0.3, 0.6, 0.95))
        self.ic_home(cx + 150, 340, 40)

    def menu_dead(self, W):
        cx = W / 2
        a = min(1.0, self.dead_t / 0.5)
        Color(0, 0, 0, 0.55 * a)
        Rectangle(pos=(0, 0), size=(W, VH))
        if self.dead_t > 0.2:
            d = int(self.dist())
            self.txt('GAME OVER', 54, RED, cx, 430, 'c')
            self.txt(str(d) + ' M', 38, (1, 1, 1, 1), cx, 360, 'c')
            if d > 0 and d >= self.best:
                self.txt('NEW BEST!', 20, (1, 0.9, 0.5, 1), cx, 315, 'c')
            else:
                self.txt('BEST ' + str(self.best) + ' M', 20, (1, 0.9, 0.5, 1), cx, 315, 'c')
        if self.dead_t > 0.6:
            self.btn(cx - 90, 235, 46, (0.13, 0.55, 0.25, 0.95))
            self.ic_restart(cx - 90, 235, 38)
            self.btn(cx + 90, 235, 46, (0.2, 0.3, 0.6, 0.95))
            self.ic_home(cx + 90, 235, 38)

    def go_menu(self):
        self.clear_touches()
        self.reset_world()
        self.state = 'main_menu'

    # ------------------------------------------------------------------
    # Text rendering (was missing from the file)
    # ------------------------------------------------------------------
    def glyph(self, ch, size):
        key = (ch, size)
        tex = self.tcache.get(key)
        if tex is None:
            lb = CoreLabel(text=ch, font_size=max(4, int(round(size * self.sc))), bold=True)
            lb.refresh()
            tex = lb.texture
            self.tcache[key] = tex
        return tex

    def txt(self, s, size, color, x, y, align='l'):
        w = self.txt_w(s, size)
        if align == 'c':
            x -= w / 2.0
        elif align == 'r':
            x -= w
        Color(*color)
        for ch in s:
            if ch == ' ':
                x += size * 0.3
                continue
            tex = self.glyph(ch, size)
            gw, gh = tex.width / self.sc, tex.height / self.sc
            Rectangle(texture=tex, pos=(x, y), size=(gw, gh))
            x += gw

    # ------------------------------------------------------------------
    # Drawing helpers that were missing from the file
    # ------------------------------------------------------------------
    def draw_plane(self, x, y, t):
        Color(0.1, 0.09, 0.22, 1)
        Rectangle(pos=(x - 17, y), size=(34, 5))
        Triangle(points=[x + 17, y, x + 17, y + 5, x + 25, y + 2.5])
        Triangle(points=[x - 3, y + 3, x - 12, y + 3, x - 8, y - 9])
        Triangle(points=[x - 15, y + 4, x - 22, y + 11, x - 10, y + 4])
        Color(1, 0.2, 0.2, 1 if (t % 1.2) < 0.5 else 0.2)
        Ellipse(pos=(x - 10, y - 10), size=(3, 3))
        Color(1, 1, 1, 1 if (t % 1.2) > 1.1 else 0.1)
        Ellipse(pos=(x - 20, y + 9), size=(3, 3))
        Color(1, 1, 1, 0.12)
        Line(points=[x - 18, y + 2.5, x - 170, y + 2.5], width=1.5)


    def draw_far_blimp(self, x, y, t):
        Color(0.28, 0.2, 0.42, 1)
        Ellipse(pos=(x - 60, y), size=(120, 38))
        Triangle(points=[x - 54, y + 22, x - 72, y + 38, x - 44, y + 30])
        Triangle(points=[x - 54, y + 16, x - 72, y, x - 44, y + 8])
        Color(0.2, 0.15, 0.32, 1)
        Rectangle(pos=(x - 12, y - 6), size=(24, 8))
        for i in range(8):
            Color(1, 0.8, 0.4, 0.9 if (int(t * 3) + i) % 8 == 0 else 0.25)
            Rectangle(pos=(x - 32 + i * 8, y + 17), size=(5, 5))
        Color(1, 0.3, 0.3, 1 if (t % 1.5) < 0.4 else 0.2)
        Ellipse(pos=(x - 64, y + 30), size=(4, 4))


    def draw_far_ufo(self, x, y, t):
        Color(0.3, 0.32, 0.42, 1)
        Ellipse(pos=(x - 24, y), size=(48, 12))
        Color(0.45, 0.9, 0.85, 0.6)
        Ellipse(pos=(x - 9, y + 6), size=(18, 12))
        if math.sin(t * 0.5) > 0.2:
            Color(0.6, 1, 0.8, 0.07)
            Triangle(points=[x - 8, y, x + 8, y, x, y - 170])
        for k in range(5):
            Color(1, 0.9, 0.3, 0.9 if int(t * 6 + k) % 5 == 0 else 0.3)
            Ellipse(pos=(x - 18 + k * 8, y + 2), size=(3, 3))


    def draw_far_heli(self, x, y, t):
        Color(0.1, 0.09, 0.22, 1)
        Ellipse(pos=(x - 14, y), size=(28, 11))
        Line(points=[x - 12, y + 7, x - 30, y + 10], width=2)
        ln = 22 * abs(math.cos(t * 14))
        Line(points=[x - ln, y + 14, x + ln, y + 14], width=1.5)
        Line(points=[x, y + 11, x, y + 14], width=1.5)
        sx = math.sin(t * 0.7) * 90
        Color(1, 1, 0.85, 0.07)
        Triangle(points=[x + 4, y + 2, x + sx - 22, y - 260, x + sx + 22, y - 260])
        Color(1, 0.2, 0.2, 1 if (t % 1.0) < 0.3 else 0.2)
        Ellipse(pos=(x - 32, y + 8), size=(3, 3))


    def draw_sky(self):
        t, W, cx, cy = self.tm, self.W, self.cam_x, self.cam_y
        lvl = self.q()['sky']
        if self.star_ins and self.frame % 3 == 0:
            for col, rect, sx, sy, ph in self.star_ins:
                col.a = 0.25 + 0.55 * abs(math.sin(t * 1.3 + ph))
                rect.pos = ((sx - cx * 0.02) % W, sy - cy * 0.05)
        span = W + 500.0
        for tr, cx0, cyy, spd in self.cloud_ins:
            tr.x = (cx0 + t * spd - cx * 0.06) % span - 250.0
            tr.y = cyy - cy * 0.08
        c = self.sky_fx
        c.clear()
        if lvl <= 0:
            return
        with c:
            x = (t * 46 + 300 - cx * 0.03) % (W + 500) - 250
            if -40 < x < W + 40:
                self.draw_plane(x, 625 - cy * 0.04 + math.sin(t * 0.3) * 4, t)
            if lvl < 2:
                return
            x = (t * 13 + 600 - cx * 0.03) % (W + 600) - 300
            if -90 < x < W + 90:
                self.draw_far_blimp(x, 520 - cy * 0.04, t)
            x = (t * 34 + 100 - cx * 0.03) % (W + 500) - 250
            if -40 < x < W + 40:
                self.draw_far_ufo(x, 655 - cy * 0.04 + math.sin(t * 1.3) * 10, t)
            x = (-t * 38 + 900 - cx * 0.03) % (W + 600) - 300
            if -40 < x < W + 40:
                self.draw_far_heli(x, 470 - cy * 0.04, t)

    def draw_bld_anim(self, b, t, kinds, x0, x1):
        for a in b.anim:
            k = a[0]
            if k not in kinds or a[1] < x0 or a[1] > x1:      # skip effects off screen
                continue
            if k == 'smoke':
                _, sx, sy, sc_, ph = a
                for i in range(6):
                    u = (t * 0.32 + i / 6.0 + ph) % 1.0
                    s = (6 + u * 20) * sc_
                    px = sx + math.sin(u * 7 + i) * 6 + u * 26
                    py = sy + u * 78
                    Color(0.62, 0.58, 0.7, 0.42 * (1 - u))
                    Ellipse(pos=(px - s / 2, py - s / 2), size=(s, s))
            elif k == 'fan':
                _, fx_, fy_, r_ = a
                ang = t * 16
                Color(0.55, 0.57, 0.65, 1)
                for j in range(3):
                    aa = ang + j * 2.0944
                    Line(points=[fx_, fy_, fx_ + math.cos(aa) * r_, fy_ + math.sin(aa) * r_], width=1.4)
            elif k == 'beacon':
                _, bx, by, col, per = a
                if (t / per) % 1.0 < 0.22:
                    Color(col[0], col[1], col[2], 0.28)
                    Ellipse(pos=(bx - 9, by - 9), size=(18, 18))
                    Color(col[0], col[1], col[2], 1)
                else:
                    Color(col[0], col[1], col[2], 0.3)
                Ellipse(pos=(bx - 3, by - 3), size=(6, 6))
            elif k == 'tv':
                _, wx, wy, ww, wh = a
                f = 0.5 + 0.5 * math.sin(t * 9 + wx) * math.sin(t * 3.7 + wy)
                Color(0.5 + 0.4 * f, 0.7 + 0.2 * f, 1, 0.2 + 0.4 * f)
                Rectangle(pos=(wx, wy), size=(ww, wh))
            elif k == 'neon':
                _, nx_, ny_, nw, nh_, col, sp = a
                f = 0.3 if math.sin(t * sp + nx_) < -0.93 else 0.75 + 0.25 * math.sin(t * 3 + nx_)
                Color(col[0], col[1], col[2], 0.28 * f)
                Rectangle(pos=(nx_ - 6, ny_ - 6), size=(nw + 12, nh_ + 12))
                Color(col[0], col[1], col[2], 0.6 * f)
                Line(rectangle=(nx_, ny_, nw, nh_), width=1.6)
            elif k == 'glow':
                _, gx, gy, gw, gh, col, sp = a
                f = 0.5 + 0.5 * math.sin(t * sp + gx)
                Color(col[0], col[1], col[2], 0.08 + 0.16 * f)
                Rectangle(pos=(gx, gy), size=(gw, gh))
                Color(col[0], col[1], col[2], 0.15 * f)
                Rectangle(pos=(gx - 8, gy - 8), size=(gw + 16, gh + 16))
            elif k == 'lights':
                _, lx0, ly0, lx1, n, ph = a
                cols = ((1, 0.4, 0.4), (0.4, 1, 0.5), (1, 0.9, 0.4), (0.5, 0.7, 1))
                for i in range(n):
                    px = lx0 + (lx1 - lx0) * i / (n - 1.0)
                    py = ly0 - 8 * math.sin(math.pi * i / (n - 1.0))
                    cc = cols[i % 4]
                    on = int(t * 2.2 + i * 1.3 + ph) % 3 != 0
                    Color(cc[0], cc[1], cc[2], 0.25 if on else 0.05)
                    Ellipse(pos=(px - 5, py - 5), size=(10, 10))
                    Color(cc[0], cc[1], cc[2], 1 if on else 0.3)
                    Ellipse(pos=(px - 2, py - 2), size=(4, 4))


    def draw_animals(self, b, t):
        p = self.p
        moving = self.state != 'paused'
        cx0, cx1 = self.cam_x - 40, self.cam_x + self.W + 40
        for a in b.animals:
            x, y = a['x'], a['y']
            if not (cx0 < x < cx1):
                if (a['k'] == 'pig' and a['st'] is None) or (a['k'] != 'pig' and not a['run']):
                    continue
            if a['k'] == 'pig':
                if a['st'] is None and self.state == 'play' and a['x'] - 340 < p.x < a['x'] + 60:
                    a['st'] = t + (a['ph'] / 6.28) * 0.35
                if a['st'] is None or t < a['st']:
                    bob = math.sin(t * 5 + a['ph']) * 1.2
                    Color(0.85, 0.5, 0.45, 1)
                    Line(points=[x - 1, y + 3, x - 1, y, x + 2, y + 3, x + 2, y], width=1)
                    Color(0.5, 0.52, 0.62, 1)
                    Ellipse(pos=(x - 6, y + 3), size=(13, 9))
                    Color(0.38, 0.4, 0.52, 1)
                    Ellipse(pos=(x - 9, y + 5), size=(8, 6))
                    Color(0.42, 0.44, 0.58, 1)
                    Ellipse(pos=(x + 4 + bob, y + 9), size=(6, 6))
                    Color(0.3, 0.75, 0.65, 0.9)
                    Ellipse(pos=(x + 3, y + 8), size=(4, 3))
                    Color(1, 0.8, 0.2, 1)
                    Triangle(points=[x + 10 + bob, y + 12, x + 13 + bob, y + 11, x + 10 + bob, y + 10])
                else:
                    s = t - a['st']
                    if s > 5:
                        continue
                    fx_ = x + a['vx'] * s
                    fy_ = y + 8 + a['vy'] * s * 0.8
                    fl = math.sin(t * 28 + a['ph'])
                    Color(0.38, 0.4, 0.52, 1)
                    Line(points=[fx_, fy_ + 6, fx_ - 6, fy_ + 6 + 10 * fl, fx_ - 12, fy_ + 6 + 5 * fl], width=2.4)
                    Color(0.5, 0.52, 0.62, 1)
                    Ellipse(pos=(fx_ - 6, fy_), size=(13, 8))
                    Ellipse(pos=(fx_ + 5, fy_ + 4), size=(6, 6))
                    Color(1, 0.8, 0.2, 1)
                    Triangle(points=[fx_ + 11, fy_ + 8, fx_ + 14, fy_ + 7, fx_ + 11, fy_ + 6])
                    Color(0.62, 0.64, 0.74, 1)
                    Line(points=[fx_ + 1, fy_ + 6, fx_ + 5, fy_ + 6 - 10 * fl, fx_ + 11, fy_ + 6 - 5 * fl], width=2.4)
            else:
                if not a['run'] and self.state == 'play' and a['x'] - 260 < p.x < a['x'] + 40:
                    a['run'] = True
                running = a['run'] and a['x'] < a['ex']
                if running and moving:
                    a['x'] += 210 * self.dt
                x = a['x']
                ph = a['ph']
                Color(0.1, 0.1, 0.14, 1)
                if running:
                    cyc = t * 22
                    Ellipse(pos=(x - 12, y + 4), size=(28, 11))
                    Ellipse(pos=(x + 12, y + 7), size=(11, 9))
                    Triangle(points=[x + 14, y + 14, x + 16, y + 19, x + 18, y + 14])
                    Triangle(points=[x + 18, y + 14, x + 21, y + 18, x + 22, y + 13])
                    Line(points=[x - 11, y + 11, x - 24, y + 16 + math.sin(cyc) * 3], width=3)
                    for j, ox in enumerate((-8, -3, 8, 13)):
                        sw = math.sin(cyc + j * 1.6) * 6
                        Line(points=[x + ox, y + 6, x + ox + sw, y], width=2)
                    Color(1, 0.9, 0.2, 1)
                    Ellipse(pos=(x + 18, y + 11), size=(2.4, 2.4))
                else:
                    Ellipse(pos=(x - 9, y + 1), size=(20, 12))
                    Ellipse(pos=(x - 11, y), size=(12, 12))
                    Ellipse(pos=(x + 6, y + 8), size=(11, 10))
                    Triangle(points=[x + 7, y + 16, x + 9, y + 21, x + 11, y + 16])
                    Triangle(points=[x + 12, y + 16, x + 15, y + 21, x + 16, y + 15])
                    pts = []
                    for i in range(6):
                        u = i / 5.0
                        pts += [x - 9 - u * 14, y + 3 + math.sin(u * 3 + t * 3 + ph) * 4 * u + u * 4]
                    Line(points=pts, width=3)
                    blink = (t + ph) % 4.0 > 3.88
                    Color(1, 0.9, 0.2, 0.0 if blink else 1)
                    Ellipse(pos=(x + 10, y + 13), size=(2.6, 2.6))
                    Ellipse(pos=(x + 14, y + 13), size=(2.6, 2.6))


    def draw_swing_dyn(self, o, t, full=True):
        ax, ay, rl = o.ax, o.ay, o.rl
        pu = 0.5 + 0.5 * math.sin(t * 4 + o.ph)
        sway = math.sin(t * 1.7 + o.ph) * 2.5
        Color(0.62, 0.52, 0.38, 1)
        Line(points=[ax, ay + rl, ax + sway, ay + rl * 0.5, ax, ay + 5], width=2)
        k = o.kind if full else ''
        if k == 'blimp':
            px, py = ax - 130, ay + rl + 14 + 38
            c_ = math.cos(t * 25)
            Color(0.2, 0.2, 0.25, 0.3)
            Ellipse(pos=(px - 2, py - 15), size=(4, 30))
            Color(0.15, 0.15, 0.2, 0.9)
            Line(points=[px, py - 15 * c_, px, py + 15 * c_], width=2)
            Color(1, 0.2, 0.2, 1 if (t % 1.1) < 0.4 else 0.2)
            Ellipse(pos=(ax - 134, ay + rl + 14 + 76), size=(5, 5))
            Color(0.2, 1, 0.4, 1 if (t % 1.1) > 0.55 else 0.2)
            Ellipse(pos=(ax + 118, ay + rl + 14 + 36), size=(5, 5))
        elif k == 'balloon':
            fy_ = ay + rl + 26
            fh = 14 + 5 * math.sin(t * 31) + 3 * math.sin(t * 19)
            Color(1, 0.7, 0.3, 0.14)
            Ellipse(pos=(ax - 22, fy_ + 6), size=(44, 44))
            Color(1, 0.55, 0.1, 0.9)
            Triangle(points=[ax - 5, fy_, ax + 5, fy_, ax + math.sin(t * 13) * 2, fy_ + fh])
            Color(1, 0.95, 0.5, 0.95)
            Triangle(points=[ax - 2.5, fy_, ax + 2.5, fy_, ax, fy_ + fh * 0.6])
        elif k == 'heli':
            ry = ay + rl + 66
            ln = 82 * abs(math.cos(t * 16))
            Color(0.5, 0.5, 0.6, 0.18)
            Ellipse(pos=(ax - 82, ry - 4), size=(164, 8))
            Color(0.15, 0.15, 0.2, 0.9)
            Line(points=[ax - ln, ry, ax + ln, ry], width=3)
            tx_, ty_ = ax - 104, ay + rl + 52
            a_ = t * 30
            Color(0.5, 0.5, 0.6, 0.2)
            Ellipse(pos=(tx_ - 9, ty_ - 9), size=(18, 18))
            Color(0.15, 0.15, 0.2, 0.9)
            Line(points=[tx_ - 9 * math.sin(a_), ty_ - 9 * math.cos(a_),
                         tx_ + 9 * math.sin(a_), ty_ + 9 * math.cos(a_)], width=2)
            sx = math.sin(t * 0.6 + o.ph) * 90
            Color(1, 1, 0.85, 0.07)
            Triangle(points=[ax + 8, ay + rl + 20, ax + 8 + sx - 34, ay - 300, ax + 8 + sx + 34, ay - 300])
            Color(1, 0.2, 0.2, 1 if (t % 1.0) < 0.3 else 0.2)
            Ellipse(pos=(ax - 112, ay + rl + 16 + 50), size=(5, 5))
        elif k == 'drone':
            for mx, my, ph in ((-66, rl + 30, 0), (66, rl + 30, 1), (-38, rl + 40, 2), (38, rl + 40, 3)):
                Color(0.5, 0.55, 0.65, 0.3)
                Ellipse(pos=(ax + mx - 26, ay + my + 3), size=(52, 6))
                Color(0.15, 0.15, 0.2, 0.9)
                ln = 26 * abs(math.cos(t * 40 + ph))
                Line(points=[ax + mx - ln, ay + my + 6, ax + mx + ln, ay + my + 6], width=2)
            Color(0.3, 1, 0.4, 1 if (t % 1.2) < 0.6 else 0.25)
            Ellipse(pos=(ax + 24, ay + rl + 4), size=(5, 5))
            Color(1, 0.2, 0.2, 1 if (t % 1.2) >= 0.6 else 0.25)
            Ellipse(pos=(ax - 29, ay + rl + 4), size=(5, 5))
            Color(0.3, 0.8, 1, 0.12 + 0.1 * pu)
            Triangle(points=[ax, ay + rl - 4, ax - 30, ay - 120, ax + 30, ay - 120])
        elif k == 'ufo':
            if math.sin(t * 0.8 + o.ph) > -0.3:
                Color(0.6, 1, 0.8, 0.07 + 0.04 * pu)
                Triangle(points=[ax - 8, ay + rl, ax + 8, ay + rl, ax, ay - 230])
                Triangle(points=[ax - 12, ay + rl, ax + 12, ay + rl, ax + 70, ay - 230])
                Triangle(points=[ax - 12, ay + rl, ax + 12, ay + rl, ax - 70, ay - 230])
            for j in range(7):
                a_ = j * 0.8976 + t * 0.6
                Color(1, 0.9, 0.3, 1 if int(t * 6 + j) % 7 == 0 else 0.35)
                Ellipse(pos=(ax + math.cos(a_) * 56 - 2.5, ay + rl + 22 + math.sin(a_) * 5 - 2.5), size=(5, 5))

        Color(0.85, 0.88, 0.95, 1)
        Line(circle=(ax, ay, 5), width=2)
        Color(1, 1, 1, 0.5 + 0.5 * pu)
        Ellipse(pos=(ax - 3.8, ay + 1.2), size=(2.6, 2.6))
        if o is self.swing_hint:
            Color(1, 0.95, 0.6, 0.25 + 0.3 * pu)
            Line(circle=(ax, ay, 16 + 3 * pu), width=1.8)


    def draw_amb(self):
        c = self.amb
        c.clear()
        t = self.tm
        qd = self.q()
        x0, x1 = self.cam_x - 80, self.cam_x + self.W + 10
        kinds, full = qd['amb'], qd['swfx']
        with c:
            for b in self.bl:
                if not b.visible:
                    continue
                self.draw_bld_anim(b, t, kinds, x0, x1)
                if b.animals and qd['animals']:
                    self.draw_animals(b, t)
            for o in self.swings:
                if o.visible:
                    self.draw_swing_dyn(o, t, full)

    def draw_back(self):
        x0 = self.cam_x - 120
        wd = self.W + 240
        self.g_road.pos = (x0, 0)
        self.g_road.size = (wd, 22)
        self.g_edge.pos = (x0, 22)
        self.g_edge.size = (wd, 2)
        self.g_dash.pos = (x0, 10)
        self.g_dash.size = (wd, 2)
        u0, u1 = x0 / 64.0, (x0 + wd) / 64.0
        self.g_dash.tex_coords = (u0, 0, u1, 0, u1, 1, u0, 1)

    def draw_web(self, x0, y0, x1, y1, frac=1.0, amp=0.0, thick=1.5, alpha=1.0, sag=0.0):
        """Straight silky strand (sag > 0 only for the slack web after letting go)."""
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy) or 1.0
        px, py = -dy / L, dx / L
        if sag <= 0.01:
            ex, ey = x0 + dx * frac, y0 + dy * frac
            pts = [x0, y0, ex, ey]
        else:
            n = 10
            pts = []
            for i in range(n + 1):
                u = i / float(n) * frac
                pts += [x0 + dx * u, y0 + dy * u - sag * 4 * u * (1 - u)]
            ex, ey = pts[-2], pts[-1]
        Color(0.4, 0.95, 1.0, 0.14 * alpha)
        Line(points=pts, width=thick * 3.0)
        Color(1, 1, 1, 0.95 * alpha)
        Line(points=pts, width=thick)
        if sag <= 0.01 and L > 60:                      # tiny cross-threads
            Color(1, 1, 1, 0.32 * alpha)
            n = min(8, int(L * frac / 46.0))
            for i in range(1, n + 1):
                u = i / float(n + 1) * frac
                bx, by = x0 + dx * u, y0 + dy * u
                Line(points=[bx - px * 2.6, by - py * 2.6, bx + px * 2.6, by + py * 2.6], width=0.8)
        if frac < 1.0:                                  # glowing tip while it flies out
            Color(0.4, 0.95, 1.0, 0.35)
            Ellipse(pos=(ex - 6, ey - 6), size=(12, 12))
            Color(1, 1, 1, 1)
            Ellipse(pos=(ex - 3, ey - 3), size=(6, 6))

    def draw_web_patch(self, x, y, r, alpha, rot=0.0):
        Color(1, 1, 1, 0.9 * alpha)
        for k in range(8):
            a = rot + k * math.pi / 4.0
            Line(points=[x, y, x + math.cos(a) * r, y + math.sin(a) * r], width=1.1)
        for f in (0.35, 0.65, 1.0):
            pts = []
            for k in range(8):
                a = rot + k * math.pi / 4.0
                rr = r * f * (1.0 - 0.12 * (k % 2))
                pts += [x + math.cos(a) * rr, y + math.sin(a) * rr]
            Line(points=pts, close=True, width=1.0)

    def draw_fx(self):
        for kind, x, y, vx, vy, age, life, size, col in self.fx:
            u = age / life
            if kind == 'asplat':
                ob = col[1]
                sc = min(1.0, age / 0.07)
                a = 1.0 if u < 0.65 else (1.0 - u) / 0.35
                self.draw_web_patch(ob.ax, ob.ay, size * (0.35 + 0.65 * sc), max(0.0, a), col[0])
                continue
            a = max(0.0, 1.0 - u)
            r_, g_, b_ = min(1.0, col[0]), min(1.0, col[1]), min(1.0, col[2])
            if kind == 'spark':
                s = size * 1.5
                Color(r_, g_, b_, a)
                Ellipse(pos=(x - s / 2, y - s / 2), size=(s, s))
            elif kind == 'dust':
                s = size * (1 + u * 0.8)
                Color(r_, g_, b_, 0.45 * a)
                Ellipse(pos=(x - s / 2, y - s / 2), size=(s, s))
            elif kind == 'ring':
                Color(0.5, 1, 1, a)
                Line(circle=(x, y, size + u * 28), width=2)
            elif kind == 'shock':
                rr = size * (1 + u * 5)
                Color(1, 1, 1, 0.5 * a)
                Line(ellipse=(x - rr, y - rr * 0.18, 2 * rr, rr * 0.36), width=1.5)
            elif kind == 'ghost':
                cx_, cy_ = x, y + 20
                ca, sa = math.cos(size), math.sin(size)
                Color(r_, g_, b_, 0.35 * a)
                Line(points=[cx_ - ca * 16, cy_ - sa * 16, cx_ + ca * 16, cy_ + sa * 16], width=9)

class WebRunnerApp(App):
    title = 'Web Runner'

    def build(self):
        force_landscape()
        self.game = Game()
        return self.game

    def on_start(self):
        force_landscape()

    def on_pause(self):
        self.game.auto_pause()
        self.game.save_best()
        return True

    def on_resume(self):
        try:
            self.game.rebake()      # GL textures may have been lost while paused
            self.game.build_bg()
        except Exception:
            pass

    def on_stop(self):
        self.game.save_best()


if __name__ == '__main__':
    WebRunnerApp().run()
