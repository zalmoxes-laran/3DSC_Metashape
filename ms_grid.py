"""The rotated grid of the block cut, pure Python (no Metashape inside).

Metashape's Block Model lays its grid in a coordinate system of our choice
(``buildModel(blocks_crs=..., blocks_origin=...)``, Metashape 2.3.2). To turn
the grid with a monument, 3DSC hands it a **local oblique Mercator** centred on
the site, scale 1, whose grid is turned by the monument's bearing. The chunk is
never touched: its CRS and transform stay as they are, nothing rotated is ever
saved, and the same bearing gives the same cut every time.

Measured 8 Nov 2026 (Metashape 2.3.2, Stereo70 chunk, 40 × 16 m slab turned by
10°): north grid 20 blocks of 8 m, rotated grid 13. Metashape names the
projection ``Oblique_Mercator`` (EPSG method 9815) and spells the parameter
``recitified_grid_angle``, as GDAL does.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Sequence, Tuple

Point = Tuple[float, float]

# the oblique Mercator's own azimuth; the grid turns by AZIMUTH - rectified angle
AZIMUTH = 45.0


def oblique_wkt(geogcs_wkt: str, lat: float, lon: float, bearing_deg: float) -> str:
    """WKT of a local oblique Mercator centred on (lat, lon) whose grid y axis
    points at ``bearing_deg`` (clockwise from true north). Built on the chunk's
    own GEOGCS, so no datum change sits between the chunk and its grid."""
    gamma = AZIMUTH - bearing_deg
    return ('PROJCS["3DSC block grid",%s,PROJECTION["Oblique_Mercator"],'
            'PARAMETER["latitude_of_center",%.10f],PARAMETER["longitude_of_center",%.10f],'
            'PARAMETER["azimuth",%.1f],PARAMETER["recitified_grid_angle",%.8f],'
            'PARAMETER["scale_factor",1],PARAMETER["false_easting",0],'
            'PARAMETER["false_northing",0],UNIT["metre",1]]'
            % (geogcs_wkt, lat, lon, AZIMUTH, gamma))


def reduce_bearing(bearing_deg: float) -> float:
    """A square grid looks the same every 90°: the bearing in [-45, 45)."""
    return (bearing_deg + 45.0) % 90.0 - 45.0


def bearing_of(p: Point, q: Point) -> float:
    """Bearing (deg, clockwise from +y) of the segment p→q."""
    return math.degrees(math.atan2(q[0] - p[0], q[1] - p[1]))


def convex_hull(points: Iterable[Point]) -> List[Point]:
    pts = sorted(set((float(x), float(y)) for x, y in points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def rotate(points: Iterable[Point], bearing_deg: float) -> List[Point]:
    """Coordinates in a frame whose y axis points at ``bearing_deg``."""
    b = math.radians(bearing_deg)
    c, s = math.cos(b), math.sin(b)
    return [(x * c - y * s, x * s + y * c) for x, y in points]


def fit_bearing(points: Sequence[Point]) -> float:
    """The bearing of the tightest (minimum-area) rectangle around the points,
    reduced to [-45, 45): the grid that wastes the least around the mesh."""
    hull = convex_hull(points)
    if len(hull) < 3:
        return 0.0
    best = (float("inf"), 0.0)
    for i in range(len(hull)):
        b = reduce_bearing(bearing_of(hull[i], hull[(i + 1) % len(hull)]))
        r = rotate(hull, b)
        xs = [p[0] for p in r]
        ys = [p[1] for p in r]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if area < best[0] - 1e-9:
            best = (area, b)
    return best[1]


def layout(points: Sequence[Point], size: float) -> Dict[str, object]:
    """The grid of cells of side ``size`` tight around ``points`` (already in
    the grid frame): as few cells as the extent needs, centred on the mesh.
    → ``{"origin": (x, y), "nx", "ny", "extent": (w, h), "cells"}``."""
    if size <= 0:
        raise ValueError("cell size must be > 0")
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w, h = x1 - x0, y1 - y0
    nx = max(1, int(math.ceil(w / size - 1e-9)))
    ny = max(1, int(math.ceil(h / size - 1e-9)))
    ox = (x0 + x1) / 2.0 - nx * size / 2.0
    oy = (y0 + y1) / 2.0 - ny * size / 2.0
    return {"origin": (ox, oy), "nx": nx, "ny": ny, "extent": (w, h), "cells": nx * ny}


def cell_of(name: str):
    """``(i, j)`` from a Metashape tile name «Tile i-j» (negative indices too:
    «Tile -1--2» → (-1, -2)); None when it is not one."""
    base = name.rsplit(".", 1)[0]
    if not base.startswith("Tile "):
        return None
    body = base[5:]
    k = body.find("-", 1)
    while k != -1:
        try:
            return int(body[:k]), int(body[k + 1:])
        except ValueError:
            k = body.find("-", k + 1)
    return None


def thin(points: Sequence, limit: int = 20000) -> List:
    """At most ``limit`` evenly spaced points (enough for the hull of a mesh)."""
    n = len(points)
    if n <= limit:
        return list(points)
    step = n / float(limit)
    return [points[int(i * step)] for i in range(limit)]
