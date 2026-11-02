"""The pen path of the "So" brush stroke, in the logo's coordinates (847 × 430): the order a hand writes it.

Each segment is (points, width): a Catmull-Rom curve through the points and the brush width it fills. The app uses it
to fill the parts of the stroke the brush left faint (so "So" is solid) and to write "So" in, stroke by stroke.
"""

SEGMENTS = [
    # S: the small hook at the bottom, up to the top, across to the sharp point on the left
    ([(449, 219), (472, 197), (494, 174), (487, 164), (450, 168), (400, 184), (340, 206), (270, 233), (217, 261),
      (205, 268)], 15),
    # back right through the middle
    ([(205, 268), (240, 268), (300, 262), (360, 257), (420, 251), (463, 249), (481, 253)], 13),
    # and the long swash down to the tail
    ([(481, 253), (455, 270), (400, 293), (320, 320), (240, 347), (160, 374), (90, 398), (40, 414)], 13),
    # the hairline over to the o
    ([(481, 253), (510, 243), (540, 233)], 4),
    # the o: up its left side, over the top, down the right, round the bottom and up again
    ([(540, 233), (578, 210), (615, 190), (650, 177), (676, 181), (678, 201), (655, 232), (615, 266), (570, 293),
      (534, 301), (524, 288), (535, 262), (562, 228), (605, 198), (645, 182)], 13),
    # the flourish out to the right
    ([(645, 182), (690, 187), (740, 168), (800, 145), (838, 131)], 6),
]


def catmull(points, steps=12):
    """Cubic Bézier segments (c1, c2, end) of a Catmull-Rom curve through the points."""
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        out.append((c1, c2, p2))
    return out


def svg_d(points):
    d = f"M{points[0][0]} {points[0][1]}"
    for c1, c2, end in catmull(points):
        d += f" C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {end[0]} {end[1]}"
    return d
