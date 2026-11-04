"""The appender between projects, the Metashape side.

:func:`append_from_project` brings a set of cameras from a chunk of another
project into a chunk of the open one, as a camera group of its own, with what
was done on them in the source: calibration, marker projections, masks,
camera reference. The decisions are in :mod:`ms_appender` (pure, tested); here
they are applied with the Metashape 2.3 API. Nothing is aligned: the user runs
Align Photos (without resetting the current alignment) afterwards.
"""

from __future__ import annotations

import hashlib
import os

import Metashape as ps

import ms_appender as ma

DEFAULTS = {
    "selection": "selected",      # selected | group | enabled | all
    "group_key": None,
    "group_label": None,          # None: «<project> · <chunk>»
    "calibration": "copy",        # copy | reuse | exif
    "fix_calibration": False,
    "markers": "merge",           # merge | new | none
    "marker_prefix": "",
    "marker_reference": True,     # new markers: bring their reference coordinates
    "masks": True,
    "camera_reference": False,
    "keep_enabled": True,
    "dedupe_by_hash": False,
}


def open_source(path):
    doc = ps.Document()
    doc.open(path, read_only=True, ignore_lock=True)
    return doc


def describe_source(doc):
    """What the dialog shows: chunks, their camera groups, counts."""
    out = []
    for ch in doc.chunks:
        groups = [{"key": g.key, "label": g.label,
                   "cameras": sum(1 for c in ch.cameras if c.group is not None and c.group.key == g.key)}
                  for g in ch.camera_groups]
        out.append({"key": ch.key, "label": ch.label, "cameras": len(ch.cameras),
                    "selected": sum(1 for c in ch.cameras if c.selected),
                    "enabled": sum(1 for c in ch.cameras if c.enabled),
                    "groups": groups, "markers": len(ch.markers),
                    "masks": sum(1 for c in ch.cameras if c.mask is not None),
                    "crs": ch.crs.wkt if ch.crs else None})
    return out


def _md5(path, block=1 << 20):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(block), b""):
            h.update(b)
    return h.hexdigest()


def _crs_wkt(crs):
    return crs.wkt if crs is not None else None


def marker_crs(chunk):
    """The system the marker coordinates are in: Metashape leaves ``marker_crs``
    empty when it is the chunk's own."""
    return chunk.marker_crs or chunk.crs


def append_from_project(target_chunk, source_path, source_chunk_key, options=None, progress=None):
    o = dict(DEFAULTS, **(options or {}))
    say = progress or (lambda msg: print("[3DSC append] " + msg))
    src_doc = open_source(source_path)
    sch = next(c for c in src_doc.chunks if c.key == source_chunk_key)

    info = [{"label": c.label, "selected": c.selected, "enabled": c.enabled,
             "group": c.group.key if c.group is not None else None, "cam": c} for c in sch.cameras]
    chosen = ma.select_cameras(info, o["selection"], o["group_key"])
    chosen = [x for x in chosen if x["cam"].photo is not None]
    missing = [x["label"] for x in chosen if not os.path.exists(x["cam"].photo.path)]
    chosen = [x for x in chosen if os.path.exists(x["cam"].photo.path)]
    say(f"{len(chosen)} cameras chosen in «{sch.label}» ({len(missing)} with the photo missing)")

    by_path = {x["cam"].photo.path: x["cam"] for x in chosen}
    tgt_paths = [c.photo.path for c in target_chunk.cameras if c.photo is not None]
    src_h = tgt_h = None
    if o["dedupe_by_hash"]:
        say("hashing the photos")
        src_h = {p: _md5(p) for p in by_path}
        tgt_h = [_md5(p) for p in tgt_paths if os.path.exists(p)]
    plan = ma.plan_photos(list(by_path), tgt_paths, src_h, tgt_h)

    if not plan["add"]:
        raise ValueError(f"No photo to add: {len(chosen)} cameras chosen with the «{o['selection']}» mode, "
                         f"{len(plan['skip'])} already in the target, {len(missing)} with the photo missing.")
    label = o["group_label"] or ma.default_group_label(source_path, sch.label)
    group = target_chunk.addCameraGroup()
    group.label = label
    before = {c.key for c in target_chunk.cameras}
    target_chunk.addPhotos(plan["add"], group=group.key, load_reference=False)
    new = [c for c in target_chunk.cameras if c.key not in before]
    pairs = []          # (source camera, target camera)
    idx = {ma.norm_path(p): c for p, c in by_path.items()}
    for c in new:
        s = idx.get(ma.norm_path(c.photo.path))
        if s is None:
            continue
        c.label = s.label
        c.group = group
        pairs.append((s, c))
    say(f"{len(pairs)} photos added to the group «{label}», {len(plan['skip'])} already there")

    # calibration
    auto_sensors = {c.sensor.key for _, c in pairs if c.sensor is not None}
    if o["calibration"] in ("copy", "reuse"):
        made = {}
        tgt_by_label = {s.label: s for s in target_chunk.sensors if s.key not in auto_sensors}
        for s, c in pairs:
            ss = s.sensor
            if ss is None:
                continue
            if ss.key not in made:
                ns = tgt_by_label.get(ss.label) if o["calibration"] == "reuse" else None
                if ns is None:
                    ns = target_chunk.addSensor(ss)
                    ns.label = ss.label
                    if ss.calibration is not None:
                        ns.user_calib = ss.calibration
                    ns.fixed_calibration = bool(o["fix_calibration"])
                made[ss.key] = ns
            c.sensor = made[ss.key]
        for sk in auto_sensors:
            sen = next((x for x in target_chunk.sensors if x.key == sk), None)
            if sen is not None and not any(c.sensor is not None and c.sensor.key == sk for c in target_chunk.cameras):
                target_chunk.remove(sen)

    n_masks = n_ref = 0
    for s, c in pairs:
        if o["keep_enabled"]:
            c.enabled = s.enabled
        if o["masks"] and s.mask is not None:
            m = ps.Mask()
            m.setImage(s.mask.image())
            c.mask = m
            n_masks += 1
        if o["camera_reference"] and s.reference.location is not None:
            for a in ("location", "rotation", "location_accuracy", "rotation_accuracy", "enabled"):
                v = getattr(s.reference, a, None)
                if v is not None:
                    setattr(c.reference, a, v)
            n_ref += 1

    # markers
    n_proj = 0
    marker_plan = []
    if o["markers"] != "none":
        tcam = {s.key: c for s, c in pairs}
        imported = {s.label for s, _ in pairs}
        src_markers = []
        for m in sch.markers:
            on = [s.label for s, _ in pairs if m.projections[s] is not None]
            if on:
                src_markers.append({"label": m.label, "cameras": on, "m": m})
        marker_plan = ma.plan_markers(src_markers, imported, [m.label for m in target_chunk.markers],
                                      mode=o["markers"], prefix=o["marker_prefix"])
        action = ma.reference_action(_crs_wkt(marker_crs(sch)), _crs_wkt(marker_crs(target_chunk)))
        smap = {x["label"]: x["m"] for x in src_markers}
        tmap = {m.label: m for m in target_chunk.markers}
        for item in marker_plan:
            sm = smap[item["source_label"]]
            if item["new"]:
                tm = target_chunk.addMarker()
                tm.label = item["target_label"]
                if o["marker_reference"] and sm.reference.location is not None:
                    loc = sm.reference.location
                    if action == "transform":
                        loc = ps.CoordinateSystem.transform(loc, marker_crs(sch), marker_crs(target_chunk))
                    tm.reference.location = loc
                    tm.reference.enabled = (action != "copy_disabled") and sm.reference.enabled
                    if sm.reference.accuracy is not None:
                        tm.reference.accuracy = sm.reference.accuracy
                item["reference"] = action if o["marker_reference"] else "none"
            else:
                tm = tmap[item["target_label"]]
            for s, c in pairs:
                p = sm.projections[s]
                if p is None:
                    continue
                tm.projections[c] = ps.Marker.Projection(ps.Vector([p.coord.x, p.coord.y]), p.pinned)
                n_proj += 1

    counts = {"cameras": len(pairs), "skipped": len(plan["skip"]), "missing_photo": len(missing),
              "masks": n_masks, "camera_reference": n_ref,
              "markers_new": sum(1 for x in marker_plan if x["new"]),
              "markers_merged": sum(1 for x in marker_plan if not x["new"]),
              "projections": n_proj}
    opts = {k: v for k, v in o.items() if k != "group_key"}
    for k, v in ma.summary_meta(source_path, sch.label, label, counts, opts).items():
        target_chunk.meta[k] = v
    say("done: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    return {"group_label": label, "counts": counts, "missing": missing, "skipped": plan["skip"],
            "markers": [{k: v for k, v in x.items() if k != "cameras"} for x in marker_plan]}
