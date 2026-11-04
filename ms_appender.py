"""The appender between projects, without Metashape: what to bring and where.

E.D. (4 Nov 2026): from inside a project (the 2015 survey of the Templum Mare)
bring a set of photos that lives in a chunk of ANOTHER project (the 2013
excavation, with the court photos selected there) into the open chunk, as a
camera group of its own, together with what was already done on them: the
marker projections, the masks, the calibration. The alignment of the new
photos onto the existing solution is then run by the user.

The decisions are pure functions over plain data, so that a test runs them
without Metashape:

* :func:`select_cameras` — which source cameras: the selected ones, one camera
  group, the enabled ones, or all;
* :func:`plan_photos` — which photos are already in the target (same file,
  compared on the normalised path, or on the content hash when given) and are
  skipped;
* :func:`plan_markers` — for each source marker with projections on the
  imported cameras: merged into the target marker of the same label, or created
  new (with a prefix, so that «101» of 2013 is not «101» of 2015);
* :func:`reference_action` — what happens to the reference coordinates of a new
  marker when the two projects have different coordinate systems;
* :func:`summary_meta` — the record written into ``chunk.meta`` of the target,
  so that the project itself says where the photos came from.
"""

from __future__ import annotations

import datetime
import json
import os
from typing import Dict, Iterable, List, Optional, Sequence

SELECTION_MODES = ("selected", "group", "enabled", "all")
MARKER_MODES = ("merge", "new")


def norm_path(p: str) -> str:
    """A path as compared between projects: absolute, normalised, case-folded
    on the file name only (macOS volumes are usually case-insensitive)."""
    p = os.path.normpath(os.path.abspath(os.path.expanduser(p)))
    d, f = os.path.split(p)
    return os.path.join(d, f.lower())


def select_cameras(cameras: Sequence[dict], mode: str, group_key: Optional[int] = None) -> List[dict]:
    """``cameras``: dicts with ``label``, ``selected``, ``enabled``, ``group``
    (key or None). Returns the ones to import, in their order."""
    if mode not in SELECTION_MODES:
        raise ValueError(f"unknown selection mode: {mode}")
    if mode == "selected":
        return [c for c in cameras if c.get("selected")]
    if mode == "group":
        return [c for c in cameras if c.get("group") == group_key]
    if mode == "enabled":
        return [c for c in cameras if c.get("enabled", True)]
    return list(cameras)


def plan_photos(source_paths: Sequence[str], target_paths: Iterable[str],
                source_hashes: Optional[Dict[str, str]] = None,
                target_hashes: Optional[Iterable[str]] = None) -> Dict[str, list]:
    """Split the source photos into ``add`` and ``skip`` (already in the target,
    or repeated in the source). With hashes, the same file under another path
    is also recognised."""
    seen_paths = {norm_path(p) for p in target_paths}
    seen_hashes = set(target_hashes or ())
    add, skip = [], []
    for p in source_paths:
        n = norm_path(p)
        h = (source_hashes or {}).get(p)
        if n in seen_paths or (h is not None and h in seen_hashes):
            skip.append(p)
            continue
        seen_paths.add(n)
        if h is not None:
            seen_hashes.add(h)
        add.append(p)
    return {"add": add, "skip": skip}


def default_group_label(source_project: str, source_chunk: str) -> str:
    name = os.path.splitext(os.path.basename(source_project))[0]
    return f"{name} · {source_chunk}"


def plan_markers(source_markers: Sequence[dict], imported_labels: Iterable[str],
                 target_labels: Iterable[str], mode: str = "merge",
                 prefix: str = "") -> List[dict]:
    """``source_markers``: dicts with ``label`` and ``cameras`` (the labels of
    the source cameras the marker is projected on). Only markers seen on at
    least one imported camera are planned. Each plan item says the
    ``target_label``, whether the marker is ``new`` in the target, and on which
    imported cameras its projections go."""
    if mode not in MARKER_MODES:
        raise ValueError(f"unknown marker mode: {mode}")
    imported = set(imported_labels)
    existing = set(target_labels)
    taken = set(existing)
    plan = []
    for m in source_markers:
        on = [c for c in m.get("cameras", ()) if c in imported]
        if not on:
            continue
        if mode == "merge" and m["label"] in existing:
            plan.append({"source_label": m["label"], "target_label": m["label"], "new": False, "cameras": on})
            continue
        label = f"{prefix}{m['label']}" if mode == "new" or m["label"] in existing else m["label"]
        base, i = label, 2
        while label in taken:
            label = f"{base}_{i}"
            i += 1
        taken.add(label)
        plan.append({"source_label": m["label"], "target_label": label, "new": True, "cameras": on})
    return plan


def is_local(crs_wkt: Optional[str]) -> bool:
    return not crs_wkt or crs_wkt.strip().upper().startswith("LOCAL_CS")


def reference_action(source_crs: Optional[str], target_crs: Optional[str]) -> str:
    """What to do with the reference coordinates of a NEW marker:
    ``copy`` (same system), ``transform`` (two geographic/projected systems),
    ``copy_disabled`` (one of the two is local: the numbers come along but do
    not constrain the target, because they mean nothing there)."""
    if is_local(source_crs) or is_local(target_crs):
        return "copy_disabled"
    if (source_crs or "").strip() == (target_crs or "").strip():
        return "copy"
    return "transform"


def summary_meta(source_project: str, source_chunk: str, group_label: str,
                 counts: dict, options: dict, when: Optional[datetime.datetime] = None) -> Dict[str, str]:
    """The key and value written into ``chunk.meta`` of the target."""
    when = when or datetime.datetime.now().astimezone()
    key = "3dsc_append_" + when.strftime("%Y%m%dT%H%M%S")
    value = json.dumps({"source_project": source_project, "source_chunk": source_chunk,
                        "camera_group": group_label, "counts": counts, "options": options,
                        "time": when.isoformat(timespec="seconds")}, ensure_ascii=False)
    return {key: value}
