"""time-based face motion and persistent canvas shapes; no tkinter in the motion model"""
import math
import random
from dataclasses import dataclass
from ui.themes import palette

FACE_COLOUR = '#b7dfad'
INK = '#123c34'


@dataclass(frozen=True)
class Layout:
    face: tuple
    conversation: tuple
    horizontal: bool


def layout_for(width, height, face_only=False):
    width, height = max(1, width), max(1, height)
    margin, top = 10, 52
    available = max(1, height - top - margin)
    if face_only:
        return Layout((margin, top, max(1, width - 2 * margin), available), (0, 0, 0, 0), False)
    horizontal = width >= 680 and width / height >= 1.35
    if horizontal:
        panel = min(480, max(280, round(width * .36)))
        face_width = max(1, width - panel - 3 * margin)
        return Layout((margin, top, face_width, available),
                      (face_width + 2 * margin, top, panel, available), True)
    face_height = max(72, round(available * (.47 if height >= 700 else .36)))
    return Layout((margin, top, max(1, width - 2 * margin), face_height),
                  (margin, top + face_height + margin, max(1, width - 2 * margin),
                   max(1, available - face_height - margin)), False)


EXPRESSIONS = ('neutral', 'warm', 'blush', 'happy', 'curious', 'attentive', 'gentle',
               'surprised', 'sleepy', 'wink', 'love', 'game_over')


class FaceMotion:
    def __init__(self, seed=None):
        self.random = random.Random(seed)
        self.state, self.expression, self.mode = 'Ready', 'neutral', 'companion'
        self.reduced = False
        self.blush_mode = 'auto'
        self.blush_strength = .75
        self.idle_animations = True
        self.level = self.roundness = 0.0
        self.last_audio = -1000.0
        self.last_time = None
        self.next_blink = 3.0
        self.blink_start = -1000.0
        self.next_gaze = 0.0
        self.gaze = (0.0, 0.0)
        self.pointer_until = self.expression_until = self.expression_start = 0.0
        self.last_interaction = 0.0
        self.values = dict(x=0., y=0., tilt=0., eye=1., smile=.30, blush=0., mouth=0.,
                           round=0., lean=1., curve=0., wink=0., hearts=0., crosses=0., brow=0.)

    def set_expression(self, name, now, duration=None):
        if name not in EXPRESSIONS:
            name = 'neutral'
        self.expression = name
        self.expression_start = self.last_interaction = now
        duration = duration if duration is not None else {'wink': .85, 'game_over': 2.6, 'surprised': 2.2}.get(name, 7.)
        self.expression_until = now + max(.2, duration)

    def audio(self, shape, now):
        self.level, self.roundness = shape
        self.last_audio = now

    def look_at(self, x, y, now):
        self.gaze = (max(-1., min(1., x)) * .035, max(-1., min(1., y)) * .022)
        self.pointer_until = now + 1.2

    def step(self, now):
        dt = min(.1, max(0., now - self.last_time)) if self.last_time is not None else .025
        self.last_time = now
        if self.state != 'Ready':
            self.last_interaction = now
        if now >= self.next_blink:
            self.blink_start = now
            self.next_blink = now + self.random.uniform(2.7, 6.8)
            if self.random.random() < .12:
                self.next_blink = now + .34
        t = now - self.blink_start
        closure = math.sin(math.pi * t / .19) ** 2 if 0 <= t <= .19 else 0
        if now > self.next_gaze and now > self.pointer_until:
            self.gaze = (self.random.uniform(-.020, .020), self.random.uniform(-.010, .010))
            self.next_gaze = now + self.random.uniform(2.4, 5.2)
        expression = self.expression if now < self.expression_until else 'neutral'
        if (expression == 'neutral' and self.idle_animations and self.state == 'Ready'
                and self.mode != 'focus' and now - self.last_interaction > 120):
            expression = 'sleepy'
        target = dict(x=self.gaze[0], y=self.gaze[1], tilt=0., eye=1., smile=.30,
                      blush=0., mouth=0., round=0., lean=1., curve=0., wink=0., hearts=0., crosses=0., brow=0.)
        if expression == 'warm':
            target.update(smile=.65, blush=.7, eye=.85, curve=.35)
        elif expression == 'blush':
            target.update(smile=.65, blush=1., eye=.8, tilt=-.035, x=-.014, curve=.5)
        elif expression == 'happy':
            target.update(smile=.85, blush=.3, curve=1.)
        elif expression == 'love':
            target.update(smile=.75, blush=.9, hearts=1.)
        elif expression == 'wink':
            target.update(wink=1., smile=.65, tilt=-.025, blush=.4)
        elif expression == 'curious':
            target.update(tilt=-.035, eye=1.16, smile=.12, brow=.25)
        elif expression == 'surprised':
            target.update(eye=1.3, smile=0., mouth=.35, round=1., brow=.3)
        elif expression == 'sleepy':
            target.update(eye=.24, smile=.18, tilt=.025)
        elif expression == 'gentle':
            target.update(eye=.8, smile=.10, brow=-.35, tilt=-.012)
        elif expression == 'game_over':
            target.update(crosses=1., smile=-.12, tilt=.045, eye=.5)
        if expression == 'attentive' or self.mode == 'focus':
            target.update(smile=.14, eye=.94, curve=0., hearts=0., crosses=0., wink=0.)
        if self.state == 'Listening':
            target.update(lean=1.025, eye=1.08, tilt=-.02, y=-.009)
        elif self.state in ('Thinking', 'Transcribing', 'Preparing voice'):
            target.update(y=-.016)
            if expression == 'neutral':
                target.update(x=.019, smile=.12, tilt=.015)
        if self.state == 'Speaking':
            target.update(mouth=0., round=0.)
            if now - self.last_audio < .16:
                target.update(mouth=max(0., min(1., self.level)), round=self.roundness)
        if self.blush_mode == 'off':
            target['blush'] = 0.
        elif self.blush_mode == 'always':
            target['blush'] = 1.
        target['blush'] *= max(0., min(1., self.blush_strength))
        elapsed = now - self.expression_start
        if not self.reduced and self.idle_animations:
            target['y'] += math.sin(now * 1.6) * .003
            target['tilt'] += math.sin(now * .65) * .004
            if expression == 'happy' and 0 <= elapsed < 1.2 and self.mode != 'focus':
                target['y'] -= abs(math.sin(elapsed * math.pi * 2 / 1.2)) * .018 * (1-elapsed/1.2)
            if expression == 'game_over' and elapsed > 1.8:
                target['tilt'] *= max(0., (2.6-elapsed)/.8)
        if self.reduced or not self.idle_animations:
            target.update(x=0., y=0., tilt=0., lean=1.)
        for key in self.values:
            speed = 23 if key == 'mouth' else 6 if key == 'blush' else 9
            self.values[key] += (target[key] - self.values[key]) * (1 - math.exp(-speed * dt))
        return {**self.values, 'blink': closure}


def geometry(width, height, values):
    scale = max(1., min(width * .88, height * 1.42)) * values['lean']
    cx, cy = width / 2, height * .47
    angle = values['tilt']
    def point(x, y):
        x += values['x']; y += values['y']
        return (cx + scale * (x * math.cos(angle) - y * math.sin(angle)),
                cy + scale * (x * math.sin(angle) + y * math.cos(angle)))
    def ellipse(x, y, rx, ry):
        return [c for i in range(32) for c in point(x + rx * math.cos(i * math.tau / 32),
                                                   y + ry * math.sin(i * math.tau / 32))]
    curve = values.get('curve', 0.)
    hearts = values.get('hearts', 0.)
    eyes = []
    crosses, brows = [], []
    for i, centre in enumerate((-.205, .205)):
        wink = values.get('wink', 0.) if i == 0 else 0.
        rx = .018 + curve * .018 + wink * .01
        ry = max(.0025, .032 * values['eye'] * (1-values['blink']) * (1-curve*.87) * (1-wink*.94))
        coords = []
        for n in range(32):
            theta = n * math.tau / 32
            x, y = rx * math.cos(theta), ry * math.sin(theta)
            y += curve * .017 * ((x / rx)**2 - .5)
            heart_x = .003 * 16 * math.sin(theta)**3
            heart_y = -.003 * (13*math.cos(theta)-5*math.cos(2*theta)-2*math.cos(3*theta)-math.cos(4*theta))
            coords.extend(point(centre + x*(1-hearts) + heart_x*hearts, -.075 + y*(1-hearts) + heart_y*hearts))
        eyes.append(coords)
        for direction in (-1,1):
            crosses.append([*point(centre-.026, -.075-.03*direction), *point(centre+.026, -.075+.03*direction)])
        brow = values.get('brow', 0.)
        sign = -1 if i == 0 else 1
        brows.append([*point(centre-.03, -.135+sign*brow*.025), *point(centre+.03, -.135-sign*brow*.025)])
    smile = values['smile']
    closed = [c for i in range(25) for c in point(-.083 + .166*i/24,
              .067 + smile*.075*math.sin(math.pi*i/24))]
    opening = values['mouth']
    mouth = ellipse(0., .093, .072-values['round']*.02, .008+.052*opening)
    cheeks = [ellipse(x, .054, .05, .018) for x in (-.235,.235)]
    return dict(eyes=eyes, closed=closed, mouth=mouth, cheeks=cheeks, crosses=crosses, brows=brows,
                cross_amount=values.get('crosses',0.), brow_amount=abs(values.get('brow',0.)),
                stroke=max(2.,scale*.0075), opening=opening, blush=values['blush'])


class FaceRenderer:
    def __init__(self, canvas):
        self.canvas = canvas
        self.motion = FaceMotion()
        self.colours = palette('classic')
        self.cheeks = [canvas.create_polygon(0,0,0,0,0,0,fill=FACE_COLOUR,smooth=True) for _ in range(2)]
        self.eyes = [canvas.create_polygon(0,0,0,0,0,0,fill=INK,smooth=True) for _ in range(2)]
        self.smile = canvas.create_line(0,0,1,1,fill=INK,smooth=True,capstyle='round')
        self.mouth = canvas.create_polygon(0,0,0,0,0,0,fill=INK,smooth=True,state='hidden')
        self.crosses = [canvas.create_line(0,0,1,1,fill=INK,capstyle='round',state='hidden') for _ in range(4)]
        self.brows = [canvas.create_line(0,0,1,1,fill=INK,capstyle='round',state='hidden') for _ in range(2)]

    def set_theme(self, name):
        self.colours = palette(name)
        self.canvas.configure(bg=self.colours['face'])
        for item in self.eyes + [self.smile,self.mouth] + self.crosses + self.brows:
            self.canvas.itemconfigure(item, fill=self.colours['ink'])

    def draw(self, now):
        shape = geometry(self.canvas.winfo_width(),self.canvas.winfo_height(),self.motion.step(now))
        crossed = shape['cross_amount'] > .4
        for item, coords in zip(self.eyes,shape['eyes']):
            self.canvas.coords(item,*coords)
            self.canvas.itemconfigure(item,state='hidden' if crossed else 'normal')
        for item, coords in zip(self.crosses,shape['crosses']):
            self.canvas.coords(item,*coords)
            self.canvas.itemconfigure(item,state='normal' if crossed else 'hidden',width=shape['stroke'])
        for item, coords in zip(self.brows,shape['brows']):
            self.canvas.coords(item,*coords)
            self.canvas.itemconfigure(item,state='normal' if shape['brow_amount']>.2 else 'hidden',width=max(2,shape['stroke']*.65))
        colour = blend(self.colours['face'],self.colours['blush'],shape['blush'])
        for item, coords in zip(self.cheeks,shape['cheeks']):
            self.canvas.coords(item,*coords); self.canvas.itemconfigure(item,fill=colour)
        self.canvas.coords(self.smile,*shape['closed'])
        self.canvas.itemconfigure(self.smile,width=shape['stroke'],state='hidden' if shape['opening']>.055 else 'normal')
        self.canvas.coords(self.mouth,*shape['mouth'])
        self.canvas.itemconfigure(self.mouth,state='normal' if shape['opening']>.055 else 'hidden')


def blend(a, b, amount):
    amount = max(0.,min(1.,amount))
    channels = [round(int(a[i:i+2],16)*(1-amount)+int(b[i:i+2],16)*amount) for i in (1,3,5)]
    return '#' + ''.join(f'{c:02x}' for c in channels)
