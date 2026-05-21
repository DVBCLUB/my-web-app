"""
MODULE BRANDING - Tài sản thương hiệu dùng trong biểu mẫu.
"""

from pathlib import Path


LOGO_PATH = Path('assets/trung_hai_logo.png')
APP_LOGO_PATH = Path('assets/fastrack_erp_logo.png')
APP_ICON_PATH = Path('assets/fastrack_erp.ico')


def ensure_logo_asset():
    """Tạo logo Trung Hải dạng PNG để chèn vào biểu mẫu nếu chưa có file ảnh."""
    if LOGO_PATH.exists():
        return str(LOGO_PATH)

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return ''

    LOGO_PATH.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new('RGBA', (360, 150), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    blue = (55, 58, 146, 255)
    red = (237, 35, 49, 255)

    draw.polygon([(22, 82), (165, 8), (314, 86), (226, 86), (155, 28), (74, 86)], fill=red)
    draw.polygon([(142, 8), (175, 8), (314, 86), (242, 86), (174, 31), (120, 76), (156, 103), (110, 103), (85, 84)], fill=blue)
    draw.polygon([(130, 65), (178, 26), (262, 92), (195, 92)], fill=(255, 255, 255, 255))
    draw.polygon([(142, 65), (178, 36), (236, 82), (194, 82)], fill=blue)

    try:
        font = ImageFont.truetype('arialbd.ttf', 34)
    except Exception:
        font = ImageFont.load_default()
    draw.text((38, 98), 'TRUNG HAI', fill=blue, font=font)

    img.save(LOGO_PATH)
    return str(LOGO_PATH)


def ensure_app_logo_asset():
    """Tạo logo FasTrack ERP dùng cho cửa sổ app và shortcut."""
    if APP_LOGO_PATH.exists() and APP_ICON_PATH.exists():
        return str(APP_LOGO_PATH), str(APP_ICON_PATH)

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return '', ''

    APP_LOGO_PATH.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new('RGBA', (1024, 1024), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    blue = (0, 132, 232, 255)
    dark_blue = (0, 70, 155, 255)
    yellow = (255, 183, 0, 255)
    silver = (235, 242, 250, 255)

    draw.rounded_rectangle([250, 190, 780, 610], radius=36, fill=(10, 36, 80, 220))
    for x, h in [(320, 210), (430, 270), (540, 330), (650, 410)]:
        draw.rounded_rectangle([x, 520 - h, x + 70, 610], radius=10, fill=blue)
        draw.rectangle([x, 520 - h + 12, x + 70, 610], fill=blue)

    draw.pieslice([205, 340, 820, 780], 160, 350, fill=yellow)
    draw.pieslice([235, 365, 790, 730], 160, 350, fill=dark_blue)
    draw.polygon([(650, 285), (825, 225), (780, 405)], fill=yellow)
    draw.polygon([(675, 322), (805, 245), (760, 390)], fill=(255, 210, 40, 255))

    try:
        big_font = ImageFont.truetype('arialbd.ttf', 190)
        name_font = ImageFont.truetype('arialbd.ttf', 120)
        erp_font = ImageFont.truetype('arialbd.ttf', 72)
        small_font = ImageFont.truetype('arialbd.ttf', 38)
    except Exception:
        big_font = name_font = erp_font = small_font = ImageFont.load_default()

    draw.text((330, 300), 'FT', fill=(20, 42, 85, 255), font=big_font, stroke_width=8, stroke_fill=silver)
    draw.text((145, 635), 'FasTrack', fill=blue, font=name_font, stroke_width=5, stroke_fill=silver)
    draw.text((425, 770), 'ERP', fill=yellow, font=erp_font, stroke_width=3, stroke_fill=(90, 60, 0, 255))
    draw.text((300, 870), 'PHẦN MỀM KẾ TOÁN', fill=silver, font=small_font)

    img.save(APP_LOGO_PATH)
    img.save(APP_ICON_PATH, sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
    return str(APP_LOGO_PATH), str(APP_ICON_PATH)


def ensure_bamboo_assets():
    """Tạo ảnh tre/lá trang trí header và nền sidebar."""
    header_path = Path('assets/bamboo_header.png')
    pattern_path = Path('assets/bamboo_pattern.png')
    header_path.parent.mkdir(parents=True, exist_ok=True)
    if header_path.exists() and pattern_path.exists():
        return str(header_path), str(pattern_path)

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return '', ''

    # Header banner 1200x90
    w, h = 1200, 90
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(13 + (27 - 13) * t)
        g = int(59 + (94 - 59) * t)
        b = int(46 + (64 - 46) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b, 255))
    greens = [(27, 94, 64), (46, 125, 50), (102, 187, 106), (165, 214, 167)]
    for i, x in enumerate([w - 80, w - 55, w - 30, w - 105]):
        c = greens[i % len(greens)]
        draw.line([(x, h - 5), (x - 8 + i * 3, 8)], fill=c, width=6)
        for y_leaf, dx in ((35, -28), (50, 24), (62, -20)):
            draw.ellipse([x + dx - 16, y_leaf - 5, x + dx + 16, y_leaf + 5], fill=greens[(i + 1) % len(greens)])
    for lx, ly in ((w - 140, 18), (w - 170, 38), (60, 22)):
        draw.ellipse([lx - 7, ly - 3, lx + 7, ly + 3], fill=(201, 162, 39, 255))
        draw.ellipse([lx - 5, ly - 6, lx + 5, ly], fill=(174, 213, 129, 255))
    img.save(header_path)

    # Pattern tile nhẹ
    tile = Image.new('RGBA', (120, 120), (238, 244, 240, 255))
    td = ImageDraw.Draw(tile)
    for x in (30, 55, 80):
        td.line([(x, 115), (x - 4, 15)], fill=(129, 199, 132, 80), width=3)
    tile.save(pattern_path)
    return str(header_path), str(pattern_path)
