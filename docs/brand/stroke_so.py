"""Draws "So" as a clean brush stroke: the pen path (so_pen.py) with its width measured from the original logo at
every point, so the shape matches the logo while the edges stay smooth and nothing is missing where the brush went
faint or crossed the letters. Writes logo-so.svg.

Usage: python stroke_so.py  (needs numpy and Pillow)
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image

import so_pen

HERE = Path(__file__).resolve().parent


def sample(points, per=40):
    """Dense points along the Catmull-Rom curve through the points."""
    out = []
    start = points[0]
    for c1, c2, end in so_pen.catmull(points):
        for t in np.linspace(0, 1, per, endpoint=False):
            out.append(((1 - t) ** 3 * start[0] + 3 * (1 - t) ** 2 * t * c1[0] + 3 * (1 - t) * t ** 2 * c2[0] + t ** 3 * end[0],
                        (1 - t) ** 3 * start[1] + 3 * (1 - t) ** 2 * t * c1[1] + 3 * (1 - t) * t ** 2 * c2[1] + t ** 3 * end[1]))
        start = end
    out.append(points[-1])
    return np.array(out)


def brush_mask():
    a = np.asarray(Image.open(HERE / "logo.png").convert("RGBA")).astype(int)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    return (al > 40) & (((b - r) > 30) | (((r + g + b) >= 300) & ((b - r) > 6)))


def widths(line, mask, reach=26, gap=4):
    """The brush's width across the line at each point: the run of brush pixels through it along the normal."""
    h, w = mask.shape
    out = []
    for i, (x, y) in enumerate(line):
        a, b = line[max(i - 2, 0)], line[min(i + 2, len(line) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        nx, ny = -dy / n, dx / n
        ends = []
        for sign in (1, -1):
            miss, last = 0, 0
            for s in range(1, reach):
                px, py = int(round(x + sign * nx * s)), int(round(y + sign * ny * s))
                if 0 <= px < w and 0 <= py < h and mask[py, px]:
                    miss, last = 0, s
                else:
                    miss += 1
                    if miss > gap:
                        break
            ends.append(last)
        out.append(ends[0] + ends[1] + 1)
    return np.array(out, float)


def smooth(values, lo, hi):
    v = np.clip(values, lo, hi)
    k = 9  # a running max fills faint spots, then a running mean smooths the edge
    padded = np.pad(v, k // 2, mode="edge")
    v = np.array([padded[i:i + k].max() for i in range(len(v))])
    padded = np.pad(v, k, mode="edge")
    return np.convolve(padded, np.ones(2 * k + 1) / (2 * k + 1), mode="same")[k:-k]


def outline(line, half):
    """The brush shape: round stamps of the given radius along the line, each joined to the next by their hull."""
    from shapely.geometry import Point
    from shapely.ops import unary_union
    stamps = [Point(x, y).buffer(max(r, 0.6), 24) for (x, y), r in zip(line, half)]
    return unary_union([stamps[i].union(stamps[i + 1]).convex_hull for i in range(len(stamps) - 1)])


def svg_path(shape):
    """SVG path data of a (Multi)Polygon: every outer ring and hole."""
    polygons = getattr(shape, "geoms", [shape])
    rings = []
    for poly in polygons:
        poly = poly.simplify(0.15)
        for ring in [poly.exterior, *poly.interiors]:
            rings.append("M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in ring.coords[:-1]) + " Z")
    return " ".join(rings)


# (min, max) width per segment, and how the ends taper (fraction of the length that thins to `tip`)
LIMITS = [(10, 24), (9, 22), (3, 34), (2.5, 4), (10, 24), (2, 13)]
# where the stroke thins to a point: (segment, which end, fraction of its length, width at the tip)
TAPERS = [(0, "end", 0.12, 5), (1, "start", 0.12, 5), (2, "end", 0.18, 3), (4, "start", 0.14, 4), (5, "end", 0.35, 2)]


def build():
    from shapely.ops import unary_union
    mask = brush_mask()
    shapes = []
    for index, (points, _) in enumerate(so_pen.SEGMENTS):
        line = sample(points)
        lo, hi = LIMITS[index]
        width = smooth(widths(line, mask), lo, hi) if index != 3 else np.full(len(line), 3.5)
        for segment, side, part, tip in TAPERS:
            if segment != index:
                continue
            n = int(len(width) * part)
            if side == "end":
                width[-n:] = np.minimum(width[-n:], np.linspace(width[-n], tip, n))
            else:
                width[:n] = np.minimum(width[:n], np.linspace(tip, width[n], n))
        shapes.append(outline(line, width / 2))
    d = svg_path(unary_union(shapes))
    (HERE / "logo-so.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 847 430" width="847" '
                                      f'height="430"><path fill="#000" fill-rule="evenodd" d="{d}"/></svg>\n')
    print("So:", len(d), "chars")


if __name__ == "__main__":
    build()
