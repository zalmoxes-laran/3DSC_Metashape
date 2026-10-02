"""The stamp of every export of 3DSC for Metashape, read from what Metashape records.

One function, :func:`stamp_export`, writes a ``<file>.stamp.json`` beside each
file an export of 3DSC writes — mesh, blocks, tiles, images; point cloud,
orthomosaic and DEM read the same way — with dtcstamp 0.1.3 (``vendor/``, or
an installed copy). It follows the shape of EM Tools' ``birth_stamp.py`` and of
3DSC for Blender's ``stamp_bridge.py``, it does not invent a third:

* the asset inside the project is the **master** (``tier: master``,
  ``packaging: datablock``), the exported file the **distribution**. The
  master's address, ``psx://<project .psx>#<chunk label>/<asset type>/<key>``
  (the twin of ``blend://``), is a PATH: it never goes in the stamp, only in
  the private ``<asset>.hints.json`` beside it, under ``from``, one key per
  master. dtcstamp 0.1.3 does not know the kind ``psx`` (``KNOWN_KINDS`` = s3,
  http, local, blend): it is written ``kind: local``, ``scope: private``;
  ``from[].state.saved`` says whether the project had unsaved changes;
* **the step is what Metashape recorded**, not what 3DSC believes: the
  ``chunk.meta`` keys of the operations (``AlignCameras/*``,
  ``OptimizeCameras/*``…), the tie points' (``MatchPhotos/*``), the asset's
  own (``BuildDepthMaps/*``, ``BuildModel/*``…, and its ``Info/Original*``
  date and software version) go in ``how.parameters`` under Metashape's own
  names, typed. ``how.parameters["3DSC/read_from_meta"]`` lists the keys that
  were read; the other keys are what 3DSC passed to the call;
* ``how.dtc_kind`` is the operation's: ``photogrammetry`` for an asset that
  Metashape built from the photos (mesh, point cloud, orthomosaic, tiled
  model), ``tiling`` for the blocks, ``export`` for an export that does not
  change the geometry, ``georeferencing`` when that export writes CRS
  coordinates of a chunk with an active reference. A kind nobody knows (a DEM)
  stays ABSENT, never a default;
* the photos enter ``from`` one sensor at a time: by their own stamps when
  every photo of the sensor has one whose digest still matches its bytes (the
  San Pietro drone does), otherwise as the TREE of their folder (content
  digest, ``entry_point`` None);
* one act, one ``how.process_id``: every file of one export carries the same;
* ``by.operator`` is the ORCID iD the exporter declared in the dialog —
  checked with the ISO 7064 MOD 11-2 digit, as EM Tools' ``local_identity``,
  and signed ``auth: {mode: declared}`` — or nothing at all: then the agent is
  the software named in ``how`` (the format's rule). No value is invented.

No ``Metashape`` import here: the stamps are measured outside Metashape, on a
fake chunk built from the ``doc.xml`` files of a real project.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(HERE, "vendor")

SOFTWARE_NAME = "3DSC for Metashape"
METASHAPE_NAME = "Agisoft Metashape"
PSX_SCHEME = "psx://"

#: the kinds of step (s3Dgraphy ``dtc_kinds.process``)
KIND_PHOTOGRAMMETRY = "photogrammetry"
KIND_TILING = "tiling"
KIND_EXPORT = "export"
KIND_GEOREFERENCING = "georeferencing"

#: «work it out from what Metashape recorded» — distinct from None, which
#: means «nobody knows: leave it absent»
AUTO = "auto"

#: Metashape asset class → (word in the locator, operations that build it,
#: the kind when it was built, the technique word)
ASSETS = {
    "Model": ("model", ("BuildModel", "BuildTexture", "BuildUV"), KIND_PHOTOGRAMMETRY,
              "Metashape Build Model"),
    "PointCloud": ("point_cloud", ("BuildPointCloud",), KIND_PHOTOGRAMMETRY,
                   "Metashape Build Point Cloud"),
    "Orthomosaic": ("orthomosaic", ("BuildOrthomosaic",), KIND_PHOTOGRAMMETRY,
                    "Metashape Build Orthomosaic"),
    "TiledModel": ("tiled_model", ("BuildTiledModel",), KIND_PHOTOGRAMMETRY,
                   "Metashape Build Tiled Model"),
    # a DEM is interpolated from a point cloud or depth maps: which kind that
    # is the vocabulary does not say, so the kind stays absent
    "Elevation": ("elevation", ("BuildDem",), None, "Metashape Build DEM"),
}

#: the asset's Info keys that say when and with what it was made
ASSET_INFO_KEYS = ("Info/OriginalDateTime", "Info/OriginalSoftwareVersion")

#: what a stamp writes the media type and format of
_MEDIA = {".obj": ("model/obj", "obj"), ".ply": ("application/octet-stream", "ply"),
          ".dae": ("model/vnd.collada+xml", "dae"), ".glb": ("model/gltf-binary", "glb"),
          ".gltf": ("model/gltf+json", "gltf"), ".xml": ("application/xml", None),
          ".tif": ("image/tiff", None), ".tiff": ("image/tiff", None),
          ".jpg": ("image/jpeg", None), ".jpeg": ("image/jpeg", None),
          ".png": ("image/png", None), ".las": ("application/vnd.las", "las"),
          ".laz": ("application/vnd.laszip", "laz"), ".zip": ("application/zip", "zip")}

PREVIOUS_INFIX = ".prev-"

_DTC = None


# ── dtcstamp: installed, or the vendored copy ───────────────────────────────

def dtcstamp():
    """The dtcstamp module: an installed one with the 0.1.3 API
    (``note_parent_seen``), else ``vendor/dtcstamp.py``."""
    global _DTC
    if _DTC is not None:
        return _DTC
    try:
        import dtcstamp as installed  # type: ignore
        if hasattr(installed, "note_parent_seen") and hasattr(installed, "new_file_set_stamp"):
            _DTC = installed
            return _DTC
    except ImportError:
        pass
    spec = importlib.util.spec_from_file_location("dsc_vendor_dtcstamp",
                                                  os.path.join(VENDOR, "dtcstamp.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module          # dataclasses look their module up
    spec.loader.exec_module(module)
    _DTC = module
    return _DTC


# ── the operator: an ORCID iD declared, or nobody ───────────────────────────
# The model of EM Tools' local_identity.py (dev28), itself EMStudio's identity.ts.

_SHAPE = re.compile(r"^(\d{4})-(\d{4})-(\d{4})-(\d{3}[\dX])$")
EMPTY, SHAPE, CHECKSUM = "empty", "shape", "checksum"
DECLARED = "declared"
PROBLEM_TEXT = {
    EMPTY: "",
    SHAPE: "not an ORCID iD: 16 digits, the last may be X (0000-0002-1825-0097)",
    CHECKSUM: "the check digit does not match: a digit is wrong or two are swapped, "
              "and this iD would name somebody else",
}


def normalize_orcid(value: Optional[str]) -> str:
    """Whatever was pasted, down to ``dddd-dddd-dddd-dddX``."""
    raw = re.sub(r"^https?://(www\.)?orcid\.org/", "", str(value or "").strip(), flags=re.I)
    raw = re.sub(r"[\s‐-―]", "-", raw)
    raw = re.sub(r"[^0-9Xx-]", "", raw).upper()
    digits = raw.replace("-", "")
    if len(digits) != 16:
        return raw
    return f"{digits[0:4]}-{digits[4:8]}-{digits[8:12]}-{digits[12:16]}"


def is_valid_orcid(value: Optional[str]) -> bool:
    """Shape AND check digit (ISO/IEC 7064 MOD 11-2)."""
    orcid = normalize_orcid(value)
    if not _SHAPE.match(orcid):
        return False
    digits = orcid.replace("-", "")
    total = 0
    for ch in digits[:15]:
        total = (total + int(ch)) * 2
    result = (12 - total % 11) % 11
    return digits[15] == ("X" if result == 10 else str(result))


def orcid_problem(value: Optional[str]) -> Optional[str]:
    """``empty`` · ``shape`` · ``checksum`` · None (a good iD)."""
    orcid = normalize_orcid(value)
    if not orcid:
        return EMPTY
    if not _SHAPE.match(orcid):
        return SHAPE
    return None if is_valid_orcid(orcid) else CHECKSUM


def declared_operator(orcid: Optional[str], name: Optional[str] = None
                      ) -> Optional[Dict[str, Any]]:
    """``by.operator`` of a declared iD, or None (empty, or not a valid iD)."""
    if orcid_problem(orcid) is not None:
        return None
    operator: Dict[str, Any] = {"id": f"https://orcid.org/{normalize_orcid(orcid)}"}
    label = str(name or "").strip()
    if label:
        operator["label"] = label
    operator["auth"] = {"mode": DECLARED}
    return operator


#: where the declared identity is remembered between two exports
SETTINGS_ORCID = "3dsc_metashape/orcid"
SETTINGS_NAME = "3dsc_metashape/name"
PREFS_FILE = os.path.join(os.path.expanduser("~"), ".3dsc_metashape.json")


def load_identity(app=None) -> Tuple[str, str]:
    """``(orcid, name)`` remembered: Metashape's settings, else the prefs file."""
    if app is not None:
        try:
            orcid = app.settings.value(SETTINGS_ORCID)
            name = app.settings.value(SETTINGS_NAME)
            if orcid is not None or name is not None:
                return str(orcid or ""), str(name or "")
        except Exception:                           # noqa: BLE001 — no settings: the file
            pass
    try:
        with open(PREFS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return str(data.get("orcid") or ""), str(data.get("name") or "")
    except (OSError, ValueError):
        return "", ""


def save_identity(orcid: str, name: str, app=None) -> str:
    """Remember ``(orcid, name)``; → where (``settings`` or the file)."""
    if app is not None:
        try:
            app.settings.setValue(SETTINGS_ORCID, str(orcid or ""))
            app.settings.setValue(SETTINGS_NAME, str(name or ""))
            app.settings.save()
            return "settings"
        except Exception:                           # noqa: BLE001
            pass
    with open(PREFS_FILE, "w", encoding="utf-8") as fh:
        json.dump({"orcid": orcid or "", "name": name or ""}, fh)
    return PREFS_FILE


def ask_operator(app) -> Optional[Dict[str, Any]]:
    """The dialog «ORCID (optional)» of an export: the remembered iD offered,
    a wrong one refused with the reason, an empty one anonymous."""
    orcid, name = load_identity(app)
    while True:
        typed = app.getString(
            "ORCID iD of who is exporting (optional).\n"
            "Empty = anonymous: the stamp then names the software only.", orcid)
        typed = str(typed or "").strip()
        problem = orcid_problem(typed)
        if problem in (None, EMPTY):
            break
        app.messageBox("ORCID iD refused: " + PROBLEM_TEXT[problem])
        orcid = typed
    if problem == EMPTY:
        save_identity("", name, app)
        return None
    typed = normalize_orcid(typed)
    name = str(app.getString("Your name (optional, a courtesy beside the iD):", name) or "").strip()
    save_identity(typed, name, app)
    return declared_operator(typed, name)


# ── what Metashape recorded ─────────────────────────────────────────────────

def meta_dict(holder) -> Dict[str, str]:
    """The ``meta`` of a chunk or an asset as a plain dict ({} if none)."""
    meta = getattr(holder, "meta", None) if holder is not None else None
    if meta is None:
        return {}
    if isinstance(meta, dict):
        return dict(meta)
    try:
        return {k: meta[k] for k in meta.keys()}
    except Exception:                               # noqa: BLE001
        return {}


def typed(value: Any) -> Any:
    """Metashape writes every meta value as a string: back to bool/int/float."""
    if not isinstance(value, str):
        return value
    if value in ("true", "false"):
        return value == "true"
    for cast in (int, float):
        try:
            return cast(value)
        except ValueError:
            continue
    return value


def asset_type(asset) -> Optional[str]:
    """``Model``, ``PointCloud``… of a Metashape asset (or of a fake one)."""
    if asset is None:
        return None
    name = getattr(asset, "asset_type", None) or type(asset).__name__
    return name if name in ASSETS else None


def was_built(asset) -> bool:
    """Whether Metashape recorded the operation that built this asset in its meta
    (an imported mesh has only ``Info/*``)."""
    kind = asset_type(asset)
    if kind is None:
        return False
    ops = ASSETS[kind][1]
    return any(k.split("/", 1)[0] in ops for k in meta_dict(asset))


def _operation(key: str) -> bool:
    return "/" in key and not key.startswith(("Info/", "3dsc_"))


def operation_parameters(chunk, asset) -> Tuple[Dict[str, Any], List[str]]:
    """The parameters of the chain that BUILT ``asset``, from Metashape's meta:
    the tie points' (``MatchPhotos/*``), the chunk's (``AlignCameras/*``,
    ``OptimizeCameras/*``) and the asset's own (``BuildDepthMaps/*``,
    ``BuildModel/*``…), the asset winning on a shared key; plus the asset's
    ``Info/Original*``. → ``(parameters, keys read)``."""
    out: Dict[str, Any] = {}
    tie = getattr(chunk, "tie_points", None)
    for source in (meta_dict(tie), meta_dict(chunk), meta_dict(asset)):
        for k, v in source.items():
            if _operation(k):
                out[k] = typed(v)
    out.update(asset_info(asset))
    return out, sorted(out)


def asset_info(asset) -> Dict[str, Any]:
    """The asset's creation date and software version, as Metashape wrote them."""
    meta = meta_dict(asset)
    return {k: meta[k] for k in ASSET_INFO_KEYS if k in meta}


def crs_text(crs) -> Optional[str]:
    """``EPSG::7791`` (the authority), else the CRS name, else None."""
    if crs is None:
        return None
    for attr in ("authority", "name"):
        value = getattr(crs, attr, None)
        if value:
            return str(value)
    return None


def vector_list(v) -> Optional[List[float]]:
    """``[x, y, z]`` of a Metashape.Vector, a tuple or a list; None if not one."""
    if v is None:
        return None
    try:
        return [float(v[0]), float(v[1]), float(v[2])]
    except (TypeError, IndexError, ValueError):
        try:
            return [float(v.x), float(v.y), float(v.z)]
        except AttributeError:
            return None


def has_active_reference(chunk) -> bool:
    """A chunk with a CRS and at least one camera or marker reference enabled."""
    if crs_text(getattr(chunk, "crs", None)) is None:
        return False
    for item in list(getattr(chunk, "cameras", []) or []) + list(getattr(chunk, "markers", []) or []):
        ref = getattr(item, "reference", None)
        if ref is not None and getattr(ref, "enabled", False) and getattr(ref, "location", None) is not None:
            return True
    return False


def reference_parameters(chunk, *, cameras: bool = True) -> Dict[str, Any]:
    """The chunk's CRS; with ``cameras``, the cameras (total, aligned, with an
    enabled reference) and the ACTIVE markers with coordinates and CRS."""
    out: Dict[str, Any] = {}
    crs = crs_text(getattr(chunk, "crs", None))
    if crs:
        out["chunk/crs"] = crs
    if not cameras:
        return out
    cams = list(getattr(chunk, "cameras", []) or [])
    out["cameras/total"] = len(cams)
    out["cameras/aligned"] = sum(1 for c in cams if getattr(c, "transform", None) is not None)
    out["cameras/reference_enabled"] = sum(
        1 for c in cams if getattr(getattr(c, "reference", None), "enabled", False)
        and getattr(c.reference, "location", None) is not None)
    marker_crs = crs_text(getattr(chunk, "marker_crs", None)) or crs
    active = []
    for m in getattr(chunk, "markers", []) or []:
        ref = getattr(m, "reference", None)
        if ref is None or not getattr(ref, "enabled", False):
            continue
        loc = vector_list(getattr(ref, "location", None))
        if loc is None:
            continue
        active.append({"label": str(getattr(m, "label", "")), "x": loc[0], "y": loc[1],
                       "z": loc[2], "crs": marker_crs})
    out["markers/active"] = active
    return out


# ── the inputs: photos by sensor, the masters ───────────────────────────────

def _cache_key(path: str) -> Tuple[str, int, float]:
    st = os.stat(path)
    return (os.path.abspath(path), st.st_size, st.st_mtime)


def _file_digest(path: str, cache: Dict) -> str:
    key = ("file",) + _cache_key(path)
    if key not in cache:
        cache[key] = dtcstamp().file_digest(path)
    return cache[key]


def _tree_digest(folder: str, cache: Dict) -> Tuple[str, int]:
    key = ("tree", os.path.abspath(folder))
    if key not in cache:
        members = dtcstamp().tree_members(folder, entry_point=None)
        members = [m for m in members if not m["path"].endswith(
            (dtcstamp().STAMP_SUFFIX, dtcstamp().HINTS_SUFFIX))]
        cache[key] = (dtcstamp().members_digest(members), len(members))
    return cache[key]


def default_resource_id(digest: str) -> str:
    """The id of something nobody named, from its bytes (EM Tools' rule)."""
    return f"res:{str(digest).split(':', 1)[-1][:16]}"


def photo_inputs(chunk, cache: Optional[Dict] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """The ``from`` entries of the photos, one sensor at a time, and a summary
    per sensor for ``how.parameters``.

    A sensor whose every photo has a ``<photo>.stamp.json`` with the digest of
    its bytes is cited by those stamps (``resource_id`` + ``digest``); any
    other is cited as the tree of each folder its photos are in. The tree is
    the folder's content (stamps and hints left out), so a photo of that folder
    the chunk does not use is in it too: the summary counts both.
    """
    dtc = dtcstamp()
    cache = {} if cache is None else cache
    by_sensor: Dict[str, List[Any]] = {}
    for cam in getattr(chunk, "cameras", []) or []:
        photo = getattr(cam, "photo", None)
        path = getattr(photo, "path", None) if photo is not None else None
        if not path:
            continue
        sensor = str(getattr(getattr(cam, "sensor", None), "label", "") or "sensor")
        by_sensor.setdefault(sensor, []).append(cam)
    entries: List[Dict[str, Any]] = []
    summary: List[Dict[str, Any]] = []
    for sensor, cams in by_sensor.items():
        paths = [c.photo.path for c in cams]
        row = {"sensor": sensor, "cameras": len(cams),
               "aligned": sum(1 for c in cams if getattr(c, "transform", None) is not None)}
        cited: List[Dict[str, Any]] = []
        mismatch = 0
        for path in paths:
            sp = path + dtc.STAMP_SUFFIX
            if not (os.path.isfile(sp) and os.path.isfile(path)):
                cited = []
                break
            try:
                own = dtc.validate_stamp(dtc.read_stamp(sp))["self"]
            except (OSError, ValueError):
                cited = []
                break
            if own.get("digest") != _file_digest(path, cache):
                mismatch += 1
                cited = []
                break
            entry = {"resource_id": own["resource_id"], "digest": own["digest"]}
            size = (own.get("measures") or {}).get("size_bytes")
            if size:
                entry["size_bytes"] = size
            entry["label"] = f"{own.get('label') or os.path.basename(path)} · {sensor}"
            cited.append(entry)
        if cited:
            row["cited_as"] = "stamps"
            entries.extend(cited)
        else:
            row["cited_as"] = "tree"
            if mismatch:
                row["note"] = "a photo's stamp no longer matches its bytes"
            folders = sorted({os.path.dirname(os.path.abspath(p)) for p in paths})
            row["folders"] = []
            for folder in folders:
                digest, files = _tree_digest(folder, cache)
                used = sum(1 for p in paths if os.path.dirname(os.path.abspath(p)) == folder)
                entries.append({"resource_id": default_resource_id(digest), "digest": digest,
                                "packaging": "directory",
                                "label": f"{sensor} · {os.path.basename(folder)}, {used} photos"})
                row["folders"].append({"folder": os.path.basename(folder),
                                       "files": files, "used": used})
        summary.append(row)
    return entries, summary


def psx_locator(psx_path: str, chunk_label: str, asset_word: str, key: Any) -> str:
    """``psx://<path>#<chunk label>/<asset type>/<key>``, percent-encoded like
    ``dtcstamp.blend_locator``. The asset type is there because the keys are
    counted per type (model 1 and point cloud 1 are two assets)."""
    path = os.path.abspath(psx_path) if psx_path else "unsaved"
    return (PSX_SCHEME + quote(str(path), safe="/") + "#" + quote(str(chunk_label or ""), safe="")
            + "/" + asset_word + "/" + quote(str(key), safe=""))


def master_of(doc, chunk, asset) -> Optional[Tuple[Dict[str, Any], str]]:
    """``(from entry, psx locator)`` of an asset of the project — the entry by
    identity (its id derived from the locator), the locator for the hints."""
    kind = asset_type(asset)
    if kind is None:
        return None
    word = ASSETS[kind][0]
    key = getattr(asset, "key", None)
    locator = psx_locator(getattr(doc, "path", "") or "", getattr(chunk, "label", ""), word, key)
    entry: Dict[str, Any] = {"resource_id": "psx:" + str(uuid.uuid5(uuid.NAMESPACE_URL, locator))}
    label = str(getattr(asset, "label", "") or "").strip()
    entry["label"] = f"{getattr(chunk, 'label', '')} · {label or word + ' ' + str(key)}"
    entry["tier"] = "master"
    entry["packaging"] = "datablock"
    modified = getattr(doc, "modified", None)
    if isinstance(modified, bool):
        note = None
        if modified:
            note = ("the project had unsaved changes: the .psx on disk is not the "
                    "state this was exported from")
        dtcstamp().with_parent_state(entry, saved=not modified, note=note)
    return entry, locator


# ── the stamp of one file ───────────────────────────────────────────────────

def _base_stamp(path: str, cache: Dict) -> Dict[str, Any]:
    """dtcstamp's stamp for what ``path`` is, ``self`` only (EM Tools' rule):
    a folder → a tree; an ``.obj``/``.gltf`` that calls other files → a
    file_set; anything else → one file."""
    dtc = dtcstamp()
    lower = path.lower()
    if os.path.isdir(path):
        entry = "tileset.json" if os.path.isfile(os.path.join(path, "tileset.json")) else None
        stamp = dtc.new_tree_stamp(path, "res:pending", computed_by="producer", entry_point=entry)
    else:
        followed = dtc.follow_references(path) if lower.endswith((".obj", ".gltf")) else None
        if followed and len(followed["members"]) > 1:
            stamp = dtc.new_file_set_stamp(path, "res:pending")
        else:
            itself = {"resource_id": "res:pending", "digest": _file_digest(path, cache),
                      "digest_covers": "artifact", "packaging": "file",
                      "measures": {"size_bytes": os.path.getsize(path)}}
            stamp = {"stamp": dtc.STAMP_VERSION, "self": itself}
        media, fmt = _MEDIA.get(os.path.splitext(lower)[1], (None, None))
        if media:
            stamp["self"].setdefault("media_type", media)
        if fmt:
            stamp["self"].setdefault("format", fmt)
    stamp["self"]["resource_id"] = default_resource_id(stamp["self"]["digest"])
    return stamp


def stamp_path_for(path: str) -> str:
    path = os.path.abspath(path.rstrip("/\\"))
    return os.path.join(os.path.dirname(path),
                        dtcstamp().stamp_filename({}, asset=os.path.basename(path)))


def _write_hints(path: str, stamp_path: str, digest: str,
                 masters: Sequence[Tuple[str, str]], when: str,
                 machine: Optional[str]) -> str:
    """``<asset>.hints.json``: the file seen here (private), and each master's
    ``psx://`` locator under ``from`` — ``kind: local``, ``scope: private``.
    Updated, never replaced, while the digest is the same."""
    dtc = dtcstamp()
    hints_path = stamp_path[:-len(dtc.STAMP_SUFFIX)] + dtc.HINTS_SUFFIX
    hints = None
    if os.path.isfile(hints_path):
        try:
            hints = dtc.read_hints(hints_path)
        except (OSError, ValueError):
            hints = None
    if not isinstance(hints, dict) or hints.get("digest") != digest:
        hints = dtc.new_hints(digest)
    dtc.note_seen(hints, os.path.abspath(path), kind="local", scope="private",
                  machine=machine, when=when)
    for master_id, locator in masters:
        dtc.note_parent_seen(hints, master_id, locator, kind="local", scope="private",
                             machine=machine, when=when)
    dtc.write_hints(hints, hints_path)
    return hints_path


def write_one(path: str, *, from_: List[Dict[str, Any]], how: Dict[str, Any],
              by: Dict[str, Any], masters: Sequence[Tuple[str, str]],
              label: Optional[str] = None, description: Optional[str] = None,
              measures: Optional[Dict[str, Any]] = None, cache: Optional[Dict] = None,
              machine: Optional[str] = None) -> Dict[str, Any]:
    """Write the stamp of one exported path. → ``{state, stamp_path, stamp,
    packaging, digest, hints_path, line}``; ``state`` is ``stamped``,
    ``revised`` (new bytes: the previous stamp kept as
    ``<asset>.prev-<hex12>.stamp.json``, the new one ``was_revision_of`` it),
    ``unchanged`` (same bytes: the stamp there stands) or ``failed``. Never
    raises: an export does not fail because of its stamp, it says so."""
    dtc = dtcstamp()
    cache = {} if cache is None else cache
    out: Dict[str, Any] = {"state": "failed", "path": path, "stamp_path": "", "stamp": None,
                           "packaging": "", "digest": "", "hints_path": "", "line": ""}
    try:
        if not path or not os.path.exists(path):
            out["line"] = f"nothing at {path!r}"
            return out
        stamp = _base_stamp(path, cache)
        itself = stamp["self"]
        itself["tier"] = "distribution"
        if label:
            itself["label"] = str(label)
        if description:
            itself["description"] = str(description)
        if measures:
            itself.setdefault("measures", {}).update(measures)
        target = stamp_path_for(path)
        out.update(stamp_path=target, packaging=itself.get("packaging", ""),
                   digest=itself.get("digest", ""))
        previous = None
        if os.path.isfile(target):
            try:
                previous = dtc.read_stamp(target)
            except (OSError, ValueError):
                previous = None
        if previous is not None and (previous.get("self") or {}).get("digest") == itself["digest"]:
            out.update(state="unchanged", stamp=previous,
                       line=f"same bytes, the stamp there stands ({os.path.basename(target)})")
            return out
        stamp["from"] = list(from_)
        stamp["how"] = dict(how)
        stamp["by"] = dict(by)
        if previous is not None:
            old = previous.get("self") or {}
            itself["was_revision_of"] = {"resource_id": old.get("resource_id"),
                                         "digest": old.get("digest")}
            keep = target[:-len(dtc.STAMP_SUFFIX)] + PREVIOUS_INFIX + \
                str(old.get("digest") or "").split(":", 1)[-1][:12] + dtc.STAMP_SUFFIX
            shutil.copy2(target, keep)
        dtc.validate_stamp(stamp)
        dtc.write_stamp(stamp, target)
        out["hints_path"] = _write_hints(path, target, itself["digest"], masters,
                                         by["at"], machine)
        out.update(state="revised" if previous is not None else "stamped",
                   stamp=dtc.clean_stamp(stamp),
                   line=f"stamped {os.path.basename(target)} ({itself.get('packaging')})")
        return out
    except Exception as exc:                        # noqa: BLE001 — said, not raised
        out["line"] = f"not stamped: {exc}"
        return out


# ── THE call ────────────────────────────────────────────────────────────────

def _git(*args: str) -> str:
    try:
        res = subprocess.run(["git", "--no-optional-locks", *args], cwd=HERE,
                             capture_output=True, text=True, timeout=5)
        return res.stdout.strip() if res.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def tool_version() -> str:
    """``__version__`` of ``3DSC_MS_GUI.py``, read as text (never imported)."""
    try:
        with open(os.path.join(HERE, "3DSC_MS_GUI.py"), "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("__version__"):
                    return line.split("=", 1)[1].strip().strip("\"'")
    except OSError:
        pass
    return ""


def tool_commit() -> str:
    """The commit 3DSC for Metashape runs from (``-dirty`` with tracked changes),
    else ``""`` — never invented."""
    commit = _git("rev-parse", "--short", "HEAD")
    if commit and _git("status", "--porcelain", "--untracked-files=no"):
        commit += "-dirty"
    return commit


def software(metashape_version: Optional[str]) -> List[Dict[str, str]]:
    """Metashape, 3DSC for Metashape (version + commit), dtcstamp."""
    out: List[Dict[str, str]] = []
    if metashape_version:
        out.append({"name": METASHAPE_NAME, "version": str(metashape_version)})
    tool = {"name": SOFTWARE_NAME}
    version, commit = tool_version(), tool_commit()
    if version:
        tool["version"] = version
    if commit:
        tool["commit"] = commit
    out.append(tool)
    out.append({"name": "dtcstamp", "version": getattr(dtcstamp(), "__version__", "?")})
    return out


def new_process_id() -> str:
    """One act, one id: every file of one export carries it."""
    return "proc:" + str(uuid.uuid4())


def stamp_export(doc, chunk, asset, paths: Iterable[str], operator: Optional[Dict[str, Any]],
                 *, process_id: Optional[str] = None, dtc_kind: Optional[str] = AUTO,
                 technique: Optional[str] = None, parameters: Optional[Dict[str, Any]] = None,
                 sources: Sequence[Any] = (), photos: Optional[bool] = None,
                 georef_export: bool = False, metashape_version: Optional[str] = None,
                 label: Optional[str] = None, labels: Optional[Dict[str, str]] = None,
                 description: Optional[str] = None,
                 measures: Optional[Dict[str, Dict[str, Any]]] = None,
                 cache: Optional[Dict] = None, when: Optional[str] = None,
                 machine: Optional[str] = None) -> List[Dict[str, Any]]:
    """Stamp every path of ONE export of ``asset`` of ``chunk`` of ``doc``.

    ``asset`` is the Metashape asset exported (a ``Model``…, or None for
    images); it is the master. ``sources`` are other assets of the project the
    files were made from (the source model of the blocks), cited as masters
    too. ``dtc_kind=AUTO`` works the kind out of what Metashape recorded
    (``photogrammetry`` for an asset it built, ``export`` — or
    ``georeferencing`` with ``georef_export`` on a chunk with an active
    reference — otherwise); ``None`` leaves it absent. ``photos`` (default:
    when the kind is photogrammetry) puts the photos in ``from``.
    ``parameters`` are what 3DSC passed to the call; they join the ones read
    from the meta. ``operator`` is :func:`declared_operator`'s, or None.
    → one result per path (:func:`write_one`).
    """
    dtc = dtcstamp()
    cache = {} if cache is None else cache
    kind_name = asset_type(asset)
    built = was_built(asset)
    if dtc_kind == AUTO:
        if built:
            dtc_kind = ASSETS[kind_name][2]
        elif georef_export and has_active_reference(chunk):
            dtc_kind = KIND_GEOREFERENCING
        else:
            dtc_kind = KIND_EXPORT
    if photos is None:
        photos = dtc_kind == KIND_PHOTOGRAMMETRY

    params: Dict[str, Any] = {}
    read: List[str] = []
    if built and dtc_kind == KIND_PHOTOGRAMMETRY:
        params, read = operation_parameters(chunk, asset)
    else:
        info = asset_info(asset)
        params.update(info)
        read = sorted(info)
    params.update(reference_parameters(chunk, cameras=bool(photos)))
    from_: List[Dict[str, Any]] = []
    masters: List[Tuple[str, str]] = []
    for item in [asset] + list(sources or []):
        found = master_of(doc, chunk, item) if item is not None else None
        if found:
            from_.append(found[0])
            masters.append((found[0]["resource_id"], found[1]))
    if photos:
        entries, summary = photo_inputs(chunk, cache)
        from_.extend(entries)
        params["photos/sensors"] = summary
    if parameters:
        params.update(parameters)
    params["3DSC/read_from_meta"] = read

    how: Dict[str, Any] = {"process_id": process_id or new_process_id()}
    if dtc_kind:
        how["dtc_kind"] = dtc_kind
    if technique is None and kind_name and built:
        technique = ASSETS[kind_name][3]
    if technique:
        how["technique"] = technique
    how["parameters"] = params
    how["software"] = software(metashape_version)
    by: Dict[str, Any] = {"at": when or dtc.now_iso()}
    if operator and operator.get("id"):
        by = {"operator": dict(operator), **by}
    results: List[Dict[str, Any]] = []
    covered = set()
    for path in paths:
        if os.path.abspath(path) in covered:
            # a member of a file set stamped above (the texture of an obj):
            # its identity is in that stamp, a second record would split it
            results.append({"state": "member", "path": path, "stamp_path": "", "stamp": None,
                            "packaging": "", "digest": "", "hints_path": "",
                            "line": f"{os.path.basename(path)}: a member of a file set above"})
            continue
        results.append(write_one(
            path, from_=from_, how=how, by=by, masters=masters,
            label=(labels or {}).get(path) or label, description=description,
            measures=(measures or {}).get(path), cache=cache, machine=machine))
        itself = (results[-1].get("stamp") or {}).get("self") or {}
        if itself.get("packaging") == "file_set":
            base = os.path.dirname(os.path.abspath(path))
            covered.update(os.path.join(base, *m["path"].split("/"))
                           for m in itself.get("members") or [])
    return results


def report_line(results: Sequence[Dict[str, Any]]) -> str:
    """One line for the operator: how many stamped, revised, kept, failed."""
    counts: Dict[str, int] = {}
    for r in results:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    if not counts:
        return ""
    parts = [f"{counts[w]} {word}" for w, word in (
        ("stamped", "stamped"), ("revised", "revised"), ("unchanged", "unchanged"),
        ("member", "inside a file set"), ("failed", "not stamped")) if counts.get(w)]
    failed = next((r["line"] for r in results if r["state"] == "failed"), "")
    return "Stamps: " + ", ".join(parts) + (f" ({failed})" if failed else "")
