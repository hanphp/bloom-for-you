"""A little interactive bouquet. Run with: python bored_flower.py"""

from functools import lru_cache
import math
import random
import time
import tkinter as tk
from tkinter import font as tkfont

WIDTH, HEIGHT = 1000, 700
INK = "#d9e1e8"
MUTED = "#8c98a4"
BLACK = "#080a0c"
NOISE = "#242b32"
ROW_HEIGHT = 6
FLOWERS = (
    ("spider", "Red spider lily", 502, 278, 499, 569, 0.0,
     "For making ordinary days feel a little more magical."),
    ("bells", "Lily of the valley", 326, 290, 493, 569, 0.5,
     "For the little things you do that make me smile."),
    ("orchid", "Orchid", 665, 326, 510, 568, 0.7,
     "For being completely, wonderfully yourself."),
    ("hydrangea", "Hydrangea", 388, 418, 495, 570, 1.0,
     "For all the small moments I'd happily live twice."),
    ("mum", "Chrysanthemum", 603, 432, 508, 570, 1.2,
     "For the next hundred times we laugh at something silly."),
)
# Extra blooms reuse their species' name, color, and note.
EXTRA_BLOOMS = (
    (1, 386, 237, 498, 568, .66, .91),
    (2, 642, 231, 505, 568, .81, .73),
    (3, 335, 378, 490, 569, .95, .63),
    (3, 454, 427, 500, 571, .90, .67),
    (4, 670, 406, 512, 569, 1.07, .62),
    (4, 540, 448, 503, 570, 1.26, .64),
)
# Smaller flower heads fill the spaces between the larger foreground blooms.
FILLER_BLOOMS = (
    (3, 438, 203, 496, 569, .74, .55),
    (4, 478, 188, 499, 568, .85, .50),
    (2, 536, 192, 502, 568, .82, .58),
    (3, 584, 211, 505, 568, .82, .57),
    (2, 421, 253, 495, 569, .91, .66),
    (4, 592, 256, 506, 568, .89, .59),
    (3, 378, 298, 493, 569, 1.01, .60),
    (4, 364, 340, 492, 569, 1.04, .64),
    (2, 420, 349, 496, 569, .96, .75),
    (4, 466, 364, 498, 570, 1.10, .62),
    (2, 504, 393, 502, 570, 1.17, .64),
    (3, 547, 372, 504, 570, 1.10, .69),
    (4, 568, 326, 505, 569, 1.04, .56),
    (2, 604, 350, 507, 569, 1.07, .64),
    (3, 635, 286, 509, 568, .91, .60),
    (3, 633, 389, 510, 569, 1.12, .59),
)
FOREGROUND_COUNT = len(FLOWERS) + len(EXTRA_BLOOMS)
STEMS = [(index, flower, 1.0) for index, flower in enumerate(FLOWERS)]
for species, x, y, base_x, base_y, delay, size in EXTRA_BLOOMS + FILLER_BLOOMS:
    kind, name, _, _, _, _, _, note = FLOWERS[species]
    STEMS.append((species, (kind, name, x, y, base_x, base_y, delay, note), size))
BLOOM_RADII = (132, 45, 55, 53, 49)
BLOOM_ORDER = sorted(range(len(STEMS)),
                     key=lambda i: (i < FOREGROUND_COUNT, STEMS[i][1][3]))

STEM_COLORS = ("#6e996e", "#86a57a", "#668e68", "#527e68", "#81a173")


def smooth(value):
    value = max(0, min(1, value))
    return value * value * (3 - 2 * value)


@lru_cache(maxsize=512)
def blend(a, b, fraction):
    channels = [round(int(a[i:i+2], 16) * (1-fraction)
                      + int(b[i:i+2], 16) * fraction) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(channels)


class Garden:
    def __init__(self, root):
        self.root = root
        root.title("Bloom for You | ASCII Garden")
        root.geometry("1000x700")
        root.minsize(680, 480)
        root.configure(bg=BLACK)
        self.canvas = tk.Canvas(root, bg=BLACK, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.scale = 1
        self.ascii_font = tkfont.Font(root=root, family="Consolas", size=-9)
        self.column_width = self.ascii_font.measure("/")
        self.cells = {}
        self.left = self.top = 0
        self.started = None
        self.selected = None
        self.particles = []
        self.water = []
        self.hits = []
        rng = random.Random(17)
        self.noise = [(rng.randrange(12, 990), rng.randrange(122, 585))
                      for _ in range(260)]
        self.canvas.bind("<Configure>", self.resize)
        self.canvas.bind("<Button-1>", self.click)
        self.canvas.bind("<Motion>", self.hover)
        root.bind("<space>", lambda event: self.water_soil())
        root.bind("<Return>", lambda event: self.water_soil())
        root.bind("r", lambda event: self.reset())
        for index in range(len(FLOWERS)):
            root.bind(str(index + 1), lambda event, i=index: self.reveal(i))
        self.frame()

    def resize(self, event):
        self.scale = min(event.width / WIDTH, event.height / HEIGHT)
        self.left = (event.width - WIDTH * self.scale) / 2
        self.top = (event.height - HEIGHT * self.scale) / 2
        self.ascii_font.configure(size=-max(7, round(9 * self.scale)))
        self.column_width = self.ascii_font.measure("/") / self.scale

    def coords(self, points):
        return [(self.left if index % 2 == 0 else self.top) + value * self.scale
                for index, value in enumerate(points)]

    def span(self, row, left, right, color):
        first = math.ceil(left / self.column_width)
        last = math.floor(right / self.column_width)
        for column in range(first, last + 1):
            self.cells[row, column] = color

    def oval(self, x, y, rx, ry, color, outline="", width=1):
        if rx <= 0 or ry <= 0:
            return
        if outline:
            points = [(x+rx*math.cos(i*math.tau/40), y+ry*math.sin(i*math.tau/40))
                      for i in range(41)]
            self.stroke(points, outline, width)
        if not color:
            return
        for row in range(math.ceil((y-ry)/ROW_HEIGHT), math.floor((y+ry)/ROW_HEIGHT)+1):
            half = rx * math.sqrt(max(0, 1-((row*ROW_HEIGHT-y)/ry)**2))
            self.span(row, x-half, x+half, color)
        if rx < self.column_width or ry < ROW_HEIGHT:
            self.cells[round(y/ROW_HEIGHT), round(x/self.column_width)] = color

    def curve(self, points, closed=False):
        vertices = list(zip(points[::2], points[1::2]))
        if len(vertices) < 3:
            return vertices
        if closed:
            vertices = [vertices[-1], *vertices, vertices[0]]
        path = []
        for i in range(1, len(vertices)-1):
            (ax, ay), (bx, by), (cx, cy) = vertices[i-1:i+2]
            left = ((ax+bx)/2, (ay+by)/2) if closed or i > 1 else (ax, ay)
            right = ((bx+cx)/2, (by+cy)/2) if closed or i < len(vertices)-2 else (cx, cy)
            for step in range(7):
                t = step / 6
                path.append(((1-t)**2*left[0] + 2*t*(1-t)*bx + t*t*right[0],
                             (1-t)**2*left[1] + 2*t*(1-t)*by + t*t*right[1]))
        return path

    def stroke(self, path, color, width):
        for (x, y), (end_x, end_y) in zip(path, path[1:]):
            steps = max(1, math.ceil(math.hypot(end_x-x, end_y-y)/3))
            for step in range(steps+1):
                t = step / steps
                cx, cy = x+(end_x-x)*t, y+(end_y-y)*t
                row, column = round(cy/ROW_HEIGHT), round(cx/self.column_width)
                self.cells[row, column] = color
                if width >= 5:
                    neighbor = column + (1 if cx >= column*self.column_width else -1)
                    self.cells.setdefault((row, neighbor), blend(color, BLACK, .43))

    def line(self, points, color, width=1):
        self.stroke(self.curve(points), color, width)

    def shape(self, points, color):
        path = self.curve(points, closed=True)
        min_y = min(y for _, y in path)
        max_y = max(y for _, y in path)
        edges = list(zip(path, path[1:]+path[:1]))
        for row in range(math.ceil(min_y/ROW_HEIGHT), math.floor(max_y/ROW_HEIGHT)+1):
            y = row * ROW_HEIGHT
            crossings = sorted(x+(y-ay)*(bx-x)/(by-ay)
                               for (x, ay), (bx, by) in edges
                               if min(ay, by) <= y < max(ay, by))
            for left, right in zip(crossings[::2], crossings[1::2]):
                self.span(row, left, right, color)

    def label(self, x, y, text, size, color=INK, family="Consolas", anchor="center"):
        self.canvas.create_text(*self.coords((x, y)), text=text, fill=color, anchor=anchor,
                                font=(family, -max(1, round(size*self.scale))))

    @staticmethod
    @lru_cache(maxsize=512)
    def is_petal_color(color):
        red, green, blue = (int(color[i:i+2], 16) for i in (1, 3, 5))
        return max(red, blue) >= 125 and max(red, blue) > green

    def ascii_character(self, row, column, color, pattern):
        if color == NOISE:
            return "." if pattern % 4 else ":"

        # Follow the strongest axis through this cell. Matching colors give
        # petal edges and veins priority where several shapes overlap.
        directions = (("|", 1, 0), ("-", 0, 1), ("/", 1, -1), ("\\", 1, 1))
        strongest = 0
        character = "."
        occupied = 0
        for glyph, dy, dx in directions:
            neighbors = (self.cells.get((row-dy, column-dx)),
                         self.cells.get((row+dy, column+dx)))
            occupied += sum(neighbor not in (None, NOISE) for neighbor in neighbors)
            weight = sum(2 if neighbor == color else 1
                         for neighbor in neighbors if neighbor not in (None, NOISE))
            if weight > strongest:
                strongest, character = weight, glyph
        if self.is_petal_color(color):
            if occupied >= 5:
                return ("#", "%", "@", "#")[pattern % 4]
            if occupied >= 3:
                return ("+", "*", "*", "o")[pattern % 4]
        if occupied >= 6:
            return (":", "+", "*", "+")[pattern % 4]
        return character if strongest else "*"

    def render_ascii(self, tick):
        rows = {}
        for (row, column), color in self.cells.items():
            pattern = (row*73856093) ^ (column*19349663)
            value = pattern ^ (pattern >> 7) ^ (pattern >> 15)
            glyph = self.ascii_character(row, column, color, value)
            if (value + tick) % 17 == 0:
                color = blend(color, INK, .35)
            rows.setdefault((row, color), {})[column] = glyph
        for (row, color), columns in rows.items():
            first, last = min(columns), max(columns)
            text = "".join(columns.get(column, " ") for column in range(first, last+1))
            x = first*self.column_width - self.column_width/2
            self.canvas.create_text(*self.coords((x, row*ROW_HEIGHT)), text=text,
                                    fill=color, font=self.ascii_font, anchor="w")

    def petal(self, x, y, angle, length, width, color, curl=0):
        ux, uy = math.cos(angle), math.sin(angle)
        vx, vy = -uy, ux
        outline = ((0, 0), (.27, -.56), (.62, -1), (.93, -.70),
                   (1, curl), (.84, .65+curl), (.50, .83), (.22, .42))
        points = [coordinate for a, b in outline for coordinate in
                  (x + a*length*ux + b*width*vx, y + a*length*uy + b*width*vy)]
        self.shape(points, color)

    def stem(self, flower, index, progress):
        _, _, x, y, base_x, base_y, _, _ = flower
        bend = (x - base_x) * .34
        points = []
        for step in range(21):
            t = step * progress / 20
            points.extend((base_x + (x-base_x)*t*t + bend*t*(1-t),
                           base_y + (y-base_y)*t))
        if progress <= 0:
            return
        color = STEM_COLORS[index]
        self.line(points, "#253e38", 7 if index == 0 else 5)
        self.line(points, color, 4 if index == 0 else 2.5)
        for height, direction, length in ((.16, -1, 54), (.29, 1, 56)):
            leaf = smooth((progress-height)/.24)
            if leaf:
                lx = base_x + (x-base_x)*height**2 + bend*height*(1-height)
                ly = base_y + (y-base_y)*height
                angle = -2.68 if direction < 0 else -.52
                self.petal(lx, ly, angle, length*leaf, 10*leaf, color, -.28)
                self.line((lx, ly, lx+math.cos(angle)*length*leaf*.8,
                           ly+math.sin(angle)*length*leaf*.8), blend(color, "#e0cc9f", .35))

    def spider(self, x, y, scale):
        for i in range(6):
            angle = i * math.tau / 6 - 1.26
            length = (101 + 12*math.sin(i*2.8))*scale
            self.petal(x, y, angle, length, 20*scale, "#bf284d", -.88)
            self.petal(x, y, angle-.04, length*.91, 15*scale, "#f44c6b", -.76)
            self.petal(x, y, angle-.09, length*.76, 7*scale, "#ff8393", -.70)
            c, s = math.cos(angle), math.sin(angle)
            points = ((0, 0), (28, 3), (56, -1), (84, -11), (105, -25))
            self.line([p for a, b in points for p in
                       (x+scale*(a*c-b*s), y+scale*(a*s+b*c))], "#ff9fa9", 1.5)
        for i in range(9):
            angle = i * math.tau / 9 - 1.46
            length = (121 + 17*math.sin(i*2.3))*scale
            c, s = math.cos(angle), math.sin(angle)
            tx, ty = x+length*c, y+length*s
            self.line((x, y, x+length*.48*c+length*.16*s, y+length*.48*s-length*.16*c,
                       x+length*.83*c+length*.12*s, y+length*.83*s-length*.12*c, tx, ty),
                      "#e9988f", 1.45*scale)
            self.oval(tx, ty, 3.4*scale, 1.9*scale, "#ffe3a2")
        self.oval(x, y, 12*scale, 10*scale, "#8e294e")
        self.oval(x-2*scale, y-2*scale, 7*scale, 6*scale, "#ffd1ac")

    def bells(self, x, y, scale):
        self.line((x+19*scale, y+43*scale, x+18*scale, y-1*scale,
                   x+4*scale, y-28*scale, x-22*scale, y-30*scale),
                  "#a5bb8a", 2.6*scale)
        for dx, dy, size in ((-21,-25,.57), (-6,-20,.70), (5,-9,.80),
                             (11,4,.91), (14,18,1.0), (16,34,1.04)):
            bx, by = x+(dx-9)*scale, y+dy*scale
            k = size*scale*1.12
            self.line((bx+13*k, by-9*k, bx+3*k, by-7*k, bx, by+2*k),
                      "#a5bb8a", 1.7*k)
            self.shape((bx, by, bx-7*k, by+3*k, bx-9*k, by+12*k, bx-11*k, by+15*k,
                        bx+11*k, by+15*k, bx+8*k, by+11*k, bx+6*k, by+3*k), "#fff2cf")
            self.oval(bx, by+14*k, 8*k, 3.4*k, "#c6bfa4")
            self.oval(bx-2*k, by+5*k, 3*k, 4*k, "#fff8e6")

    def orchid(self, x, y, scale):
        self.line((x+21*scale, y+34*scale, x, y+13*scale,
                   x-3*scale, y-6*scale, x+13*scale, y-23*scale),
                  "#839669", 2.5*scale)
        for dx, dy, size in ((24, 30, .65), (-17, 13, .85), (13, -22, 1)):
            bx, by = x+dx*scale, y+dy*scale
            k = size*scale
            for i, angle in enumerate((-1.57, -.30, .78, 2.36, 3.44)):
                self.petal(bx, by, angle, (37 if i % 2 else 31)*k, 13*k, "#9b588a")
                self.petal(bx, by-2*k, angle, (35 if i % 2 else 29)*k, 11*k,
                           ("#f3b9e2", "#e29bd2", "#edb0de")[i % 3])
                self.petal(bx, by, angle, 20*k, 2*k, "#b969a4")
            self.petal(bx, by-2*k, 1.57, 17*k, 8*k, "#a42c71")
            self.oval(bx, by, 6*k, 5*k, "#fff0a9")

    def hydrangea(self, x, y, scale):
        rng = random.Random(31)
        for i in range(20):
            angle = i*2.399963
            radius = math.sqrt((19-i)/19) * 43
            bx = x + math.cos(angle)*radius*scale
            by = y + math.sin(angle)*radius*.84*scale
            k = scale*rng.uniform(.75, 1.14)
            color = rng.choice(("#9d9be8", "#b5a7ed", "#838cda", "#c3b5f1", "#7884ca"))
            for j in range(4):
                self.petal(bx, by, angle+j*math.pi/2, 12*k, 5.6*k, color)
            self.oval(bx, by, 2.4*k, 2.4*k, "#ffedbb")

    def mum(self, x, y, scale):
        for row in range(5):
            count = 17-row*2
            for i in range(count):
                angle = i*math.tau/count+row*.46
                length = (50-row*8)*scale
                color = blend("#cd713d", "#ffe6a0", row*.19 + .10*(i%3))
                self.petal(x, y, angle, length, (5.8-row*.72)*scale, color, .55)
        self.oval(x, y, 8*scale, 8*scale, "#a85636")
        for i in range(7):
            self.oval(x+math.cos(i)*3.4*scale, y+math.sin(i)*3.4*scale,
                      1.2*scale, 1.2*scale, "#ffe4a6")

    def background(self, tick, elapsed):
        for i, (x, y) in enumerate(self.noise):
            if (i + tick//3) % 7 < 2:
                self.cells[round(y/ROW_HEIGHT), round(x/self.column_width)] = NOISE
        self.label(58, 36, "bored_flower.py", 14, MUTED, anchor="w")
        self.label(942, 36, f"t = {elapsed:05.2f}s", 14, MUTED, anchor="e")
        self.label(500, 86, "B L O O M   F O R   Y O U", 26)

    def foliage(self, elapsed):
        leaves = (
            (496, 525, -2.84, 63, 9, "#476a35"),
            (504, 524, -.42, 65, 10, "#527c3c"),
            (497, 509, -2.86, 91, 12, "#597e3a"),
            (503, 506, -.31, 86, 12, "#5f8b42"),
            (497, 489, -2.91, 99, 12, "#466e3d"),
            (503, 487, -.38, 106, 13, "#527e44"),
            (493, 478, -2.63, 104, 14, "#628d47"),
            (506, 471, -.62, 104, 14, "#6a9148"),
            (485, 461, -2.55, 111, 13, "#426d42"),
            (517, 453, -.56, 103, 12, "#4c7842"),
            (481, 446, -2.33, 91, 12, "#548048"),
            (521, 441, -.87, 91, 11, "#618846"),
            (476, 433, -2.28, 94, 10, "#426d3d"),
            (525, 430, -.90, 90, 11, "#648e48"),
        )
        for index, (x, y, angle, length, width, color) in enumerate(leaves):
            growth = smooth((elapsed-.9-index*.09)/2.5)
            if growth <= 0:
                continue
            reach = length*growth
            self.petal(x, y, angle, reach, width*growth, color, -.4)
            self.line((x, y, x+math.cos(angle)*reach*.88,
                       y+math.sin(angle)*reach*.88), blend(color, "#c0c98a", .40))

    def soil(self, elapsed):
        fade = smooth((elapsed-2.2)/2.5)
        if fade < 1:
            self.oval(500, 571, 92, 10, blend("#484449", BLACK, fade))
            self.oval(500, 566, 81, 5, blend("#777079", BLACK, fade))
        if self.started is None:
            self.oval(500, 549, 10, 5, "#ffffff")

    def button(self, x, y, text, primary=False):
        self.label(x, y, text, 16, INK if primary else MUTED)

    def frame(self):
        now = time.monotonic()
        elapsed = now-self.started if self.started is not None else 0
        self.canvas.delete("all")
        self.cells.clear()
        tick = int(now * 8)
        self.background(tick, min(elapsed, 4.75))
        self.soil(elapsed)
        self.hits = []
        progress = []
        for species, flower, _ in STEMS:
            delay = flower[6]
            stem = smooth((elapsed-delay-.38)/2.25)
            bloom = smooth((elapsed-delay-1.55)/1.9)
            progress.append((stem, bloom))
            self.stem(flower, species, stem)
        self.foliage(elapsed)
        gathered = smooth((elapsed-1.7)/1.5)
        if gathered:
            for offset, color in ((-4, "#577f36"), (1, "#83a34d"), (5, "#5f883f")):
                self.line((500+offset, 569, 498+offset, 551,
                           501+offset, 569-39*gathered), color, 4)
        for index in BLOOM_ORDER:
            species, (kind, _, x, y, base_x, base_y, _, _), size = STEMS[index]
            stem, bloom = progress[index]
            if bloom:
                bend = (x-base_x)*.34
                bx = base_x + (x-base_x)*stem*stem + bend*stem*(1-stem)
                by = base_y + (y-base_y)*stem
                scale = size*bloom
                getattr(self, kind)(bx, by, scale)
                if bloom > .55:
                    self.hits.append((index, bx, by, BLOOM_RADII[species]*scale))
        self.water = [drop for drop in self.water if now-drop[0] < .95]
        for born, x, delay in self.water:
            age = (now-born-delay)/.63
            if 0 <= age <= 1:
                self.oval(x, 448+111*age**1.8, 2.2, 5, "#a7dce6")
        self.particles = [p for p in self.particles if now-p[0] < 1.1]
        for born, x, y, vx, vy in self.particles:
            age = now-born
            size = 2.7*(1-age/1.1)
            self.oval(x+vx*age, y+vy*age+62*age*age, size, size, "#ffd2a4")
        self.render_ascii(tick)
        if self.selected is not None:
            _, name, _, _, _, _, _, note = STEMS[self.selected][1]
            self.label(500, 606, name, 19, INK)
            self.label(500, 631, note, 14, INK)
        else:
            hint = ("Click the soil or water the seed to begin." if self.started is None else
                    "Your flowers are growing…" if elapsed < 4.7 else
                    "Pick a flower to find a little note.")
            self.label(500, 621, hint, 15, MUTED)
        self.button(500, 667, "[ Space : Water ]", True)
        self.button(665, 667, "[ R : Reset ]")
        self.root.after(33 if (self.started is not None and elapsed < 4.8)
                        or self.water or self.particles else 100, self.frame)

    def water_soil(self):
        now = time.monotonic()
        if self.started is None:
            self.started = now
        self.water = [(now, 500+random.uniform(-35, 35), random.uniform(0, .30))
                      for _ in range(23)]

    def reset(self):
        self.started = self.selected = None
        self.water.clear()
        self.particles.clear()
        self.hits.clear()

    def reveal(self, index):
        for flower, x, y, _ in self.hits:
            if flower == index:
                self.selected = index
                now = time.monotonic()
                self.particles = [(now, x, y, random.uniform(-103, 103),
                                   random.uniform(-125, -32)) for _ in range(30)]
                return

    def target(self, event):
        x, y = (event.x-self.left)/self.scale, (event.y-self.top)/self.scale
        if 647 <= y <= 688:
            if 427 <= x <= 573:
                return "water"
            if 600 <= x <= 730:
                return "reset"
        candidates = [(math.hypot(x-bx, y-by), index, radius)
                      for index, bx, by, radius in self.hits]
        flower = min(((distance, index) for distance, index, radius in candidates
                      if distance <= radius), default=None)
        if flower is not None:
            return flower[1]
        if ((x-500)/92)**2 + ((y-564)/25)**2 <= 1:
            return "water"
        return None

    def hover(self, event):
        self.canvas.configure(cursor="hand2" if self.target(event) is not None else "")

    def click(self, event):
        target = self.target(event)
        if target == "water":
            self.water_soil()
        elif target == "reset":
            self.reset()
        elif target is not None:
            self.reveal(target)


if __name__ == "__main__":
    window = tk.Tk()
    Garden(window)
    window.mainloop()
