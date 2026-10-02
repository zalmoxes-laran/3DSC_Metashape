"""A fake Metashape document built from the ``doc.xml`` files of a real project.

A ``.psx`` project keeps its state in ``<name>.files/``: ``project.zip``, one
``<chunk>/chunk.zip`` per chunk (sensors, cameras with ``transform`` and
``reference``, markers, CRS, ``meta``), and ``<chunk>/0/frame.zip`` (photo
paths, and where each asset's zip is — ``model.zip``, ``point_cloud.zip``,
``depth_maps.zip``, each with its own ``meta``). The classes here carry the
attributes ``dtc_stamp_ms`` reads from the real API, under the same names, so
that a stamp is measured without Metashape (the reading is the one of
``_lavoro-claude/script/ms.py``).
"""

from __future__ import annotations

import os
import re
import zipfile
import xml.etree.ElementTree as ET


def _doc(path):
    return ET.fromstring(zipfile.ZipFile(path).read("doc.xml"))


def _meta(node):
    m = node.find("meta") if node is not None else None
    return {p.get("name"): p.get("value") for p in m} if m is not None else {}


class Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class CRS(Obj):
    pass


class Model(Obj):
    """``label``, ``key``, ``meta``, ``faces`` (a range: ``len()`` works)."""


class PointCloud(Obj):
    pass


class Elevation(Obj):
    pass


class TiePoints(Obj):
    pass


def _crs(wkt):
    if not wkt:
        return None
    auth = re.findall(r'AUTHORITY\["(\w+)","(\d+)"\]', wkt)
    name = re.match(r'\w+\["([^"]+)"', wkt)
    return CRS(authority=f"{auth[-1][0]}::{auth[-1][1]}" if auth else None,
               name=name.group(1) if name else None, wkt=wkt)


def load_chunk(files_dir, label):
    """``(doc, chunk)`` for the chunk called ``label`` in ``<name>.files``."""
    project = _doc(os.path.join(files_dir, "project.zip"))
    psx = files_dir[:-len(".files")] + ".psx"
    doc = Obj(path=psx, modified=False, meta=_meta(project))
    for entry in project.find("chunks"):
        cid = entry.get("id")
        c = _doc(os.path.join(files_dir, cid, "chunk.zip"))
        if c.get("label") != label:
            continue
        frame_dir = os.path.join(files_dir, cid, "0")
        frame = _doc(os.path.join(frame_dir, "frame.zip"))
        sensors = {s.get("id"): Obj(label=s.get("label")) for s in c.find("sensors")}
        photos = {}
        for cam in frame.find("cameras"):
            p = cam.find("photo")
            if p is not None:
                photos[cam.get("camera_id")] = os.path.normpath(os.path.join(frame_dir, p.get("path")))
        cameras = []
        for cam in c.find("cameras").iter("camera"):
            ref = cam.find("reference")
            location = None
            enabled = False
            if ref is not None and ref.get("x") is not None:
                location = (float(ref.get("x")), float(ref.get("y")), float(ref.get("z")))
                enabled = ref.get("enabled") != "false"
            cameras.append(Obj(
                label=cam.get("label"), sensor=sensors.get(cam.get("sensor_id")),
                photo=Obj(path=photos[cam.get("id")]) if cam.get("id") in photos else None,
                transform=cam.find("transform").text if cam.find("transform") is not None else None,
                reference=Obj(enabled=enabled, location=location)))
        markers = []
        node = c.find("markers")
        for m in (node if node is not None else []):
            ref = m.find("reference")
            loc = None
            if ref is not None and ref.get("x") is not None:
                loc = (float(ref.get("x")), float(ref.get("y")), float(ref.get("z")))
            markers.append(Obj(label=m.get("label"), reference=Obj(
                enabled=ref is not None and ref.get("enabled") != "false", location=loc)))
        models = []
        for m in frame.findall("model"):
            z = os.path.join(frame_dir, m.get("path"))
            d = _doc(z)
            faces = int(d.find("mesh/faceCount").text)
            models.append(Model(key=int(m.get("id")), label="", meta=_meta(d), faces=range(faces)))
        tie = None
        pc = frame.find("point_cloud")
        if pc is not None:
            tie = TiePoints(meta=_meta(_doc(os.path.join(frame_dir, pc.get("path")))))
        ref = c.find("reference")
        chunk = Obj(label=label, key=int(cid), meta=_meta(c), crs=_crs(ref.text if ref is not None else None),
                    cameras=cameras, markers=markers, models=models,
                    model=models[-1] if models else None, tie_points=tie)
        return doc, chunk
    raise KeyError(label)
