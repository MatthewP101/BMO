"""time-based face motion and persistent canvas shapes; no tkinter in the motion model"""
import math
import random
from dataclasses import dataclass

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


class FaceMotion:
    def __init__(self, seed=None):
        self.random = random.Random(seed)
        self.state = 'Ready'
        self.expression = 'neutral'
        self.mode = 'companion'
        self.reduced = False
        self.level = self.roundness = 0.0
        self.last_audio = -1000.0
        self.last_time = None
        self.next_blink = 3.0
        self.blink_start = -1000.0
        self.next_gaze = 0
        self.gaze = (0.0, 0.0)
        self.pointer_until = 0.0
        self.expression_until = 0.0
        self.values = dict(x=0., y=0., tilt=0., eye=1., smile=.30, blush=0., mouth=0., round=0., lean=1.)

    def set_expression(self, name, now):
        self.expression = name
        self.expression_until = now + 9

    def audio(self, shape, now):
        self.level, self.roundness = shape
        self.last_audio = now

    def look_at(self, x, y, now):
        self.gaze = (max(-1., min(1., x)) * .035, max(-1., min(1., y)) * .022)
        self.pointer_until = now + 1.2

    def step(self, now):
        dt = min(.1, max(0., now - self.last_time)) if self.last_time is not None else .025
        self.last_time = now
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
        target = dict(x=self.gaze[0], y=self.gaze[1], tilt=0., eye=1., smile=.30,
                      blush=0., mouth=0., round=0., lean=1.)
        if expression in ('warm', 'happy'):
            target.update(smile=.65, blush=.65 if expression == 'warm' else .15, eye=.78)
        elif expression == 'curious':
            target.update(tilt=-.035, eye=1.13, smile=.18)
        elif expression == 'attentive' or self.mode == 'focus':
            target.update(smile=.14, eye=.94)
        if self.state == 'Listening':
            target.update(lean=1.035, eye=1.1, smile=.12, tilt=-.026, x=0., y=-.009)
        elif self.state in ('Thinking', 'Transcribing', 'Preparing voice'):
            target.update(x=.019, y=-.023, smile=.10, tilt=.018)
        if now - self.last_audio < .16 and self.state == 'Speaking':
            target.update(mouth=max(0., min(1., self.level)), round=self.roundness)
        if self.reduced:
            target.update(x=0., y=0., tilt=0., lean=1.)
        else:
            target['y'] += math.sin(now * 1.6) * .003
            target['tilt'] += math.sin(now * .65) * .005
        for key in self.values:
            speed = 23 if key == 'mouth' else 7
            self.values[key] += (target[key] - self.values[key]) * (1 - math.exp(-speed * dt))
        return {**self.values, 'blink': closure}


def geometry(width, height, values):
    # a uniform scale keeps the face's proportions on every aspect ratio
    scale = max(1., min(width * .93, height * 1.55)) * values['lean']
    cx, cy = width / 2, height * .47
    angle = values['tilt']
    def point(x, y):
        x += values['x']
        y += values['y']
        return (cx + scale * (x * math.cos(angle) - y * math.sin(angle)),
                cy + scale * (x * math.sin(angle) + y * math.cos(angle)))
    def ellipse(x, y, rx, ry):
        return [c for i in range(32) for c in point(x + rx * math.cos(i * math.tau / 32),
                                                    y + ry * math.sin(i * math.tau / 32))]
    eye_y = -.075
    eye_height = max(.0025, .032 * values['eye'] * (1 - values['blink']))
    eyes = [ellipse(x, eye_y, .018, eye_height) for x in (-.205, .205)]
    smile = values['smile']
    closed = [c for i in range(25) for c in point(-.083 + .166 * i / 24,
              .067 + smile * .075 * math.sin(math.pi * i / 24))]
    opening = values['mouth']
    rx = .072 - values['round'] * .016
    ry = .009 + .052 * opening
    mouth = ellipse(0., .093, rx, ry)
    cheeks = [ellipse(x, .054, .052, .019) for x in (-.235, .235)]
    return dict(eyes=eyes, closed=closed, mouth=mouth, cheeks=cheeks,
                stroke=max(2., scale * .008), opening=opening, blush=values['blush'])


class FaceRenderer:
    def __init__(self, canvas):
        self.canvas = canvas
        self.motion = FaceMotion()
        self.cheeks = [canvas.create_polygon(0, 0, 0, 0, 0, 0, fill=FACE_COLOUR, smooth=True) for _ in range(2)]
        self.eyes = [canvas.create_polygon(0, 0, 0, 0, 0, 0, fill=INK, smooth=True) for _ in range(2)]
        self.smile = canvas.create_line(0, 0, 1, 1, fill=INK, smooth=True, capstyle='round')
        self.mouth = canvas.create_polygon(0, 0, 0, 0, 0, 0, fill=INK, smooth=True, state='hidden')

    def draw(self, now):
        values = self.motion.step(now)
        shape = geometry(self.canvas.winfo_width(), self.canvas.winfo_height(), values)
        for item, coords in zip(self.eyes, shape['eyes']):
            self.canvas.coords(item, *coords)
        colour = blend(FACE_COLOUR, '#ec9399', shape['blush'])
        for item, coords in zip(self.cheeks, shape['cheeks']):
            self.canvas.coords(item, *coords)
            self.canvas.itemconfigure(item, fill=colour)
        self.canvas.coords(self.smile, *shape['closed'])
        self.canvas.itemconfigure(self.smile, width=shape['stroke'], state='hidden' if shape['opening'] > .055 else 'normal')
        self.canvas.coords(self.mouth, *shape['mouth'])
        self.canvas.itemconfigure(self.mouth, state='normal' if shape['opening'] > .055 else 'hidden')


def blend(a, b, amount):
    amount = max(0., min(1., amount))
    channels = [round(int(a[i:i+2], 16) * (1 - amount) + int(b[i:i+2], 16) * amount) for i in (1, 3, 5)]
    return '#' + ''.join(f'{c:02x}' for c in channels)
