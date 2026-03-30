"""Generates icon.icns (Mac) and icon.ico (Windows) from scratch. Run before PyInstaller."""
import sys, os, struct, zlib
from pathlib import Path

def make_rgba(size):
    """Generate a simple purple 'G' icon as raw RGBA bytes using pure Python (no Pillow)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGBA", (size, size), (15, 15, 15, 255))
        draw = ImageDraw.Draw(img)
        pad = size // 8
        r   = size // 5
        draw.rounded_rectangle([pad, pad, size-pad, size-pad], radius=r, fill=(26,26,26,255))
        font_size = int(size * 0.55)
        try:
            if sys.platform == 'darwin':
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
            else:
                font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()
        text = "G"
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        x = (size - tw)//2 - bbox[0]
        y = (size - th)//2 - bbox[1] - size//20
        draw.text((x+4, y+4), text, font=font, fill=(0,0,0,160))
        draw.text((x, y), text, font=font, fill=(124, 92, 191, 255))
        r2 = size//28
        cx, cy = size//2, size - size//7
        draw.ellipse([cx-r2, cy-r2, cx+r2, cy+r2], fill=(124, 92, 191, 255))
        return img
    except ImportError:
        # Fallback: solid purple square
        from PIL import Image
        return Image.new("RGBA", (size, size), (124, 92, 191, 255))

OUT = Path(__file__).parent

if sys.platform == 'darwin':
    import subprocess
    iconset = OUT / "icon.iconset"
    iconset.mkdir(exist_ok=True)
    master = make_rgba(1024)
    from PIL import Image
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    for s in sizes:
        master.resize((s, s), Image.LANCZOS).save(iconset / f"icon_{s}x{s}.png")
        if s <= 512:
            master.resize((s*2, s*2), Image.LANCZOS).save(iconset / f"icon_{s}x{s}@2x.png")
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(OUT / "icon.icns")], check=True)
    print(f"Created {OUT / 'icon.icns'}")

else:
    # Windows: create .ico with multiple sizes
    from PIL import Image
    import io
    sizes = [16, 32,48, 64, 128, 256]
    images = [make_rgba(s).convert("RGBA") for s in sizes]
    ico_path = OUT / "icon.ico"
    images[0].save(str(ico_path), format='ICO', sizes=[(s,s) for s in sizes],
                   append_images=images[1:])
    print(f"Created {ico_path}")
