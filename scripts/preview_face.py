"""render the real motion geometry for inspection without a display or microphone"""
import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ui.face import FACE_COLOUR, INK, FaceMotion, blend, geometry


def main():
    from PIL import Image, ImageDraw, ImageFont
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    width, height, fps = 720, 450, 20
    motion = FaceMotion(11)
    frames = []
    stages = [(0, 'Ready', 'neutral', 'At ease'), (1.7, 'Listening', 'curious', 'Listening'),
              (3.4, 'Thinking', 'attentive', 'Thinking'), (5.1, 'Speaking', 'warm', 'Speaking'),
              (7.4, 'Ready', 'happy', 'A little pleased')]
    stage = -1
    for index in range(180):
        now = index / fps
        current = max(i for i, row in enumerate(stages) if row[0] <= now)
        if current != stage:
            stage = current
            _, state, expression, label = stages[stage]
            motion.state = state
            motion.set_expression(expression, now)
        if motion.state == 'Speaking':
            # synthetic envelope demonstrates the same path real playback drives
            level = max(0., math.sin(now * 12) * .35 + .25) if int(now * 3) % 4 else 0.
            motion.audio((level, .5 + math.sin(now * 8) * .3), now)
        values = motion.step(now)
        shapes = geometry(width * 2, (height - 35) * 2, values)
        image = Image.new('RGB', (width * 2, height * 2), FACE_COLOUR)
        draw = ImageDraw.Draw(image)
        def points(coords):
            return list(zip(coords[::2], coords[1::2]))
        for coords in shapes['cheeks']:
            draw.polygon(points(coords), fill=blend(FACE_COLOUR, '#ec9399', shapes['blush']))
        for coords in shapes['eyes']:
            draw.polygon(points(coords), fill=INK)
        if shapes['opening'] > .055:
            draw.polygon(points(shapes['mouth']), fill=INK)
        else:
            draw.line(points(shapes['closed']), fill=INK, width=round(shapes['stroke']), joint='curve')
        image = image.resize((width, height), Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(image)
        draw.text((width / 2, height - 25), label + '  /  motion preview', anchor='mm', fill=INK,
                  font=ImageFont.truetype('DejaVuSans.ttf', 13))
        frames.append(image)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(args.output, save_all=True, append_images=frames[1:], duration=round(1000/fps), loop=0)
    frames[110].save(args.output.with_suffix('.png'))
    print(args.output)


if __name__ == '__main__':
    main()
