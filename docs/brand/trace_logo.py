"""Splits the logo into its dark "SAY" and blue "So" stroke and traces each into an SVG (same viewBox)."""
import sys
import numpy as np
import potrace
from PIL import Image, ImageFilter

src, out = sys.argv[1], sys.argv[2]
im = Image.open(src).convert("RGBA")
SCALE = 4
big = im.resize((im.width * SCALE, im.height * SCALE), Image.LANCZOS)
a = np.asarray(big).astype(int)
r, g, b, alpha = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
blue = (alpha > 40) & (((b - r) > 30) | ((r + g + b >= 300) & ((b - r) > 6)))  # semi-transparent brush; grey letter edges stay out
dark = (alpha > 128) & ~blue & (r + g + b < 300)

def smooth(mask, close=0, blur=2):
    """close: fills holes and nicks up to about that size (in 4x pixels) before the edges are smoothed."""
    img = Image.fromarray((mask * 255).astype(np.uint8))
    if close:
        img = img.filter(ImageFilter.MaxFilter(close)).filter(ImageFilter.MinFilter(close))
    return np.asarray(img.filter(ImageFilter.GaussianBlur(blur))) > 127

def svg(mask, name, close=0, blur=2):
    curves = potrace.Bitmap(~smooth(mask, close, blur)).trace(turdsize=200, alphamax=1.1, opticurve=True, opttolerance=0.6)
    d = []
    f = lambda p: f"{p.x / SCALE:.2f} {p.y / SCALE:.2f}"
    for c in curves:
        d.append("M" + f(c.start_point))
        for s in c.segments:
            d.append(("L" + f(s.c) + " L" + f(s.end_point)) if s.is_corner else
                     ("C" + f(s.c1) + " " + f(s.c2) + " " + f(s.end_point)))
        d.append("Z")
    path = " ".join(d)
    open(f"{out}/{name}.svg", "w").write(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {im.width} {im.height}" width="{im.width}" height="{im.height}">'
        f'<path fill="#000" fill-rule="evenodd" d="{path}"/></svg>\n')
    print(name, len(curves), "curves", len(path), "chars")

svg(dark, "logo-say")
svg(blue, "logo-so-trace", close=21, blur=7)
