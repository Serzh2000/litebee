"""Contact sheet of downloaded, unaltered reference images (Pillow)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parent
refs = root / 'references'
items = [
    ('ired_01.jpg', '01 | FM-10 front / above | iRed'),
    ('ired_02.jpg', '02 | FM-10 right side | iRed'),
    ('fm10_871966.jpg', '03 | FM-10 opposite side | iRed'),
    ('fm10_348130.jpg', '04 | FM-10 TOP: frame, spacing, studs | iRed'),
    ('fm10_379367.jpg', '05 | FM-10 FRONT: height, cables | iRed'),
    ('manufacturer_front.jpg', '06 | FM FRONT | litebee.com'),
    ('fm_manual_page-05.png', '07 | FM exploded view | MGIT manual, p.2'),
    ('fm_manual_page-07.png', '08 | FM battery + light mounts | MGIT, p.4'),
    ('manufacturer_hardware.jpg', '09 | BASE Wing close-up, no FM light | LiteBee'),
]
board = Image.new('RGB', (1800, 1920), '#e9e9e6')
draw = ImageDraw.Draw(board)
try:
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 20)
except OSError:
    font = ImageFont.load_default()
for i, (name, label) in enumerate(items):
    im = Image.open(refs / name).convert('RGB')
    im.thumbnail((580, 585), Image.Resampling.LANCZOS)
    x, y = (i % 3) * 600, (i // 3) * 640
    board.paste(im, (x + (600-im.width)//2, y+40+(585-im.height)//2))
    draw.text((x+12, y+10), label, fill='#222222', font=font)
board.save(root / 'reference_board.jpg', quality=93)
