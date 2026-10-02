"""The blocks of STEP2, read from the files Metashape wrote — no Metashape here.

Three things are decided on the files, after ``buildModel(split_in_blocks=True,
export_blocks=True)`` has written them, and all three are pure functions that a
test runs without Metashape:

* **the check that stops identical blocks** (:func:`check_blocks`). Version
  ``0c2559a`` (23 Jul 2026) cut by setting the chunk region and calling
  ``exportModel(clip_to_boundary=True)``: the 32 blocks it wrote were the SAME
  whole model 32 times (one sha256 once the ``mtllib`` line is removed).
  ``clip_to_boundary`` clips to the *boundary shapes* of the chunk, not to the
  region — Metashape 2.3.2 says so in ``Chunk.exportModel.__doc__``: «Clip model
  to boundary shapes», the region being ``clip_to_region`` (default False).
  The check makes that failure loud: two blocks with the same content, or with
  the same bbox and face count, or faces adding up to more than 1.5 times the
  source, stop the step;
* **the grid names** (:func:`grid_names`): ``block_xNNN_yNNN`` from the CENTRE
  of each tile in a grid of side ``blocks_size`` whose origin is the minimum
  corner of the model's bbox, instead of Metashape's «Tile 93341-516978»;
* **the small tiles** (:func:`plan_small_tiles`): a tile under ``min_faces`` is
  merged into the largest neighbour whose bbox touches it, or only flagged.

The coordinates are those of the files: Metashape writes the tiles in a local
frame whose origin is ``<SRSOrigin>`` of the ``metadata.xml`` beside them
(measured 2 Oct 2026: tile vertices around -37, 20, -14 for an origin at
834913.43, 4623978.85, 613.35 in EPSG:7791). Bboxes, centres and the grid
origin all live in that one frame, so the names do not depend on it.
"""

from __future__ import annotations

import hashlib
import math
import os
import shutil
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

#: the ceiling on the faces of all blocks together, as a multiple of the source:
#: a Block Model re-meshes at the seams (1.055 × the LOD0 on San Pietro), 32
#: copies of the whole model are 32 ×
MAX_FACES_RATIO = 1.5

#: the proposed threshold for a tile too small to stand alone (STEP2 dialog)
DEFAULT_MIN_FACES = 2000

#: what to do with a tile under the threshold
SMALL_MERGE = "merge"
SMALL_FLAG = "flag"
SMALL_MODES = (SMALL_MERGE, SMALL_FLAG)

#: the extensions renamed together with a tile's .obj
TILE_EXTENSIONS = (".obj", ".mtl", ".tls")

#: where a merged-away tile's files go (never deleted: the operator decides)
ABSORBED_DIR = "_absorbed"

#: two bboxes that come closer than this (in the files' units, metres) touch
TOUCH_TOLERANCE = 1e-3

#: digits of a bbox coordinate that count when two bboxes are compared
_BBOX_DIGITS = 6


class BlocksRejected(Exception):
    """The blocks are not distinct spatial pieces; ``problems`` says why."""

    def __init__(self, problems: Sequence[str]):
        self.problems = list(problems)
        super().__init__("\n".join(self.problems))


class GridCollision(Exception):
    """Two tiles fall in the same grid cell: one name would overwrite the other."""

    def __init__(self, collisions: Dict[str, List[str]]):
        self.collisions = collisions
        lines = [f"{name}: {', '.join(sorted(tiles))}" for name, tiles in sorted(collisions.items())]
        super().__init__("two tiles in one grid cell:\n" + "\n".join(lines))


# ── reading a tile ──────────────────────────────────────────────────────────

def obj_stats(path: str) -> Dict[str, object]:
    """Faces, vertices, bbox and content digest of an OBJ, read in one pass.

    The digest is the sha256 of every line but ``mtllib``: renaming a tile
    rewrites that line and nothing else, and the 32 identical blocks of
    ``0c2559a`` differed only there. ``bbox`` is ``((minx, miny, minz),
    (maxx, maxy, maxz))`` of the ``v`` lines, None when there are none.
    """
    sha = hashlib.sha256()
    faces = vertices = 0
    lo = [math.inf, math.inf, math.inf]
    hi = [-math.inf, -math.inf, -math.inf]
    with open(path, "rb") as fh:
        for line in fh:
            if line.startswith(b"mtllib"):
                continue
            sha.update(line)
            if line.startswith(b"v "):
                vertices += 1
                parts = line.split(None, 4)
                for i in range(3):
                    c = float(parts[i + 1])
                    if c < lo[i]:
                        lo[i] = c
                    if c > hi[i]:
                        hi[i] = c
            elif line.startswith(b"f "):
                faces += 1
    bbox = (tuple(lo), tuple(hi)) if vertices else None
    return {"path": path, "name": os.path.splitext(os.path.basename(path))[0],
            "faces": faces, "vertices": vertices, "bbox": bbox,
            "digest": "sha256:" + sha.hexdigest()}


def folder_stats(folder: str, names: Optional[Iterable[str]] = None) -> List[Dict[str, object]]:
    """:func:`obj_stats` of every ``.obj`` in ``folder`` (or of ``names``), sorted."""
    if names is None:
        names = [n for n in os.listdir(folder) if n.lower().endswith(".obj")]
    return [obj_stats(os.path.join(folder, n)) for n in sorted(names)]


# ── 1. the check that stops identical blocks ────────────────────────────────

def _bbox_key(bbox) -> Optional[Tuple[float, ...]]:
    if bbox is None:
        return None
    return tuple(round(c, _BBOX_DIGITS) for corner in bbox for c in corner)


def _file(stat) -> str:
    return os.path.basename(str(stat.get("path") or stat.get("name")))


def check_blocks(stats: Sequence[Dict[str, object]], source_faces: Optional[int] = None,
                 *, max_ratio: float = MAX_FACES_RATIO) -> List[str]:
    """The reasons these blocks are not distinct pieces of one model — [] if none.

    * two or more blocks with the same digest (content without ``mtllib``);
    * two or more blocks with the same bbox AND the same number of faces;
    * the faces of all blocks above ``max_ratio`` × ``source_faces``.

    Every sentence names the files.
    """
    problems: List[str] = []
    by_digest: Dict[str, List[str]] = {}
    for s in stats:
        by_digest.setdefault(str(s["digest"]), []).append(_file(s))
    same_content = [sorted(v) for v in by_digest.values() if len(v) > 1]
    for files in sorted(same_content):
        problems.append(f"{len(files)} blocks have the same content: {', '.join(files)}")

    seen_twins = {f for files in same_content for f in files}
    by_shape: Dict[tuple, List[str]] = {}
    for s in stats:
        key = (_bbox_key(s.get("bbox")), s.get("faces"))
        by_shape.setdefault(key, []).append(_file(s))
    for (bbox, faces), files in sorted(by_shape.items(), key=lambda kv: sorted(kv[1])):
        if len(files) > 1 and not set(files) <= seen_twins:
            problems.append(f"{len(files)} blocks have the same bbox and {faces} faces: "
                            f"{', '.join(sorted(files))}")

    if source_faces:
        total = sum(int(s.get("faces") or 0) for s in stats)
        if total > max_ratio * source_faces:
            problems.append(f"the blocks add up to {total:,} faces, "
                            f"{total / source_faces:.2f} × the {source_faces:,} of the source "
                            f"(ceiling {max_ratio} ×): {len(stats)} blocks")
    return problems


def assert_blocks(stats, source_faces=None, *, max_ratio: float = MAX_FACES_RATIO) -> None:
    """:func:`check_blocks`, raising :class:`BlocksRejected` when it finds something."""
    problems = check_blocks(stats, source_faces, max_ratio=max_ratio)
    if problems:
        raise BlocksRejected(problems)


# ── 2. the grid names ───────────────────────────────────────────────────────

def grid_origin(stats: Sequence[Dict[str, object]]) -> Tuple[float, float]:
    """The minimum corner (x, y) of the model's bbox: the union of the tiles'."""
    boxes = [s["bbox"] for s in stats if s.get("bbox")]
    return (min(b[0][0] for b in boxes), min(b[0][1] for b in boxes))


def read_srs_origin(folder: str) -> Optional[Tuple[float, float, float]]:
    """``<SRSOrigin>`` of the ``metadata.xml`` Metashape writes beside the
    blocks: the CRS point the files' local frame starts from. None if absent."""
    import xml.etree.ElementTree as ET
    path = os.path.join(folder, "metadata.xml")
    if not os.path.isfile(path):
        return None
    try:
        node = ET.parse(path).getroot().find("SRSOrigin")
        x, y, z = (float(v) for v in (node.text or "").split(","))
        return (x, y, z)
    except (ET.ParseError, AttributeError, ValueError):
        return None


def cut_grid_origin(stats: Sequence[Dict[str, object]], size: float,
                    srs_origin: Optional[Sequence[float]]) -> Tuple[float, float]:
    """The minimum corner of the model's bbox, snapped down onto the grid of the CUT.

    Metashape's Block Model lays its grid from the CRS origin: tile «i-j»
    covers ``[i·size, (i+1)·size]`` in x (and j in y), with a 1 % overlap at
    the seams (measured on San Pietro, 108 tiles). A naming grid whose origin is
    the bare bbox corner is shifted by a fraction of a cell against it, and the
    centres of two marginal tiles fall in one cell — 12 such collisions on San
    Pietro. Snapped onto the cut, every centre lies in its own cell, and the name
    is the cut's index counted from 1. Without ``srs_origin`` (no metadata.xml)
    it is the bare corner, and :func:`grid_names` says when that collides.
    """
    mx, my = grid_origin(stats)
    if not srs_origin:
        return (mx, my)
    sx, sy = float(srs_origin[0]), float(srs_origin[1])
    return (math.floor((mx + sx) / size) * size - sx,
            math.floor((my + sy) / size) * size - sy)


def grid_cell(bbox, size: float, origin: Tuple[float, float]) -> Tuple[int, int]:
    """The 1-based (x, y) cell of the CENTRE of ``bbox``."""
    cx = (bbox[0][0] + bbox[1][0]) / 2.0
    cy = (bbox[0][1] + bbox[1][1]) / 2.0
    return (int(math.floor((cx - origin[0]) / size)) + 1,
            int(math.floor((cy - origin[1]) / size)) + 1)


def grid_name(cell: Tuple[int, int]) -> str:
    return f"block_x{cell[0]:03d}_y{cell[1]:03d}"


def grid_names(stats: Sequence[Dict[str, object]], size: float,
               origin: Optional[Tuple[float, float]] = None) -> Dict[str, str]:
    """``{metashape name: block_xNNN_yNNN}`` for every tile with vertices.

    Raises :class:`GridCollision` when two tiles land in one cell: renaming
    would overwrite one with the other, and that is never done silently.
    """
    if size <= 0:
        raise ValueError(f"blocks_size must be > 0, got {size}")
    origin = origin or grid_origin(stats)
    mapping: Dict[str, str] = {}
    cells: Dict[str, List[str]] = {}
    for s in stats:
        if not s.get("bbox"):
            continue
        new = grid_name(grid_cell(s["bbox"], size, origin))
        mapping[str(s["name"])] = new
        cells.setdefault(new, []).append(str(s["name"]))
    collisions = {k: v for k, v in cells.items() if len(v) > 1}
    if collisions:
        raise GridCollision(collisions)
    return mapping


def mtllib_line(mtl: str) -> bytes:
    """``mtllib <name>``: quoted only when the name has a space. Metashape
    always quotes; dtcstamp 0.1.3 reads the quotes as part of the name and does
    not find the ``.mtl`` (measured 2 Oct 2026), so a name without spaces is
    written bare — the quotes said nothing there."""
    name = mtl.encode("utf-8")
    return (b'mtllib "' + name + b'"\n') if any(c.isspace() for c in mtl) else b"mtllib " + name + b"\n"


def _rewrite_mtllib(obj_path: str, new_mtl: str) -> None:
    """Point the ``mtllib`` line of ``obj_path`` at ``new_mtl``, streaming."""
    tmp = obj_path + ".tmp-rename"
    with open(obj_path, "rb") as src, open(tmp, "wb") as dst:
        for line in src:
            if line.startswith(b"mtllib"):
                line = mtllib_line(new_mtl)
            dst.write(line)
    os.replace(tmp, obj_path)


def unquote_mtllib(obj_path: str) -> bool:
    """Rewrite ``mtllib "<name>"`` as ``mtllib <name>`` when the name has no
    space (see :func:`mtllib_line`). → whether the file changed. Reads only
    the head of the file: Metashape writes ``mtllib`` on its second line."""
    with open(obj_path, "rb") as fh:
        head = [fh.readline() for _ in range(8)]
    for line in head:
        if line.startswith(b"mtllib"):
            value = line[len(b"mtllib"):].strip()
            if len(value) > 1 and value[:1] == b'"' and value[-1:] == b'"':
                name = value[1:-1].decode("utf-8", "replace")
                if not any(c.isspace() for c in name):
                    _rewrite_mtllib(obj_path, name)
                    return True
            return False
    return False


def rename_tiles(folder: str, mapping: Dict[str, str]) -> List[Tuple[str, str]]:
    """Rename ``.obj``/``.mtl``/``.tls`` of every tile in ``mapping`` and point
    the ``mtllib`` line at the renamed ``.mtl``. → ``[(old, new)]`` done.

    Refuses before touching anything when a target file already exists.
    """
    for old, new in mapping.items():
        for ext in TILE_EXTENSIONS:
            target = os.path.join(folder, new + ext)
            if old != new and os.path.exists(target):
                raise FileExistsError(f"{target} exists: the tiles were not renamed")
    done = []
    for old, new in sorted(mapping.items()):
        if old == new:
            continue
        for ext in TILE_EXTENSIONS:
            src = os.path.join(folder, old + ext)
            if os.path.exists(src):
                os.replace(src, os.path.join(folder, new + ext))
        obj = os.path.join(folder, new + ".obj")
        if os.path.exists(obj) and os.path.exists(os.path.join(folder, new + ".mtl")):
            _rewrite_mtllib(obj, new + ".mtl")
        done.append((old, new))
    return done


# ── 3. the small tiles ──────────────────────────────────────────────────────

def bboxes_touch(a, b, tol: float = TOUCH_TOLERANCE) -> bool:
    """Whether two bboxes touch or overlap in plan (x, y): the cut is a grid in
    plan, so the neighbours of a tile are its neighbours in x and y."""
    return (a[0][0] <= b[1][0] + tol and b[0][0] <= a[1][0] + tol
            and a[0][1] <= b[1][1] + tol and b[0][1] <= a[1][1] + tol)


def _union(a, b):
    return (tuple(min(a[0][i], b[0][i]) for i in range(3)),
            tuple(max(a[1][i], b[1][i]) for i in range(3)))


def plan_small_tiles(stats: Sequence[Dict[str, object]], min_faces: int,
                     mode: str = SMALL_MERGE) -> Dict[str, object]:
    """What happens to the tiles under ``min_faces``, decided on the stats.

    The small tiles are taken from the smallest up. In ``merge`` mode each goes
    into the largest tile (faces counted after the merges already planned)
    whose bbox touches it; one with no neighbour stays, flagged. In ``flag``
    mode nothing moves. → ``{small, merges: [(small, into)], flagged,
    faces_after: {name: faces}}``.
    """
    if mode not in SMALL_MODES:
        raise ValueError(f"mode must be one of {SMALL_MODES}, got {mode!r}")
    live = {str(s["name"]): {"faces": int(s.get("faces") or 0), "bbox": s.get("bbox")}
            for s in stats}
    small = sorted((n for n, v in live.items() if v["faces"] < min_faces),
                   key=lambda n: (live[n]["faces"], n))
    merges: List[Tuple[str, str]] = []
    flagged: List[str] = []
    for name in small:
        me = live.get(name)
        if me is None:
            continue
        if me["faces"] >= min_faces:
            continue                    # grown past the threshold by a merge
        if mode == SMALL_FLAG or not me["bbox"]:
            flagged.append(name)
            continue
        neighbours = [(v["faces"], n) for n, v in live.items()
                      if n != name and v["bbox"] and bboxes_touch(me["bbox"], v["bbox"])]
        if not neighbours:
            flagged.append(name)
            continue
        _, into = max(neighbours)
        live[into]["faces"] += me["faces"]
        live[into]["bbox"] = _union(live[into]["bbox"], me["bbox"])
        del live[name]
        merges.append((name, into))
    # a merge into a tile that was itself merged later: follow it to the end
    final = {}
    for small_name, into in merges:
        while into not in live:
            into = dict(merges)[into]
        final[small_name] = into
    return {"small": small, "merges": [(s, final[s]) for s, _ in merges],
            "flagged": flagged, "faces_after": {n: v["faces"] for n, v in live.items()}}


def _parse_index(token: bytes, offset: int) -> bytes:
    if not token:
        return token
    value = int(token)
    if value < 0:
        raise ValueError("relative (negative) OBJ indices are not merged")
    return str(value + offset).encode()


def append_obj(into_path: str, small_path: str) -> int:
    """Append the geometry of ``small_path`` to ``into_path``: its ``v``/``vt``/
    ``vn`` lines and its faces, the face indices shifted past the vertices
    already there. → faces appended."""
    counts = {b"v": 0, b"vt": 0, b"vn": 0}
    with open(into_path, "rb") as fh:
        for line in fh:
            head = line.split(None, 1)[0] if line.strip() else b""
            if head in counts:
                counts[head] += 1
    added = 0
    with open(small_path, "rb") as src, open(into_path, "ab") as dst:
        dst.write(b"\n# appended by 3DSC: " + os.path.basename(small_path).encode("utf-8") + b"\n")
        for line in src:
            head = line.split(None, 1)[0] if line.strip() else b""
            if head in counts:
                dst.write(line)
            elif head == b"f":
                parts = []
                for corner in line.split()[1:]:
                    ids = corner.split(b"/")
                    ids[0] = _parse_index(ids[0], counts[b"v"])
                    if len(ids) > 1:
                        ids[1] = _parse_index(ids[1], counts[b"vt"])
                    if len(ids) > 2:
                        ids[2] = _parse_index(ids[2], counts[b"vn"])
                    parts.append(b"/".join(ids))
                dst.write(b"f " + b" ".join(parts) + b"\n")
                added += 1
    return added


def apply_small_tiles(folder: str, plan: Dict[str, object]) -> List[str]:
    """Carry out the merges of :func:`plan_small_tiles` on the files.

    The small tile's geometry is appended to its neighbour's ``.obj``; the
    small tile's files, and the neighbour's ``.tls`` (Metashape's own copy of a
    mesh that no longer is the one in the ``.obj``), go into ``_absorbed/`` —
    moved, never deleted. → a line per merge.
    """
    lines = []
    absorbed = os.path.join(folder, ABSORBED_DIR)
    for small, into in plan["merges"]:
        os.makedirs(absorbed, exist_ok=True)
        n = append_obj(os.path.join(folder, into + ".obj"), os.path.join(folder, small + ".obj"))
        for name in (small,):
            for ext in TILE_EXTENSIONS:
                src = os.path.join(folder, name + ext)
                if os.path.exists(src):
                    shutil.move(src, os.path.join(absorbed, name + ext))
        tls = os.path.join(folder, into + ".tls")
        if os.path.exists(tls):
            shutil.move(tls, os.path.join(absorbed, into + ".tls"))
        lines.append(f"{small} ({n} faces) → {into}")
    return lines
