"""Render the app's real face geometry; Pillow is needed only for this preview."""
import argparse
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ui.face import FaceMotion, EXPRESSIONS, blend, geometry
from ui.themes import palette


def render(motion, now, theme, width=640, height=380, label=''):
    from PIL import Image, ImageDraw, ImageFont
    colours=palette(theme)
    shape=geometry(width*2,(height-35)*2,motion.step(now))
    image=Image.new('RGB',(width*2,height*2),colours['face']);draw=ImageDraw.Draw(image)
    def points(coords):return list(zip(coords[::2],coords[1::2]))
    def line(coords,width):
        pts=points(coords);draw.line(pts,fill=colours['ink'],width=width,joint='curve')
        radius=width/2
        for x,y in (pts[0],pts[-1]):draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=colours['ink'])
    for coords in shape['cheeks']:
        draw.polygon(points(coords),fill=blend(colours['face'],colours['blush'],shape['blush']))
    if shape['cross_amount']>.4:
        for coords in shape['crosses']:line(coords,round(shape['stroke']))
    else:
        for coords in shape['eyes']:draw.polygon(points(coords),fill=colours['ink'])
    if shape['brow_amount']>.2:
        for coords in shape['brows']:line(coords,max(2,round(shape['stroke']*.65)))
    if shape['opening']>.055:draw.polygon(points(shape['mouth']),fill=colours['ink'])
    else:line(shape['closed'],round(shape['stroke']))
    image=image.resize((width,height),Image.Resampling.LANCZOS)
    if label:
        ImageDraw.Draw(image).text((width/2,height-20),label,anchor='mm',fill=colours['ink'],font=ImageFont.truetype('DejaVuSans.ttf',14))
    return image


def main():
    from PIL import Image
    parser=argparse.ArgumentParser()
    parser.add_argument('output',type=Path)
    parser.add_argument('--sheet',type=Path)
    args=parser.parse_args()
    stages=[('warm','Here with you'),('blush','Oh. You noticed.'),('happy','A little pleased'),
            ('wink','Our little secret'),('love','Heart eyes'),('game_over','One more life?'),
            ('gentle','Listening closely'),('surprised','Oh!')]
    motion=FaceMotion(11);frames=[];fps=20;stage=-1
    for i in range(len(stages)*40):
        now=i/fps;current=i//40
        if current!=stage:
            stage=current;expression,label=stages[stage];motion.set_expression(expression,now)
        frames.append(render(motion,now,'classic' if stage<4 else 'pink',label=label))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    frames[0].save(args.output,save_all=True,append_images=frames[1:],duration=50,loop=0)
    if args.sheet:
        sheet=Image.new('RGB',(4*320,6*200),'white')
        for theme_index,theme in enumerate(('classic','pink')):
            for index,name in enumerate(EXPRESSIONS):
                motion=FaceMotion(11);motion.set_expression(name,0)
                for i in range(20):motion.step(i/40)
                tile=render(motion,.5,theme,320,200,name.replace('_',' '))
                sheet.paste(tile,((index%4)*320,(index//4+theme_index*3)*200))
        sheet.save(args.sheet)
    print(args.output)


if __name__=='__main__':main()
