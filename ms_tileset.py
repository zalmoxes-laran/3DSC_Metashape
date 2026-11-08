"""Reading back an exported Cesium tileset, pure Python (no Metashape inside).

After the export, 3DSC reads the FILE (a .3tz archive or a folder), not what
it asked Metashape to write: tiles per level, primitives per tile (one per
texture page: each is a draw call), size, and where the root sits on the Earth
(lat, lon and ellipsoidal height of the root transform). Checking the height
on the written file is what keeps a height correction from being tautological
(lesson of 7 Nov 2026).
"""

from __future__ import annotations

import json
import math
import os
import posixpath
import struct
import zipfile
from typing import Dict, List, Optional


class _Source:
    def __init__(self, path: str):
        self.path = path
        self.zip = zipfile.ZipFile(path) if os.path.isfile(path) else None

    def read(self, name: str) -> bytes:
        name = name.lstrip("./") if name.startswith("./") else name
        if self.zip is not None:
            return self.zip.read(name)
        with open(os.path.join(self.path, name), "rb") as f:
            return f.read()

    def size(self) -> int:
        if self.zip is not None:
            return os.path.getsize(self.path)
        total = 0
        for root, _d, files in os.walk(self.path):
            for fn in files:
                total += os.path.getsize(os.path.join(root, fn))
        return total


def glb_primitives(data: bytes) -> Optional[int]:
    """Primitives in a .glb (or a .b3dm wrapping one); None if unreadable."""
    if data[:4] == b"b3dm":
        ft_json, ft_bin, bt_json, bt_bin = struct.unpack("<4I", data[12:28])
        data = data[28 + ft_json + ft_bin + bt_json + bt_bin:]
    if data[:4] != b"glTF":
        return None
    length = struct.unpack("<I", data[16:20])[0]
    doc = json.loads(data[20:20 + length].decode("utf-8"))
    return sum(len(m.get("primitives", [])) for m in doc.get("meshes", []))


def ecef_to_geodetic(x: float, y: float, z: float):
    """WGS84 lat, lon (deg) and ellipsoidal height (m), Bowring's method."""
    a, f = 6378137.0, 1 / 298.257223563
    b = a * (1 - f)
    e2 = 1 - (b * b) / (a * a)
    ep2 = (a * a) / (b * b) - 1
    p = math.hypot(x, y)
    th = math.atan2(z * a, p * b)
    lat = math.atan2(z + ep2 * b * math.sin(th) ** 3, p - e2 * a * math.cos(th) ** 3)
    lon = math.atan2(y, x)
    n = a / math.sqrt(1 - e2 * math.sin(lat) ** 2)
    h = p / math.cos(lat) - n
    return math.degrees(lat), math.degrees(lon), h


def inspect(path: str, max_tiles: int = 200000) -> Dict[str, object]:
    """→ ``{"levels": {depth: tiles}, "tiles", "primitives_mean", "primitives_max",
    "bytes", "root": {lat, lon, h} or None, "version", "geometric_error"}``."""
    src = _Source(path)
    root_name = "tileset.json"
    tileset = json.loads(src.read(root_name))
    levels: Dict[int, int] = {}
    prims: List[int] = []
    root_pos = None
    t = tileset.get("root", {}).get("transform")
    if t and len(t) == 16:
        root_pos = dict(zip(("lat", "lon", "h"), ecef_to_geodetic(t[12], t[13], t[14])))

    def content_uris(tile):
        out = []
        for c in ([tile.get("content")] if tile.get("content") else []) + tile.get("contents", []):
            u = c.get("uri") or c.get("url")
            if u:
                out.append(u)
        return out

    stack = [(tileset["root"], 0, "")]
    seen = 0
    while stack and seen < max_tiles:
        tile, depth, base = stack.pop()
        seen += 1
        levels[depth] = levels.get(depth, 0) + 1
        for uri in content_uris(tile):
            name = posixpath.normpath(posixpath.join(base, uri))
            if uri.lower().endswith(".json"):
                try:
                    sub = json.loads(src.read(name))
                    stack.append((sub["root"], depth + 1, posixpath.dirname(name)))
                except (KeyError, ValueError, OSError):
                    pass
                continue
            try:
                n = glb_primitives(src.read(name))
            except (KeyError, OSError, ValueError, struct.error):
                n = None
            if n is not None:
                prims.append(n)
        for ch in tile.get("children", []):
            stack.append((ch, depth + 1, base))
    return {
        "levels": dict(sorted(levels.items())),
        "tiles": sum(levels.values()),
        "primitives_mean": (sum(prims) / len(prims)) if prims else None,
        "primitives_max": max(prims) if prims else None,
        "bytes": src.size(),
        "root": root_pos,
        "version": tileset.get("asset", {}).get("version"),
        "geometric_error": tileset.get("geometricError"),
    }


def report(info: Dict[str, object]) -> str:
    lv = " · ".join("L%d %d" % (k, v) for k, v in info["levels"].items())
    pm = info["primitives_mean"]
    lines = ["%d tiles (%s)" % (info["tiles"], lv),
             "primitives per tile: %s (max %s)" % ("%.2f" % pm if pm is not None else "—",
                                                   info["primitives_max"]),
             "size: %.1f MB · 3D Tiles %s" % (info["bytes"] / 1e6, info["version"])]
    r = info.get("root")
    if r:
        lines.append("root: %.6f N %.6f E, h %.2f m (ellipsoidal, from the file)"
                     % (r["lat"], r["lon"], r["h"]))
    return "\n".join(lines)
