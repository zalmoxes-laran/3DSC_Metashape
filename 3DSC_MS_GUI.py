# 3DSC for Metashape
# Version aligned with the 3D Survey Collection (3DSC) Blender extension.
# See https://www.extendedmatrix.org
__version__ = "1.7.0"

import Metashape as ps
import os
import sys
import json
import math

# The modules beside this script (pure Python, no Metashape inside): the checks
# and names of the STEP2 blocks, and the stamp of every export.
try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:  # run from the console with exec(): no __file__
    _HERE = os.getcwd()
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import ms_blocks
import dtc_stamp_ms
import ms_dd
import ms_grid
import ms_tileset
import ms_masters


class MetashapeTools:
    def __init__(self, gui=True):
        self.global_shift_file = None
        self.global_shift_line = None
        self.global_shift_vector = None
        self.global_shift_crs_string = None
        self.global_shift_crs = None
        self.workflow_state = {
            "lod0_chunk_key": None,
            "cut_blocks": [],
            "cut_mode": None,
            "cut_folder": None,
            "cut_source_chunk_key": None,
            "generated_chunk_keys": [],
        }
        if gui:
            self.init_gui()
    

    def init_gui(self):
        # Inizializza il menu principale
        label = "3DSC Metashape Tools"
        
        # Rimuovi i menu esistenti prima di aggiungerli (per evitare duplicazioni)
        try:
            ps.app.removeMenuItem(label)
        except:
            pass  # Ignora errori se il menu non esiste

        # One entry per step of the chain (see README, «The chain»).
        self.restore_shift_from_doc()
        L = label + "/"
        ps.app.addMenuItem(L + "0 · Operator (ORCID)…   [" + self.operator_preview() + "]", self.operator_panel)
        ps.app.addMenuItem(L + "1 · Shift…   [" + self.get_global_shift_preview(compact=True) + "]", self.shift_panel)
        ps.app.addMenuItem(L + "2 · Import/Models…", self.import_panel)
        ps.app.addMenuItem(L + "2 · Import/Photos from Another Project…", self.append_photos_from_project)
        ps.app.addMenuItem(L + "3 · Masters (geometric · texturable · tileable)…", self.masters_panel)
        ps.app.addMenuItem(L + "4 · Blocks (cut the tileable master on a grid)…", self.blocks_panel)
        ps.app.addMenuItem(L + "5 · Texturing (Demetrescu-D'Annibale rule)…", self.texturing_panel)
        ps.app.addMenuItem(L + "6 · LODs + Normal Maps (blocks)", self.generate_workflow_lods_experimental)
        ps.app.addMenuItem(L + "7 · Tileset (Cesium 3D Tiles, .3tz)…", self.tileset_panel)
        ps.app.addMenuItem(L + "8 · Export/Blocks (textured, with LODs)", self.export_workflow_blocks_textured)
        ps.app.addMenuItem(L + "8 · Export/Models (one file per chunk)", self.export_multiple_models)
        ps.app.addMenuItem(L + "8 · Export/Active Model with Shift", self.export_single_model_with_shift)
        ps.app.addMenuItem(L + "8 · Export/Undistorted Images (active chunk)", self.export_undistorted_images_active_chunk)
        ps.app.addMenuItem(L + "Utility/Rename Chunks…", self.rename_panel)
        ps.app.addMenuItem(L + "Utility/Flag LOD0 (old STEP1)", self.prepare_or_flag_lod0)
        ps.app.addMenuItem(L + "Help/Documentation of 3DSC for Metashape", self.open_docs)
        ps.app.addMenuItem(L + "Help/About · Rule and References", self.about_panel)

    @property
    def doc(self):
        # Always return the CURRENT active document. Do not cache it: the menu
        # persists across File > Open, so a cached reference would go stale and
        # every command would act on (or reject) the wrong/old document.
        return ps.app.document

    def show_menu(self):
        # Visualizza un messaggio quando si clicca sul menu principale
        ps.app.messageBox("3DSC Metashape Tools - Select a specific tool from the submenu.")

    def _chunk_key(self, chunk):
        return getattr(chunk, "key", id(chunk))

    def _get_chunk_by_key(self, chunk_key):
        for chunk in self.doc.chunks:
            if self._chunk_key(chunk) == chunk_key:
                return chunk
        return None

    def _read_shift_parameters_from_file(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
        return self._parse_shift_line(first_line)

    def _parse_shift_line(self, first_line):
        first_line = first_line.strip()
        parts = first_line.split()
        if len(parts) < 4:
            raise Exception("Invalid shift.txt format. Expected: CRS SHIFT_X SHIFT_Y SHIFT_Z")

        crs_string = parts[0]
        shift = ps.Vector([float(parts[1]), float(parts[2]), float(parts[3])])
        crs = None
        if crs_string.upper() not in ['LOCAL', 'LOCAL_CS', 'NONE']:
            crs = ps.CoordinateSystem(crs_string)

        return {
            "line": first_line,
            "crs_string": crs_string,
            "crs": crs,
            "shift": shift,
        }

    # The shift lives in the project (doc.meta), so it comes back with the .psx.
    SHIFT_META_LINE = "3dsc_shift_line"
    SHIFT_META_FILE = "3dsc_shift_file"

    def set_shift_from_file(self, path):
        self._set_global_shift_state(path, self._read_shift_parameters_from_file(path))

    def _save_shift_to_doc(self):
        try:
            meta = self.doc.meta
            meta[self.SHIFT_META_LINE] = self.global_shift_line or ""
            meta[self.SHIFT_META_FILE] = self.global_shift_file or ""
        except Exception as e:
            print(f"[3DSC shift] not saved in the project: {e}")

    def restore_shift_from_doc(self):
        """Read the shift kept in the project; a project without one clears it."""
        try:
            line = self.doc.meta[self.SHIFT_META_LINE]
            path = self.doc.meta[self.SHIFT_META_FILE]
        except Exception:
            line, path = None, None
        if not line:
            if self.global_shift_line is not None and getattr(self, "_shift_doc", None) != id(self.doc):
                self.global_shift_file = self.global_shift_line = self.global_shift_vector = None
                self.global_shift_crs_string = self.global_shift_crs = None
            self._shift_doc = id(self.doc)
            return
        if line != self.global_shift_line:
            try:
                parsed = self._parse_shift_line(line)
                self.global_shift_file = path or None
                self.global_shift_line = parsed["line"]
                self.global_shift_vector = parsed["shift"]
                self.global_shift_crs_string = parsed["crs_string"]
                self.global_shift_crs = parsed["crs"]
            except Exception as e:
                print(f"[3DSC shift] the project's shift is unreadable: {e}")
        self._shift_doc = id(self.doc)

    def _set_global_shift_state(self, file_path, parsed_shift):
        self.global_shift_file = file_path
        self.global_shift_line = parsed_shift["line"]
        self.global_shift_vector = parsed_shift["shift"]
        self.global_shift_crs_string = parsed_shift["crs_string"]
        self.global_shift_crs = parsed_shift["crs"]
        self._save_shift_to_doc()
        self.init_gui()

    def get_global_shift_preview(self, compact=False):
        if self.global_shift_vector is None:
            return "NONE"
        text = (
            f"{self.global_shift_crs_string} "
            f"{self.global_shift_vector.x:.3f} "
            f"{self.global_shift_vector.y:.3f} "
            f"{self.global_shift_vector.z:.3f}"
        )
        if compact and len(text) > 56:
            return text[:56] + "..."
        return text

    def clear_global_shift(self, quiet=False):
        self.global_shift_file = None
        self.global_shift_line = None
        self.global_shift_vector = None
        self.global_shift_crs_string = None
        self.global_shift_crs = None
        self._save_shift_to_doc()
        self.init_gui()
        if not quiet:
            ps.app.messageBox("Global shift cleared.")

    def _resolve_shift_for_operation(self, operation_label, ask_if_missing=True):
        self.restore_shift_from_doc()
        if self.global_shift_vector is not None:
            return self.global_shift_crs, self.global_shift_vector, self.global_shift_line

        if not ask_if_missing:
            return None, None, None

        shift_path = ps.app.getOpenFileName(f"{operation_label} - Select shift.txt (optional)")
        if not shift_path:
            return None, None, None
        parsed = self._read_shift_parameters_from_file(shift_path)
        return parsed["crs"], parsed["shift"], parsed["line"]

    def _set_chunk_textured_flag(self, chunk, value):
        if hasattr(chunk, "meta"):
            chunk.meta["3dsc_workflow_textured"] = "1" if value else "0"

    def _is_chunk_textured(self, chunk):
        try:
            if hasattr(chunk, "meta") and chunk.meta.get("3dsc_workflow_textured") == "1":
                return True
        except Exception:
            pass

        model = getattr(chunk, "model", None)
        if not model:
            return False

        try:
            if hasattr(model, "textures") and len(model.textures) > 0:
                return True
        except Exception:
            pass
        return False

    def _safe_remove_asset(self, chunk, asset):
        if asset is None:
            return
        try:
            chunk.remove(asset)
        except Exception:
            pass

    def _clear_all_models_in_chunk(self, chunk):
        models = []
        try:
            models = list(chunk.models)
        except Exception:
            pass

        for model in models:
            self._safe_remove_asset(chunk, model)

        if getattr(chunk, "model", None):
            self._safe_remove_asset(chunk, chunk.model)

    def _prepare_lightweight_chunk(self, chunk):
        self._clear_all_models_in_chunk(chunk)
        for attr in ["tiled_model", "dense_cloud", "depth_maps", "elevation", "orthomosaic"]:
            asset = getattr(chunk, attr, None)
            self._safe_remove_asset(chunk, asset)

    def _extract_models(self, chunk):
        try:
            models = list(chunk.models)
            if models:
                return models
        except Exception:
            pass
        return [chunk.model] if getattr(chunk, "model", None) else []

    def _activate_model(self, chunk, model):
        try:
            chunk.model = model
            return True
        except Exception:
            return False

    def _mesh_stats(self, model):
        """Return (face_count, surface_area_m2, density_faces_per_m2) for a model.

        Any value may be None if unavailable. Note: area() is the 3D surface
        area (walls, roof, terrain), not the ground footprint, so density is
        faces per m² of mesh surface.
        """
        if not model:
            return None, None, None
        try:
            faces = len(model.faces)
        except Exception:
            faces = None
        try:
            area = model.area()
        except Exception:
            area = None
        density = (faces / area) if (faces and area) else None
        return faces, area, density

    def _model_format_for(self, path):
        """Pick a Metashape ModelFormat from a file extension."""
        ext = os.path.splitext(path)[1].lower()
        MF = ps.ModelFormat
        return {
            ".obj": MF.ModelFormatOBJ,
            ".ply": MF.ModelFormatPLY,
            ".dae": MF.ModelFormatCOLLADA,
        }.get(ext, MF.ModelFormatOBJ)

    def _scan_files(self, folder):
        found = set()
        for root, _dirs, files in os.walk(folder):
            for fn in files:
                found.add(os.path.join(root, fn))
        return found

    # ── the stamp of every export (dtc_stamp_ms) ───────────────────────────

    SETTINGS_ASK_OPERATOR = "3dsc_metashape/ask_operator"

    def operator_preview(self):
        try:
            orcid, name = dtc_stamp_ms.load_identity(ps.app)
        except Exception:
            orcid, name = "", ""
        return (name + " " + orcid).strip() if orcid else "anonymous"

    def _ask_operator(self):
        """The declared operator of this export, or None (anonymous): the one
        set in «Operator», asked again only when that panel says so. A failing
        dialog never stops the export."""
        try:
            ask = str(ps.app.settings.value(self.SETTINGS_ASK_OPERATOR) or "0") == "1"
            orcid, name = dtc_stamp_ms.load_identity(ps.app)
            if not ask:
                return dtc_stamp_ms.declared_operator(orcid, name) if orcid else None
            return dtc_stamp_ms.ask_operator(ps.app)
        except Exception as e:
            print(f"[3DSC stamp] operator not asked: {e}")
            return None

    def _stamp(self, chunk, asset, paths, operator, doc=None, **kwargs):
        """Stamp the files of one export; → results. Never raises: an export
        does not fail because its stamp could not be written, it says so."""
        try:
            results = dtc_stamp_ms.stamp_export(
                doc or self.doc, chunk, asset, [p for p in paths if p], operator,
                metashape_version=ps.app.version, **kwargs)
        except Exception as e:
            results = [{"state": "failed", "line": f"not stamped: {e}"}]
        line = dtc_stamp_ms.report_line(results)
        if line:
            print(f"[3DSC stamp] {line}")
        return results

    def _export_files(self, out_path):
        """The files an exportModel call wrote for ``out_path``: the obj (its mtl
        and textures are found by the stamp as members of its file set). The
        quotes Metashape puts around a space-free ``mtllib`` name are taken
        off first, or dtcstamp 0.1.3 would not find the mtl."""
        if not os.path.exists(out_path):
            return []
        if out_path.lower().endswith(".obj"):
            try:
                ms_blocks.unquote_mtllib(out_path)
            except OSError:
                pass
        return [out_path]

    def _import_block(self, chunk, obj_path, srs_origin, grid_crs=None):
        """Bring one block back where it was cut. Blocks cut on a rotated grid
        are written in the grid's own CRS (no metadata.xml): Metashape converts
        them back from ``grid_crs``."""
        if grid_crs is not None:
            chunk.importModel(path=obj_path, format=self._model_format_for(obj_path), crs=grid_crs)
            return
        self._import_block_srs(chunk, obj_path, srs_origin)

    def _import_block_srs(self, chunk, obj_path, srs_origin):
        """Import a block file back into ``chunk`` WHERE IT WAS CUT.

        Metashape writes the blocks in a local frame whose origin is the
        ``<SRSOrigin>`` of the ``metadata.xml`` beside them. Imported without
        it, a block lands near the CRS origin, far from the cameras, and STEP3
        textures it with nothing: measured 2 Oct 2026 on San Pietro, 28 pages
        of 4096² all with one sha256. With the origin as ``shift`` and the
        chunk's CRS the block is back under its cameras."""
        kwargs = dict(path=obj_path, format=self._model_format_for(obj_path))
        if srs_origin:
            kwargs["shift"] = ps.Vector(list(srs_origin))
            if getattr(chunk, "crs", None) is not None:
                kwargs["crs"] = chunk.crs
        chunk.importModel(**kwargs)

    # ── the grid of the cut (ms_grid): rotated in the cut only ─────────────

    def _vertex_matrix(self, chunk, model):
        """Matrix from a model's vertex coordinates to geocentric (ECEF).

        Measured 8 Nov 2026 on Metashape 2.3.2: a model BUILT by Metashape has
        an identity ``Model.transform`` and internal vertices (→ the chunk's
        transform); an IMPORTED model carries its own translation to ECEF and
        the chunk's transform does not apply."""
        mt = getattr(model, "transform", None)
        if isinstance(mt, ps.Matrix):
            ident = all(abs(mt[r, c] - (1.0 if r == c else 0.0)) < 1e-12 for r in range(4) for c in range(4))
            if not ident:
                return mt
        return chunk.transform.matrix

    def _mesh_xyz(self, chunk, limit=20000, model=None):
        """Up to ``limit`` vertices of ``model`` (default: the active one), as
        (x, y, z) in the chunk's CRS."""
        model = model if model is not None else chunk.model
        verts = model.vertices
        n = len(verts)
        T = self._vertex_matrix(chunk, model)
        step = max(1, n // limit)
        out = []
        for i in range(0, n, step):
            q = chunk.crs.project(T.mulp(verts[i].coord))
            out.append((q[0], q[1], q[2]))
        return out

    def _mesh_xy(self, chunk, crs, limit=20000, model=None):
        return [(x, y) for x, y, _z in self._mesh_xyz(chunk, limit, model)]

    # measures kept in the meta, so a panel opens without loading meshes
    # (40.9 M faces: 5.6 s to count, 7 s for the area — Templu Mare, 10 Nov)
    def _meta_get(self, holder, key):
        try:
            if key in holder.meta.keys():
                return holder.meta[key]
        except Exception:
            pass
        return None

    def models_info(self, chunk, measure=False):
        """→ (rows, area_m2): every model of ``chunk`` with its faces (cached
        or measured), label and texture; the chunk's surface, measured once on
        its lightest model."""
        rows = []
        for m in list(chunk.models or []):
            f = self._meta_get(m, "3dsc_faces")
            if measure or f is None:
                if measure:
                    f = len(m.faces)
                    m.meta["3dsc_faces"] = str(f)
                    ps.app.update()
            try:
                tex = len(m.textures) > 0
            except Exception:
                tex = False
            rows.append({"key": m.key, "label": m.label or "", "faces": int(f) if f else None,
                         "textured": tex, "level": self._meta_get(m, "3dsc_master_level") or ""})
        area = self._meta_get(chunk, "3dsc_area_m2")
        if measure and rows:
            known = [r for r in rows if r["faces"]]
            if known:
                light = min(known, key=lambda r: r["faces"])
                model = [m for m in chunk.models if m.key == light["key"]][0]
                area = model.area()
                chunk.meta["3dsc_area_m2"] = "%.3f" % area
        return rows, (float(area) if area else None)

    def model_name(self, row):
        base = row.get("label") or "model %d" % (row["key"] + 1)
        if row.get("faces"):
            base += " · %s faces" % "{:,}".format(row["faces"]).replace(",", "\u202f")
        return base

    # the orientation of the grid: what the bearing is measured from
    def _selected_line(self, chunk):
        """The first selected shape of the chunk, as its two farthest-apart
        ends (x, y) in the chunk CRS: the line drawn along the monument's axis."""
        shapes = getattr(chunk, "shapes", None)
        if not shapes:
            raise Exception("draw a line along the axis (Draw Polyline) and select it")
        for sh in shapes:
            if not getattr(sh, "selected", False):
                continue
            g = sh.geometry
            coords = g.coordinates
            if coords and isinstance(coords[0], (list, tuple)) and coords and not hasattr(coords[0], "x"):
                coords = coords[0]                       # a polygon: its outer ring
            pts = []
            for v in coords:
                v = ps.Vector(list(v)) if not isinstance(v, ps.Vector) else v
                if shapes.crs is not None and chunk.crs is not None and shapes.crs.wkt != chunk.crs.wkt:
                    v = ps.CoordinateSystem.transform(v, shapes.crs, chunk.crs)
                pts.append((v[0], v[1]))
            if len(pts) >= 2:
                if len(pts) == 2:
                    return pts[0], pts[1]
                best = max(((a, b) for a in pts for b in pts), key=lambda ab: (ab[0][0] - ab[1][0]) ** 2 + (ab[0][1] - ab[1][1]) ** 2)
                return best
        raise Exception("no selected shape: draw a line along the axis (Draw Polyline) and select it")

    def _marker_xy(self, chunk, label):
        for m in chunk.markers:
            if m.label == label:
                if m.position is not None:
                    q = chunk.crs.project(chunk.transform.matrix.mulp(m.position))
                    return (q[0], q[1])
                if m.reference.location is not None:
                    return (m.reference.location[0], m.reference.location[1])
        raise Exception("marker %s has no position" % label)

    def project_grid(self):
        """The grid saved in the project (doc.meta), or None."""
        raw = self._meta_get(self.doc, "3dsc_grid")
        try:
            return json.loads(raw) if raw else None
        except ValueError:
            return None

    def save_project_grid(self, info, side, chunk):
        self.doc.meta["3dsc_grid"] = json.dumps({
            "wkt": info["wkt"], "origin": info["origin"][:2], "side": side,
            "bearing": info["bearing"], "true_bearing": info["true_bearing"],
            "from_chunk": chunk.label or "", "mode": info["mode"]})

    def _grid_for(self, chunk, side, grid):
        """→ (blocks_crs, blocks_origin, info) for ``grid`` = {"mode": "north" |
        "fit" | "bearing" | "line" | "markers" | "project", ...}; (None, None,
        info) for north. Every bearing is measured in the chunk's own map
        grid; the local oblique Mercator is re-aimed to absorb the meridian
        convergence. ``info`` also lists the cells that hold mesh."""
        mode = (grid or {}).get("mode", "north")
        crs = getattr(chunk, "crs", None)
        if mode == "north" and (crs is None or chunk.model is None or "PROJCS" not in crs.wkt):
            return None, None, {"mode": "north", "cells_list": [], "cells": 0, "north_cells": 0,
                                "origin": [0.0, 0.0], "z": 0.0, "bearing": 0.0}
        if crs is None or chunk.model is None:
            raise Exception("the grid needs a georeferenced chunk with an active model")
        pts3 = self._mesh_xyz(chunk)
        pts = [(x, y) for x, y, _z in pts3]
        zs = sorted(z for _x, _y, z in pts3)
        z_mid = zs[len(zs) // 2] if zs else 0.0
        if mode == "north":
            ox = math.floor(min(p[0] for p in pts) / side) * side
            oy = math.floor(min(p[1] for p in pts) / side) * side
            cells = sorted({(int(math.floor((x - ox) / side)), int(math.floor((y - oy) / side))) for x, y in pts})
            return None, None, {"mode": "north", "cells_list": cells, "cells": len(cells),
                                "origin": [ox, oy], "z": z_mid, "bearing": 0.0, "north_cells": len(cells)}
        if "PROJCS" not in crs.wkt:
            raise Exception("a rotated grid needs a projected CRS (metres), not %s" % crs.name)
        why = ""
        if mode == "project":
            pg = self.project_grid()
            if not pg:
                raise Exception("no project grid saved yet")
            gcrs = ps.CoordinateSystem(pg["wkt"])
            origin = (float(pg["origin"][0]), float(pg["origin"][1]))
            side = float(pg["side"])
            bearing, aim = float(pg["bearing"]), float(pg["true_bearing"])
            why = "the project grid (from «%s»)" % pg.get("from_chunk", "")
        else:
            if mode == "fit":
                bearing = ms_grid.fit_bearing(pts)
                why = "the tightest rectangle around the mesh footprint"
            elif mode == "line":
                a, b = self._selected_line(chunk)
                bearing = ms_grid.reduce_bearing(ms_grid.bearing_of(a, b))
                why = "the selected line"
            elif mode == "markers":
                a = self._marker_xy(chunk, grid["a"])
                b = self._marker_xy(chunk, grid["b"])
                bearing = ms_grid.reduce_bearing(ms_grid.bearing_of(a, b))
                why = "markers %s → %s" % (grid["a"], grid["b"])
            else:
                bearing = ms_grid.reduce_bearing(float(grid.get("bearing", 0.0)))
                why = "the bearing typed"
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
            geog = crs.geogcs
            ll = ps.CoordinateSystem.transform(ps.Vector([cx, cy, 0.0]), crs, geog)
            b = math.radians(bearing)
            p0 = ps.Vector([cx, cy, 0.0])
            p1 = ps.Vector([cx + 10.0 * math.sin(b), cy + 10.0 * math.cos(b), 0.0])
            aim = bearing
            for _ in range(2):
                gcrs = ps.CoordinateSystem(ms_grid.oblique_wkt(geog.wkt, ll[1], ll[0], aim))
                q0 = ps.CoordinateSystem.transform(p0, crs, gcrs)
                q1 = ps.CoordinateSystem.transform(p1, crs, gcrs)
                aim += ms_grid.bearing_of((q0[0], q0[1]), (q1[0], q1[1]))
            gcrs = ps.CoordinateSystem(ms_grid.oblique_wkt(geog.wkt, ll[1], ll[0], aim))
            origin = None
        gpts = []
        for x, y in pts:
            q = ps.CoordinateSystem.transform(ps.Vector([x, y, z_mid]), crs, gcrs)
            gpts.append((q[0], q[1]))
        if origin is None:
            origin = ms_grid.layout(gpts, side)["origin"]
        cells = sorted({(int(math.floor((x - origin[0]) / side)), int(math.floor((y - origin[1]) / side)))
                        for x, y in gpts})
        nox = math.floor(min(p[0] for p in pts) / side) * side
        noy = math.floor(min(p[1] for p in pts) / side) * side
        north = {(int(math.floor((x - nox) / side)), int(math.floor((y - noy) / side))) for x, y in pts}
        info = {"mode": mode, "why": why, "bearing": bearing, "true_bearing": aim, "side": side,
                "cells": len(cells), "cells_list": cells, "north_cells": len(north),
                "origin": [origin[0], origin[1]], "wkt": gcrs.wkt, "z": z_mid}
        return gcrs, ps.Vector([origin[0], origin[1], 0.0]), info

    # the preview: the cells drawn as shapes in the chunk, a group of their own
    PREVIEW_GROUP = "3DSC grid preview"

    def clear_grid_preview(self, chunk):
        shapes = getattr(chunk, "shapes", None)
        if not shapes:
            return 0
        groups = [g for g in shapes.groups if g.label == self.PREVIEW_GROUP]
        if not groups:
            return 0
        keys = {g.key for g in groups}
        doomed = [sh for sh in shapes if sh.group is not None and sh.group.key in keys]
        shapes.remove(doomed)
        try:
            shapes.remove(groups)
        except Exception:
            for g in groups:
                try:
                    shapes.remove(g)
                except Exception:
                    pass
        return len(doomed)

    def draw_grid_preview(self, chunk, side, grid):
        """Draw the cells that will become blocks; → info with a text line."""
        gcrs, _o, info = self._grid_for(chunk, side, grid)
        side = info.get("side", side)
        self.clear_grid_preview(chunk)
        if chunk.shapes is None:
            chunk.shapes = ps.Shapes()
            chunk.shapes.crs = chunk.crs
        shapes = chunk.shapes
        grp = shapes.addGroup()
        grp.label = self.PREVIEW_GROUP
        try:
            grp.color = (255, 120, 0)
        except Exception:
            pass
        ox, oy = info["origin"]
        z = info["z"]
        i0 = min(c[0] for c in info["cells_list"])
        j0 = min(c[1] for c in info["cells_list"])
        for (i, j) in info["cells_list"]:
            ring = []
            for (dx, dy) in ((0, 0), (1, 0), (1, 1), (0, 1), (0, 0)):
                v = ps.Vector([ox + (i + dx) * side, oy + (j + dy) * side, z])
                if gcrs is not None:
                    v = ps.CoordinateSystem.transform(v, gcrs, chunk.crs)
                if shapes.crs is not None and shapes.crs.wkt != chunk.crs.wkt:
                    v = ps.CoordinateSystem.transform(v, chunk.crs, shapes.crs)
                ring.append(v)
            sh = shapes.addShape()
            sh.group = grp
            sh.label = ms_blocks.grid_name((i - i0 + 1, j - j0 + 1))[6:]
            try:
                sh.geometry = ps.Geometry.LineString(ring)
            except Exception:
                sh.geometry = ps.Geometry.Polygon(ring)
        info["text"] = ("%s: %d cells hold mesh (north grid: %d)%s" % (
            "north grid" if info["mode"] == "north" else "bearing %.2f° from %s" % (info["bearing"], info["why"]),
            info["cells"], info["north_cells"],
            "" if info["mode"] == "north" else ". The orange grid is in the view (group «%s»)." % self.PREVIEW_GROUP))
        return info

    def _georef_rotated_blocks(self, chunk, source_model, files, folder, tile_models=None):
        """Bring the files of a rotated cut into the chunk's CRS.

        Measured 8 Nov 2026 (Metashape 2.3.2): with a custom ``blocks_crs`` the
        block files carry no metadata.xml and a frame of their own. Metashape
        also adds one model per block to the chunk: each is exported again
        here, by Metashape itself, in the chunk's CRS minus one origin (the
        mesh centre, to the metre), over the file of the cut; a metadata.xml
        like the one of a north cut is written beside them. From here on a
        rotated cut is the same folder as a north one."""
        tile_models = tile_models or {}
        crs = chunk.crs
        pts = self._mesh_xy(chunk, crs, limit=2000, model=source_model)
        origin = (float(round(sum(p[0] for p in pts) / len(pts))),
                  float(round(sum(p[1] for p in pts) / len(pts))), 0.0)
        missing = []
        for path in files:
            if not path.lower().endswith(".obj"):
                continue
            stem = os.path.splitext(os.path.basename(path))[0]
            tm = tile_models.get(stem)
            if tm is None:
                missing.append(stem)
                continue
            chunk.model = tm
            kw = dict(path=path, format=ps.ModelFormat.ModelFormatOBJ, crs=crs,
                      shift=ps.Vector(list(origin)), clip_to_boundary=False)
            try:
                chunk.exportModel(save_texture=False, **kw)
            except TypeError:
                chunk.exportModel(**kw)
            ps.app.update()
        if source_model is not None:
            chunk.model = source_model
        if missing:
            raise Exception("rotated cut: no block model in the chunk for %s" % ", ".join(missing[:10]))
        auth = getattr(crs, "authority", "") or ""
        srs = auth.replace("::", ":") if auth else crs.wkt
        with open(os.path.join(folder, "metadata.xml"), "w", encoding="utf-8") as fh:
            fh.write('<?xml version="1.0" encoding="utf-8"?>\n<ModelMetadata version="1">\n'
                     "\t<!--Spatial Reference System-->\n\t<SRS>%s</SRS>\n"
                     "\t<!--Origin in Spatial Reference System-->\n"
                     "\t<SRSOrigin>%r,%r,%r</SRSOrigin>\n"
                     "\t<!--3DSC: blocks cut on a rotated grid, see grid_crs.wkt-->\n"
                     "</ModelMetadata>\n" % (srs, origin[0], origin[1], origin[2]))
        return origin

    def grid_preview(self, chunk, side, grid):
        """What the cut will be, drawn in the view, without cutting."""
        info = self.draw_grid_preview(chunk, side, grid)
        return {"text": info["text"], "bearing": info.get("bearing")}

    def _build_block_model_and_collect(self, chunk, target_area_m2, blocks_folder, grid=None):
        """Build a Metashape **Block Model** (mesh built already split into
        separate spatial blocks) and collect the exported block meshes.

        Uses ``chunk.buildModel(split_in_blocks=True, blocks_size=<side_m>,
        export_blocks=True, output_folder=...)``. ``blocks_size`` is in CRS
        units (metres) = the block side, so side = sqrt(area). This is the
        native equivalent of the 3DSC Blender "Cutter" and — unlike clipping an
        existing mesh — actually produces distinct spatial pieces, because the
        split happens at build time.

        Tries ``source_data=ModelData`` first (re-tile the existing LOD0 mesh,
        fast), falling back to ``DepthMapsData`` (rebuild from depth maps).
        Returns ``(cut_blocks, produced_files, source_used)``.
        """
        side = max(0.1, math.sqrt(max(0.01, target_area_m2)))
        before = self._scan_files(blocks_folder)
        grid_crs, grid_origin, self._last_grid = self._grid_for(chunk, side, grid)

        sources = []
        DS = getattr(ps, "DataSource", None)
        if DS is not None and hasattr(DS, "ModelData"):
            sources.append(("ModelData", DS.ModelData))
        if DS is not None and hasattr(DS, "DepthMapsData"):
            sources.append(("DepthMapsData", DS.DepthMapsData))
        if not sources:
            sources = [("default", None)]

        last_err = None
        source_used = None
        for name, src in sources:
            try:
                kwargs = dict(
                    surface_type=ps.SurfaceType.Arbitrary,
                    interpolation=ps.Interpolation.EnabledInterpolation,
                    face_count=ps.FaceCount.HighFaceCount,
                    split_in_blocks=True,
                    blocks_size=float(side),
                    export_blocks=True,
                    output_folder=blocks_folder,
                    build_texture=False,
                    replace_asset=False,
                )
                if grid_crs is not None:
                    kwargs["blocks_crs"] = grid_crs
                    kwargs["blocks_origin"] = grid_origin
                if src is not None:
                    kwargs["source_data"] = src
                chunk.buildModel(**kwargs)
                source_used = name
                break
            except Exception as e:
                last_err = e
                continue
        if source_used is None:
            raise Exception(f"Block model build failed: {str(last_err)}")

        ps.app.update()
        produced = sorted(self._scan_files(blocks_folder) - before)
        mesh_files = [p for p in produced if p.lower().endswith((".obj", ".ply"))]

        cut_blocks = []
        for idx, path in enumerate(mesh_files):
            cut_blocks.append({
                "index": idx,
                "name": os.path.splitext(os.path.basename(path))[0],
                "obj_path": path,
                "png_path": None,
            })
        return cut_blocks, produced, source_used

    def _get_workflow_chunks(self):
        chunks = []
        for chunk_key in self.workflow_state.get("generated_chunk_keys", []):
            chunk = self._get_chunk_by_key(chunk_key)
            if chunk:
                chunks.append(chunk)
        return chunks

    def _show_step3_options_dialog(self):
        # Native Metashape dialogs ONLY. A tkinter window (tk.Tk + mainloop)
        # crashes Metashape on macOS, where Tk cannot share the Qt event loop.
        try:
            area_str = ps.app.getString(
                "STEP2 - Block plan area in m² (target size of each block):", "80"
            )
            if not area_str:
                return None
            area_value = float(str(area_str).replace(",", "."))
            if area_value <= 0:
                ps.app.messageBox("Block area must be > 0.")
                return None

            run_step1_now = ps.app.getBool(
                "Run STEP1 now (prepare/flag LOD0) before cutting?"
            )
            output_multi_chunks = ps.app.getBool(
                "Output one chunk per block? (Yes = recommended)"
            )

            min_faces_str = ps.app.getString(
                "STEP2 - Minimum faces per tile (0 = keep every tile as it is).\n"
                "A tile under it is merged into its largest touching neighbour, "
                "or only flagged:", str(ms_blocks.DEFAULT_MIN_FACES)
            )
            min_faces = int(float(str(min_faces_str or "0").replace(",", ".")))
            small_mode = ms_blocks.SMALL_MERGE
            if min_faces > 0 and not ps.app.getBool(
                    "Merge each small tile into its largest touching neighbour?\n"
                    "(No = keep them, only flag them in the report)"):
                small_mode = ms_blocks.SMALL_FLAG

            out_dir = ps.app.getExistingDirectory("Select STEP2 output folder")
            if not out_dir:
                return None

            # Sensible defaults for the rarely-changed options (previously
            # checkboxes in the tkinter form).
            return {
                "target_area_m2": area_value,
                "run_step2_now": bool(run_step1_now),
                "output_multi_chunks": bool(output_multi_chunks),
                "min_faces": max(0, min_faces),
                "small_mode": small_mode,
                "grid_naming": True,
                "export_temp_textures": False,
                "cleanup_temp_files": False,
                "rebuild_tiled_model": True,
                "export_root": out_dir,
            }
        except Exception as e:
            ps.app.messageBox(f"Error - STEP2 options: {str(e)}")
            return None

    def _show_step7_options_dialog(self):
        # Native Metashape dialogs ONLY (see note in _show_step3_options_dialog).
        try:
            out_dir = ps.app.getExistingDirectory("Select STEP5 export folder")
            if not out_dir:
                return None

            has_global_shift = self.global_shift_vector is not None
            use_shift = ps.app.getBool("Apply a coordinate shift on export?")

            shift_file = ""
            if use_shift and not has_global_shift:
                shift_file = ps.app.getOpenFileName("Select shift.txt file for STEP5")
                if not shift_file:
                    use_shift = False
                    ps.app.messageBox("No shift file selected - exporting without shift.")

            save_textures = ps.app.getBool("Export UV + textures?")

            return {
                "export_folder": out_dir,
                "use_shift": bool(use_shift),
                "save_textures": bool(save_textures),
                "shift_file": shift_file,
            }
        except Exception as e:
            ps.app.messageBox(f"Error - STEP5 options: {str(e)}")
            return None

    # Implementation of existing scripts
    def import_multiple_models(self):
        try:
            # Get folder of 3D models
            path_folder = ps.app.getExistingDirectory("Specify folder with 3D models: ")
            if not path_folder:
                return
            path_folder += "/"
            
            # Process as in the original script
            file_list = os.listdir(path_folder)
            coord_shift = False
            
            # Look for shift file
            projection_coor = None
            for ob_txt in file_list:
                if ob_txt.endswith(".txt"):
                    file_txt_fullpath = str(path_folder + ob_txt)
                    print(file_txt_fullpath)
                    with open(file_txt_fullpath, 'r', encoding='utf-8') as f:
                        first = f.readline()
                        parts = first.split()
                        crs_string = parts[0]
                        shift_coor_x = float(parts[1])
                        shift_coor_y = float(parts[2])
                        shift_coor_z = float(parts[3])
                        shift_coor = ps.Vector([shift_coor_x, shift_coor_y, shift_coor_z])
                        coord_shift = True
                        
                        # Handle CRS: only set if not LOCAL or NONE
                        if crs_string.upper() not in ['LOCAL', 'LOCAL_CS', 'NONE']:
                            projection_coor = crs_string
                        
                        print(f"Using shift coordinates: {shift_coor_x}, {shift_coor_y}, {shift_coor_z}")
                        if projection_coor:
                            print(f"Using CRS: {projection_coor}")
                        else:
                            print("Using local coordinates (no CRS)")

            if not coord_shift and self.global_shift_vector is not None:
                coord_shift = True
                shift_coor = self.global_shift_vector
                projection_coor = self.global_shift_crs_string if self.global_shift_crs else None
                print("Using global shift from GUI settings.")
            
            # Import each model
            obj_list = []
            chunk_number = 1
            
            for ob in file_list:
                if ob.startswith("."):
                    continue
                    
                if ob.endswith((".obj", ".ply", ".dae")):
                    format_file = str(ob.split(".")[-1])
                    
                    if format_file == "obj":
                        format_file_import = ps.ModelFormat.ModelFormatOBJ
                    elif format_file == "ply":
                        format_file_import = ps.ModelFormat.ModelFormatPLY
                    elif format_file == "dae":
                        format_file_import = ps.ModelFormat.ModelFormatCOLLADA
                        
                    ob_fullpath = str(path_folder + ob)
                    obj_list.append(ob_fullpath)
                    print(f"Importing {ob}")
                    
                    # Create a new chunk or use existing one
                    if chunk_number >= len(self.doc.chunks):
                        # Copy the first chunk if it exists
                        if len(self.doc.chunks) > 0:
                            self.doc.chunk = self.doc.chunks[0]
                            chunk = self.doc.chunks[0].copy()
                        else:
                            chunk = self.doc.addChunk()
                    
                    self.doc.chunk = self.doc.chunks[chunk_number]
                    self.doc.chunk.label = ob
                    
                    # Import with or without shift
                    if coord_shift:
                        if projection_coor:
                            # Import with CRS and shift
                            self.doc.chunk.importModel(path=ob_fullpath, format=format_file_import, 
                                                     crs=ps.CoordinateSystem(projection_coor), shift=shift_coor)
                        else:
                            # Import with shift only (local coordinates)
                            self.doc.chunk.importModel(path=ob_fullpath, format=format_file_import, shift=shift_coor)
                    else:
                        self.doc.chunk.importModel(path=ob_fullpath, format=format_file_import)
                        
                    chunk_number += 1
            
            ps.app.update()
            ps.app.messageBox("Import complete - Models imported successfully!")
            
        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")
    
    def append_photos_from_project(self):
        """Bring a group of photos from a chunk of another project into the active
        chunk, with calibration, marker projections and masks (ms_append_gui)."""
        try:
            # The modules beside this script: found from ms_blocks, which the
            # menu has already imported, also when Run Script left no __file__.
            import importlib
            here = os.path.dirname(os.path.abspath(ms_blocks.__file__))
            if here not in sys.path:
                sys.path.insert(0, here)
            importlib.invalidate_caches()
            import ms_append_gui
            ms_append_gui.run_append_dialog()
        except Exception as e:
            ps.app.messageBox(f"Error - Append photos: {str(e)}")

    def _texturize_chunk_models(self, chunk, tex_size=4096, ratio=0.6, x_res_a_terra=1.26, max_area=None,
                                max_pages=None):
        models = self._extract_models(chunk)
        if not models:
            return 0

        textured_models = 0
        for model in models:
            if not self._activate_model(chunk, model):
                if textured_models > 0:
                    break

            current_model = chunk.model
            if not current_model:
                continue

            area_model = current_model.area()
            if area_model is None or area_model == 0.0:
                print(f"{chunk.label} has no area. Maybe the model isn't metric.")
                continue

            sim = ms_dd.simulate(area_model, x_res_a_terra, tex_size, ratio, max_pages)
            tex_num = sim["pages_cap"] if sim["over"] else sim["pages"]
            if hasattr(chunk, "meta"):
                chunk.meta["3dsc_dd"] = json.dumps({
                    "area_m2": round(area_model, 3), "pages": tex_num, "rule_pages": sim["pages"],
                    "texel_mm": round(sim["texel_cap"] if sim["over"] else sim["texel"], 4),
                    "texel_target_mm": x_res_a_terra, "atlas_px": tex_size, "uv_ratio": ratio,
                    "reference": "Demetrescu et al. 2026, Remote Sensing 18, 203, Eq. 1"})
            print(f"{chunk.label} has an area of {area_model} mq and needs {int(tex_num)} textures.")

            chunk.buildUV(mapping_mode=ps.GenericMapping, page_count=tex_num, texture_size=tex_size)
            chunk.buildTexture(
                blending_mode=ps.MosaicBlending,
                texture_size=tex_size,
                fill_holes=True,
                ghosting_filter=True
            )
            textured_models += 1

        if textured_models > 0:
            self._set_chunk_textured_flag(chunk, True)
        return textured_models

    def _texturize_chunk_list(self, chunks, max_area=None, progress_title="Texturizing"):
        processed = 0
        total = len(chunks)
        for idx, chunk in enumerate(chunks, start=1):
            if not chunk.model:
                continue
            processed += self._texturize_chunk_models(chunk, max_area=max_area)
            if total > 0:
                progress = (idx / total) * 100
                print(f"{progress_title}: {progress:.2f}% ({idx}/{total} chunks)")
            ps.app.update()
        return processed

    def prepare_or_flag_lod0(self):
        try:
            chunk = self.doc.chunk
            if chunk is None:
                ps.app.messageBox("Error - Select a chunk with a mesh model first.")
                return
            # A model may exist in chunk.models without being the active
            # chunk.model; accept it and activate it rather than rejecting.
            models = self._extract_models(chunk)
            if not models:
                ps.app.messageBox("Error - Select a chunk with a mesh model first.")
                return
            if not getattr(chunk, "model", None):
                self._activate_model(chunk, models[0])

            create_decimated_copy = ps.app.getBool(
                "STEP1 - Create an optional LOD0 decimated copy?\n"
                "(No = use current giant mesh as LOD0)\n"
                "The full-resolution mesh is always kept."
            )

            target_chunk = chunk
            mode = "original"
            info = "Current mesh flagged as LOD0 (full resolution kept)."

            # Always preserve the full-resolution mesh as the high-res source
            # (used by STEP4 for normal maps and kept for archival).
            if hasattr(chunk, "meta"):
                chunk.meta["3dsc_workflow_highres"] = "1"
            self.workflow_state["highres_source_chunk_key"] = self._chunk_key(chunk)

            if create_decimated_copy:
                # Show the real mesh stats so the target density is meaningful.
                # density here is faces per m² of 3D SURFACE (not footprint):
                # asking for more than the native density cannot decimate.
                src_faces, src_area, src_density = self._mesh_stats(chunk.model)
                default_density = str(int(src_density)) if src_density else "1000"
                prompt = "Target polygon density for LOD0 (polygons per m² of mesh surface):"
                if src_density:
                    prompt = (
                        f"Current mesh: {src_faces:,} faces over {src_area:,.0f} m² surface "
                        f"(~{src_density:,.0f} poly/m²).\n"
                        "Enter a LOWER value to reduce the mesh — a higher value cannot "
                        "add detail and will leave the mesh unchanged.\n\n"
                    ) + prompt

                density_str = ps.app.getString(prompt, default_density)
                if not density_str:
                    return
                target_density = float(str(density_str).replace(",", "."))
                if target_density <= 0:
                    raise Exception("Polygon density must be > 0.")

                # Decimate a COPY so the original full-resolution mesh is kept.
                target_chunk = chunk.copy()
                target_chunk.label = (chunk.label if chunk.label else "chunk") + "_LOD0"
                self.doc.chunk = target_chunk

                area_m2 = target_chunk.model.area() if target_chunk.model else 0
                cur_faces, _, _ = self._mesh_stats(target_chunk.model)
                target_faces = int(max(1000, area_m2 * target_density))

                if cur_faces and target_faces >= cur_faces:
                    # Decimation only ever removes faces; a target at/above the
                    # current count is a silent no-op in Metashape. Say so.
                    mode = "no_decimation_target_above_current"
                    info = (
                        f"No decimation performed: the requested ~{target_faces:,} faces "
                        f"({target_density:,.0f} poly/m²) is at or above the current "
                        f"{cur_faces:,} faces (~{src_density:,.0f} poly/m²).\n"
                        "Re-run STEP1 with a LOWER poly/m² to actually reduce LOD0.\n"
                        f"Full-resolution mesh preserved in chunk '{chunk.label}'."
                    )
                else:
                    try:
                        target_chunk.decimateModel(face_count=target_faces)
                        mode = "decimated"
                        info = (
                            f"LOD0 decimated copy created (~{target_faces:,} target faces, "
                            f"{target_density:,.0f} poly/m²).\n"
                            f"Full-resolution mesh preserved in chunk '{chunk.label}'."
                        )
                    except Exception as dec_err:
                        mode = "copy_no_decimation"
                        info = (
                            "LOD0 copy created, but decimation was not applied by Metashape API.\n"
                            f"Full-resolution mesh preserved in chunk '{chunk.label}'.\n"
                            f"Reason: {str(dec_err)}"
                        )

            if hasattr(target_chunk, "meta"):
                target_chunk.meta["3dsc_workflow_lod0"] = "1"
                target_chunk.meta["3dsc_workflow_lod0_mode"] = mode
            self.workflow_state["lod0_chunk_key"] = self._chunk_key(target_chunk)
            self.workflow_state["cut_source_chunk_key"] = self._chunk_key(target_chunk)
            self._set_chunk_textured_flag(target_chunk, False)

            ps.app.messageBox("STEP1 completed.\n" + info)

        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")

    def texturize_workflow_blocks(self):
        try:
            if not self.workflow_state.get("cut_blocks"):
                ps.app.messageBox("No workflow blocks found. Run STEP2 first.")
                return

            mode = self.workflow_state.get("cut_mode")
            chunks = []
            if mode == "multi_chunk":
                chunks = self._get_workflow_chunks()
            else:
                source_chunk = self._get_chunk_by_key(self.workflow_state.get("cut_source_chunk_key"))
                if source_chunk:
                    chunks = [source_chunk]

            if not chunks:
                ps.app.messageBox("No target chunks available for STEP3 texturing.")
                return

            processed = self._texturize_chunk_list(chunks, max_area=None, progress_title="Workflow STEP3")
            ps.app.update()
            ps.app.messageBox(f"STEP3 completed. Textured models: {processed}.")
        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")

    def generate_workflow_lods_experimental(self):
        try:
            if not self.workflow_state.get("cut_blocks"):
                ps.app.messageBox("No workflow blocks found. Run STEP2 first.")
                return

            ratio1_str = ps.app.getString("STEP4 - LOD1 decimation ratio (0..1):", "0.5")
            ratio2_str = ps.app.getString("STEP4 - LOD2 decimation ratio (0..1):", "0.25")
            if not ratio1_str or not ratio2_str:
                return

            ratio1 = float(str(ratio1_str).replace(",", "."))
            ratio2 = float(str(ratio2_str).replace(",", "."))
            if ratio1 <= 0 or ratio1 >= 1 or ratio2 <= 0 or ratio2 >= 1:
                raise Exception("LOD ratios must be between 0 and 1.")

            preserve_borders = ps.app.getBool("Try to preserve borders during decimation? (if supported)")
            build_normal_maps = ps.app.getBool("Build normal maps for generated LOD chunks? (if supported)")

            source_chunks = []
            mode = self.workflow_state.get("cut_mode")
            if mode == "multi_chunk":
                source_chunks = self._get_workflow_chunks()
            else:
                source_chunk = self._get_chunk_by_key(self.workflow_state.get("cut_source_chunk_key"))
                if source_chunk:
                    source_chunks = [source_chunk]

            if not source_chunks:
                raise Exception("No source chunk available for STEP4.")

            created = 0
            if mode == "models_chunk":
                for bc in self._get_workflow_chunks():
                    for m in [k for k in bc.models if (k.label or "").startswith("block_") and "_LOD" not in (k.label or "")]:
                        n0 = len(m.faces)
                        for lod_name, ratio in [("LOD1", ratio1), ("LOD2", ratio2)]:
                            before = {k.key for k in bc.models}
                            try:
                                bc.decimateModel(face_count=int(max(500, n0 * ratio)), model=m, replace_asset=False)
                            except Exception as dec_err:
                                print(f"LOD warning - {m.label}: {dec_err}")
                                continue
                            fresh = [k for k in bc.models if k.key not in before]
                            if fresh:
                                fresh[0].label = f"{m.label}_{lod_name}"
                                fresh[0].meta["3dsc_lod_of"] = m.label
                                created += 1
                            ps.app.update()
                        bc.model = m
                ps.app.messageBox(f"LODs made: {created} models (LOD1 {ratio1:g}, LOD2 {ratio2:g} of each block).")
                return
            for source_chunk in source_chunks:
                if not source_chunk.model:
                    continue

                # the LODs are fractions of the block's own faces (it is LOD0)
                base_faces = len(source_chunk.model.faces) if source_chunk.model else 100000

                for lod_name, ratio in [("LOD1", ratio1), ("LOD2", ratio2)]:
                    lod_chunk = source_chunk.copy()
                    lod_chunk.label = f"{source_chunk.label}_{lod_name}"
                    try:
                        face_count = int(max(500, base_faces * ratio))
                        try:
                            lod_chunk.decimateModel(face_count=face_count, preserve_boundary=preserve_borders)
                        except Exception:
                            lod_chunk.decimateModel(face_count=face_count)
                    except Exception as dec_err:
                        print(f"STEP4 warning - decimation failed for {lod_chunk.label}: {str(dec_err)}")

                    if build_normal_maps:
                        try:
                            lod_chunk.buildNormalMap()
                        except Exception as nm_err:
                            print(f"STEP4 warning - normal map not generated for {lod_chunk.label}: {str(nm_err)}")

                    self._set_chunk_textured_flag(lod_chunk, self._is_chunk_textured(source_chunk))
                    created += 1
                    ps.app.update()

            ps.app.messageBox(
                f"STEP4 completed (experimental). Created {created} LOD chunks.\n"
                "Normal map and border preservation depend on the Metashape API version."
            )

        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")

    def export_workflow_blocks_textured(self):
        try:
            if not self.workflow_state.get("cut_blocks"):
                ps.app.messageBox("No workflow blocks found. Run STEP2 first.")
                return

            panel = self._show_step7_options_dialog()
            if not panel:
                return

            export_folder = panel["export_folder"]
            use_shift = False
            shift_line = None
            crs = None
            shift = None

            use_shift = panel["use_shift"]
            if use_shift:
                if self.global_shift_vector is not None:
                    crs = self.global_shift_crs
                    shift = self.global_shift_vector
                    shift_line = self.global_shift_line
                else:
                    shift_file = panel.get("shift_file")
                    parsed = self._read_shift_parameters_from_file(shift_file)
                    crs = parsed["crs"]
                    shift = parsed["shift"]
                    shift_line = parsed["line"]

            save_textures = panel["save_textures"]
            mode = self.workflow_state.get("cut_mode")
            exported = 0
            operator = self._ask_operator()
            process_id = dtc_stamp_ms.new_process_id()
            stamp_results = []
            stamp_cache = {}
            export_params = {"Export/format": "obj", "Export/save_texture": bool(save_textures),
                             "Export/shift": dtc_stamp_ms.vector_list(shift) if (use_shift and shift is not None) else None,
                             "Export/crs": dtc_stamp_ms.crs_text(crs) if use_shift else None}

            if mode == "multi_chunk":
                chunks = self._get_workflow_chunks()
                if not chunks:
                    ps.app.messageBox("No workflow chunks found. Run STEP2 again.")
                    return

                for chunk in chunks:
                    if not self._is_chunk_textured(chunk):
                        raise Exception(f"Chunk '{chunk.label}' is not marked as textured. Run STEP3 first.")
                    if not chunk.model:
                        continue

                    out_name = (chunk.label if chunk.label else "block") + ".obj"
                    out_path = os.path.join(export_folder, out_name)
                    kwargs = dict(
                        path=out_path,
                        format=ps.ModelFormat.ModelFormatOBJ,
                        save_texture=save_textures,
                        save_uv=save_textures,
                        save_normals=True,
                        save_colors=True
                    )
                    if use_shift and shift is not None:
                        kwargs["shift"] = shift
                        if crs is not None:
                            kwargs["crs"] = crs
                    chunk.exportModel(**kwargs)
                    exported += 1
                    stamp_results += self._stamp(
                        chunk, chunk.model, self._export_files(out_path), operator,
                        process_id=process_id, parameters=export_params,
                        georef_export=bool(use_shift), label=chunk.label, cache=stamp_cache)
            else:
                chunk = self._get_chunk_by_key(self.workflow_state.get("cut_source_chunk_key"))
                if chunk is None:
                    chunk = self.doc.chunk
                if chunk is None or not chunk.model:
                    raise Exception("No chunk/model available for STEP5 export.")
                if not self._is_chunk_textured(chunk):
                    raise Exception("Current workflow chunk is not marked as textured. Run STEP3 first.")

                models = self._extract_models(chunk)
                block_defs = self.workflow_state.get("cut_blocks", [])

                if len(models) <= 1:
                    out_path = os.path.join(export_folder, "workflow_block.obj")
                    kwargs = dict(
                        path=out_path,
                        format=ps.ModelFormat.ModelFormatOBJ,
                        save_texture=save_textures,
                        save_uv=save_textures,
                        save_normals=True,
                        save_colors=True
                    )
                    if use_shift and shift is not None:
                        kwargs["shift"] = shift
                        if crs is not None:
                            kwargs["crs"] = crs
                    chunk.exportModel(**kwargs)
                    exported = 1
                    stamp_results += self._stamp(
                        chunk, chunk.model, self._export_files(out_path), operator,
                        process_id=process_id, parameters=export_params,
                        georef_export=bool(use_shift), cache=stamp_cache)
                else:
                    for idx, model in enumerate(models):
                        if not self._activate_model(chunk, model):
                            continue
                        block_name = model.label or f"block_{idx:04d}"
                        if not model.label and idx < len(block_defs):
                            block_name = block_defs[idx]["name"]
                        out_path = os.path.join(export_folder, block_name + ".obj")
                        kwargs = dict(
                            path=out_path,
                            format=ps.ModelFormat.ModelFormatOBJ,
                            save_texture=save_textures,
                            save_uv=save_textures,
                            save_normals=True,
                            save_colors=True
                        )
                        if use_shift and shift is not None:
                            kwargs["shift"] = shift
                            if crs is not None:
                                kwargs["crs"] = crs
                        chunk.exportModel(**kwargs)
                        exported += 1
                        stamp_results += self._stamp(
                            chunk, model, self._export_files(out_path), operator,
                            process_id=process_id, parameters=export_params,
                            georef_export=bool(use_shift), label=block_name, cache=stamp_cache)

            if use_shift and shift_line:
                with open(os.path.join(export_folder, "shift.txt"), "w", encoding="utf-8") as f:
                    f.write(shift_line + "\n")

            ps.app.messageBox(f"STEP5 completed. Exported meshes: {exported}.\n"
                              + dtc_stamp_ms.report_line(stamp_results))
        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")
    
    def export_multiple_models(self):
        try:
            # Get export folder
            path_folder = ps.app.getExistingDirectory("Specify destination folder for 3D models: ")
            if not path_folder:
                return
            path_folder += "/"
            
            # Check for shift file
            file_list = os.listdir(path_folder)
            coord_shift = False
            projection_coor = None
            
            for ob_txt in file_list:
                if ob_txt.endswith(".txt"):
                    file_txt_fullpath = str(path_folder + ob_txt)
                    print(file_txt_fullpath)
                    
                    with open(file_txt_fullpath, 'r', encoding='utf-8') as f:
                        first = f.readline()
                        parts = first.split()
                        crs_string = parts[0]
                        shift_coor_x = float(parts[1])
                        shift_coor_y = float(parts[2])
                        shift_coor_z = float(parts[3])
                        shift_coor = ps.Vector([shift_coor_x, shift_coor_y, shift_coor_z])
                        coord_shift = True
                        
                        # Handle CRS: only set if not LOCAL or NONE
                        if crs_string.upper() not in ['LOCAL', 'LOCAL_CS', 'NONE']:
                            projection_coor = crs_string
                        
                        print(shift_coor_x)
                        if projection_coor:
                            print(f"Using CRS: {projection_coor}")
                        else:
                            print("Using local coordinates (no CRS)")

            if not coord_shift and self.global_shift_vector is not None:
                coord_shift = True
                shift_coor = self.global_shift_vector
                projection_coor = self.global_shift_crs_string if self.global_shift_crs else None
                print("Using global shift from GUI settings.")
            
            # Export each chunk
            number = 0
            operator = self._ask_operator()
            process_id = dtc_stamp_ms.new_process_id()
            stamp_results = []
            stamp_cache = {}
            for i in range(0, len(self.doc.chunks)):
                chunk = self.doc.chunks[i]
                
                if chunk.model:
                    ob_fullpath = str(path_folder + chunk.label + "_mt.obj")
                    
                    if coord_shift:
                        if projection_coor:
                            # Export with CRS and shift
                            self.doc.chunks[i].exportModel(
                                path=ob_fullpath, 
                                binary=True, 
                                precision=6, 
                                texture_format=ps.ImageFormat.ImageFormatJPEG, 
                                save_texture=True, 
                                save_uv=True, 
                                save_normals=True, 
                                save_colors=True, 
                                save_cameras=False, 
                                save_markers=False, 
                                save_udim=False, 
                                save_alpha=False, 
                                strip_extensions=False, 
                                raster_transform=ps.RasterTransformNone, 
                                colors_rgb_8bit=True, 
                                format=ps.ModelFormat.ModelFormatOBJ,
                                crs=ps.CoordinateSystem(projection_coor), 
                                shift=shift_coor
                            )
                        else:
                            # Export with shift only (local coordinates)
                            self.doc.chunks[i].exportModel(
                                path=ob_fullpath, 
                                binary=True, 
                                precision=6, 
                                texture_format=ps.ImageFormat.ImageFormatJPEG, 
                                save_texture=True, 
                                save_uv=True, 
                                save_normals=True, 
                                save_colors=True, 
                                save_cameras=False, 
                                save_markers=False, 
                                save_udim=False, 
                                save_alpha=False, 
                                strip_extensions=False, 
                                raster_transform=ps.RasterTransformNone, 
                                colors_rgb_8bit=True, 
                                format=ps.ModelFormat.ModelFormatOBJ,
                                shift=shift_coor
                            )
                    else:
                        self.doc.chunks[i].exportModel(
                            path=ob_fullpath, 
                            binary=True, 
                            precision=6, 
                            texture_format=ps.ImageFormat.ImageFormatJPEG, 
                            save_texture=True, 
                            save_uv=True, 
                            save_normals=True, 
                            save_colors=True, 
                            save_cameras=False, 
                            save_markers=False, 
                            save_udim=False, 
                            save_alpha=False, 
                            strip_extensions=False, 
                            raster_transform=ps.RasterTransformNone, 
                            colors_rgb_8bit=True, 
                            format=ps.ModelFormat.ModelFormatOBJ
                        )
                    stamp_results += self._stamp(
                        chunk, chunk.model, self._export_files(ob_fullpath), operator,
                        process_id=process_id, georef_export=coord_shift, label=chunk.label,
                        parameters={"Export/format": "obj",
                                    "Export/shift": dtc_stamp_ms.vector_list(shift_coor) if coord_shift else None,
                                    "Export/crs": projection_coor},
                        cache=stamp_cache)
                
                number += 1
            
            ps.app.update()
            ps.app.messageBox(f"Success - Exported {number} models successfully.\n"
                              + dtc_stamp_ms.report_line(stamp_results))
            
        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")
    
    def export_single_model_with_shift(self):
        try:
            # Check if there's an active chunk
            if self.doc.chunk is None:
                ps.app.messageBox("Error - No active chunk found.")
                return
            
            chunk = self.doc.chunk
            
            crs, shift_coor, _ = self._resolve_shift_for_operation(
                "Export Single Model with Shift", ask_if_missing=True
            )
            
            # Ask for destination folder and filename
            save_folder = ps.app.getExistingDirectory("Specify the folder to save the OBJ file:")
            if not save_folder:
                return
            
            file_name = ps.app.getString("Enter the name of the OBJ file:", chunk.label)
            if not file_name:
                file_name = chunk.label
            
            save_path = os.path.join(save_folder, file_name + ".obj")
            operator = self._ask_operator()
            
            # Export the model
            if crs and shift_coor:
                chunk.exportModel(path=save_path, format=ps.ModelFormat.ModelFormatOBJ, crs=crs, shift=shift_coor)
            elif shift_coor:
                chunk.exportModel(path=save_path, format=ps.ModelFormat.ModelFormatOBJ, shift=shift_coor)
            else:
                chunk.exportModel(path=save_path, format=ps.ModelFormat.ModelFormatOBJ)
            stamp_results = self._stamp(
                chunk, chunk.model, self._export_files(save_path), operator,
                georef_export=bool(shift_coor), label=file_name,
                parameters={"Export/format": "obj",
                            "Export/shift": dtc_stamp_ms.vector_list(shift_coor) if shift_coor else None,
                            "Export/crs": dtc_stamp_ms.crs_text(crs)})
            
            ps.app.messageBox(f"Success - Model exported successfully to {save_path}.\n"
                              + dtc_stamp_ms.report_line(stamp_results))
            
        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")
    
    def export_tiled_models(self):
        try:
            # Get export folder
            export_folder = ps.app.getExistingDirectory("Specify destination folder for 3D models: ")
            if not export_folder:
                return
            export_folder += "/"

            _, shift, shift_line = self._resolve_shift_for_operation(
                "Export Tiled Models", ask_if_missing=True
            )
            
            # Get active chunk
            chunk = self.doc.chunk
            
            # Set export parameters
            tile_format = ps.TileFormat.TileFormatOBJ
            texture_format = ps.ImageFormat.ImageFormatPNG
            
            # Check for tiled model
            tiled_model = chunk.tiled_model
            if not tiled_model:
                ps.app.messageBox("Error - No tiled model found in the active chunk.")
                return
            
            # Create export folder if it doesn't exist
            if not os.path.exists(export_folder):
                os.makedirs(export_folder)
            
            # Export tiles
            operator = self._ask_operator()
            process_id = dtc_stamp_ms.new_process_id()
            stamp_results = []
            stamp_cache = {}
            for tile_index in range(len(tiled_model.tiles)):
                tile_name = f"tile_{tile_index:04d}"
                obj_path = os.path.join(export_folder, f"{tile_name}.obj")
                png_path = os.path.join(export_folder, f"{tile_name}.png")
                
                if shift:
                    tiled_model.exportTile(tile_index, obj_path, tile_format, translation=shift)
                else:
                    tiled_model.exportTile(tile_index, obj_path, tile_format)
                
                # Export the texture
                tiled_model.exportTileTexture(tile_index, png_path, texture_format)
                stamp_results += self._stamp(
                    chunk, tiled_model, [p for p in (obj_path, png_path) if os.path.exists(p)],
                    operator, process_id=process_id, georef_export=bool(shift),
                    label=tile_name, cache=stamp_cache,
                    parameters={"ExportTile/index": tile_index,
                                "ExportTile/translation": dtc_stamp_ms.vector_list(shift) if shift else None})

            if shift_line:
                with open(os.path.join(export_folder, "shift.txt"), "w", encoding="utf-8") as f:
                    f.write(shift_line + "\n")
            
            ps.app.messageBox(f"Success - Exported {len(tiled_model.tiles)} tiled models successfully.\n"
                              + dtc_stamp_ms.report_line(stamp_results))
            
        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")

    def cut_giant_mesh_into_blocks_with_shift(self):
        try:
            if self.doc.chunk is None:
                ps.app.messageBox("Error - No active chunk found.")
                return

            chunk = self.doc.chunk
            models = self._extract_models(chunk)
            if not models:
                ps.app.messageBox("Error - No mesh model found in the active chunk.")
                return
            if not getattr(chunk, "model", None):
                self._activate_model(chunk, models[0])

            panel = self._show_step3_options_dialog()
            if not panel:
                return

            run_step2_now = panel["run_step2_now"]
            if run_step2_now:
                self.prepare_or_flag_lod0()
                lod_chunk = self._get_chunk_by_key(self.workflow_state.get("lod0_chunk_key"))
                if lod_chunk and lod_chunk.model:
                    chunk = lod_chunk
                    self.doc.chunk = chunk

            operator = self._ask_operator()
            report = self.run_step2(self.doc, chunk, panel, operator)
            ps.app.messageBox(report["message"])

        except ms_blocks.BlocksRejected as e:
            ps.app.messageBox(
                "STEP2 stopped: the blocks are not distinct pieces of the model.\n\n"
                + "\n".join(p[:400] for p in e.problems)
            )
        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")

    def run_step2(self, doc, chunk, panel, operator):
        """STEP2 without dialogs: the Block Model, the check, the small tiles,
        the grid names, the chunks, the stamps. → a report (dict, with the
        ``message`` the menu shows). Raises ``ms_blocks.BlocksRejected`` when
        the blocks are not distinct pieces of the model."""
        if (panel.get("grid") or {}).get("mode") == "project" and self.project_grid():
            panel["target_area_m2"] = float(self.project_grid()["side"]) ** 2
        try:
            self.clear_grid_preview(chunk)
        except Exception:
            pass
        target_area_m2 = panel["target_area_m2"]
        output_multi_chunks = panel["output_multi_chunks"]
        export_root = panel["export_root"]
        min_faces = int(panel.get("min_faces", ms_blocks.DEFAULT_MIN_FACES) or 0)
        small_mode = panel.get("small_mode", ms_blocks.SMALL_MERGE)
        side = max(0.1, math.sqrt(max(0.01, target_area_m2)))

        chunk_label = chunk.label if chunk.label else "active_chunk"
        safe_label = "".join(c if c.isalnum() or c in ('_', '-', '.') else '_' for c in chunk_label)
        blocks_folder = os.path.join(export_root, safe_label + "_workflow_blocks")
        os.makedirs(blocks_folder, exist_ok=True)

        source_model = chunk.model
        source_faces, _, _ = self._mesh_stats(source_model)
        keys_before = {m.key for m in self._extract_models(chunk)}

        # Native spatial cut: Metashape Block Model builds the mesh already
        # split into separate spatial blocks (split happens at build time,
        # not by clipping an existing mesh). Mirrors the 3DSC Blender
        # "Cutter". blocks_size = sqrt(area) in metres.
        cut_blocks, produced, source_used = self._build_block_model_and_collect(
            chunk, target_area_m2, blocks_folder, panel.get("grid")
        )
        grid_info = getattr(self, "_last_grid", None) or {"mode": "north"}
        grid_crs = ps.CoordinateSystem(grid_info["wkt"]) if grid_info.get("wkt") else None
        if grid_crs is not None:
            with open(os.path.join(blocks_folder, "grid_crs.wkt"), "w", encoding="utf-8") as fh:
                fh.write(grid_info["wkt"] + "\n")
            new_models = {m.label: m for m in self._extract_models(chunk)
                          if m.key not in keys_before and m.label}
            self._georef_rotated_blocks(chunk, source_model, [b["obj_path"] for b in cut_blocks],
                                        blocks_folder, new_models)
            if panel.get("save_grid") and grid_info.get("mode") != "project":
                self.save_project_grid(grid_info, side, chunk)
        if not cut_blocks:
            sample = "\n".join(os.path.basename(p) for p in produced[:30]) or "(no files)"
            raise Exception(
                "Block model built (source: %s) but no .obj/.ply block meshes "
                "were found. Files produced:\n%s\n\nFolder: %s"
                % (source_used, sample, blocks_folder)
            )
        ps.app.update()
        # the block models Metashape added to the chunk, by their tile name
        tile_models = {m.label: m for m in self._extract_models(chunk)
                       if m.key not in keys_before and m.label}

        # 1. the check: distinct pieces, or stop and name the files
        names = [os.path.basename(b["obj_path"]) for b in cut_blocks
                 if b["obj_path"].lower().endswith(".obj")]
        stats = ms_blocks.folder_stats(blocks_folder, names)
        ms_blocks.assert_blocks(stats, source_faces)
        produced_count = len(stats)

        # 2. the grid names, from each tile's centre in the grid of the cut —
        # on the tiles AS CUT: a tile that absorbs a small neighbour keeps the
        # name of its own cell (its grown bbox may centre in the next one)
        srs_origin = ms_blocks.read_srs_origin(blocks_folder)
        mapping = {s["name"]: s["name"] for s in stats}
        if panel.get("grid_naming", True) and grid_crs is not None:
            # rotated grid: the cut's own cell «Tile i-j», counted from 1
            # counted from the grid origin: with the project grid, the same cell
            # has the same name in every epoch
            cells = {s["name"]: ms_grid.cell_of(s["name"]) for s in stats}
            if all(cells.values()):
                i0 = min(0, min(c[0] for c in cells.values()))
                j0 = min(0, min(c[1] for c in cells.values()))
                mapping = {n: ms_blocks.grid_name((c[0] - i0 + 1, c[1] - j0 + 1)) for n, c in cells.items()}
        elif panel.get("grid_naming", True):
            origin = ms_blocks.cut_grid_origin(stats, side, srs_origin)
            mapping = ms_blocks.grid_names(stats, side, origin)

        # 3. the small tiles: merged into a neighbour, or flagged
        small_plan = {"small": [], "merges": [], "flagged": []}
        merge_lines = []
        if min_faces > 0:
            small_plan = ms_blocks.plan_small_tiles(stats, min_faces, small_mode)
            if small_plan["merges"]:
                merge_lines = ms_blocks.apply_small_tiles(blocks_folder, small_plan)
                gone = {s for s, _ in small_plan["merges"]}
                stats = ms_blocks.folder_stats(
                    blocks_folder, [os.path.basename(s["path"]) for s in stats
                                    if s["name"] not in gone])
        absorbed_into = {}
        for small, into in small_plan["merges"]:
            absorbed_into.setdefault(into, []).append(small)

        if panel.get("grid_naming", True):
            ms_blocks.rename_tiles(blocks_folder, {s["name"]: mapping[s["name"]] for s in stats})
            for old, new in mapping.items():
                model = tile_models.get(old)
                if model is not None:
                    try:
                        model.label = new
                    except Exception:
                        pass

        cut_blocks = []
        for idx, s in enumerate(sorted(stats, key=lambda s: mapping[s["name"]])):
            new = mapping[s["name"]]
            cut_blocks.append({
                "index": idx,
                "name": new,
                "source_name": s["name"],
                "obj_path": os.path.join(blocks_folder, new + ".obj"),
                "png_path": None,
                "faces": s["faces"],
                "merged_from": sorted(absorbed_into.get(s["name"], [])),
            })

        generated_chunk_keys = []
        if panel.get("output") == "models":
            master = self._get_chunk_by_key(panel.get("master_key")) if panel.get("master_key") else None
            if master is not None:
                bc = self._copy_master(master)
            else:
                bc = chunk.copy()
                self._prepare_lightweight_chunk(bc)
            bc.label = f"{safe_label}_blocks"
            bc.meta["3dsc_blocks_of"] = chunk.label or ""
            for block in cut_blocks:
                before = {m.key for m in bc.models}
                self._import_block(bc, block["obj_path"], srs_origin)
                fresh = [m for m in bc.models if m.key not in before]
                if fresh:
                    fresh[0].label = block["name"]
                    fresh[0].meta["3dsc_block"] = block["name"]
                    fresh[0].meta["3dsc_tile_source_name"] = block["source_name"]
                    fresh[0].meta["3dsc_faces"] = str(block["faces"])
                    try:
                        fresh[0].meta["3dsc_area_m2"] = "%.3f" % fresh[0].area()
                    except Exception:
                        pass
                ps.app.update()
            self._set_chunk_textured_flag(bc, False)
            self.workflow_state["cut_mode"] = "models_chunk"
            self.workflow_state["generated_chunk_keys"] = [self._chunk_key(bc)]
            output_multi_chunks = False
            self.workflow_state["cut_blocks"] = cut_blocks
            self.workflow_state["cut_folder"] = blocks_folder
            self.workflow_state["cut_source_chunk_key"] = self._chunk_key(bc)
        elif output_multi_chunks:
            # Re-import each block as its own chunk (copies the source chunk
            # so cameras/depth maps travel with it for STEP3 texturing).
            master = self._get_chunk_by_key(panel.get("master_key")) if panel.get("master_key") else None
            for block in cut_blocks:
                if master is not None:
                    new_chunk = self._copy_master(master)
                else:
                    new_chunk = chunk.copy()
                    self._prepare_lightweight_chunk(new_chunk)
                new_chunk.label = f"{safe_label}_{block['name']}"
                self._import_block(new_chunk, block["obj_path"], srs_origin)
                self._set_chunk_textured_flag(new_chunk, False)
                if hasattr(new_chunk, "meta"):
                    new_chunk.meta["3dsc_workflow_block_name"] = block["name"]
                    new_chunk.meta["3dsc_tile_source_name"] = block["source_name"]
                generated_chunk_keys.append(self._chunk_key(new_chunk))
                ps.app.update()
            self.workflow_state["cut_mode"] = "multi_chunk"
            self.workflow_state["generated_chunk_keys"] = generated_chunk_keys
        else:
            # Files-only: leave the block meshes on disk (verify them, or
            # clean/segment further in Blender), no chunk import.
            self.workflow_state["cut_mode"] = "files_only"
            self.workflow_state["generated_chunk_keys"] = []

        if panel.get("output") != "models":
            self.workflow_state["cut_blocks"] = cut_blocks
            self.workflow_state["cut_folder"] = blocks_folder
            self.workflow_state["cut_source_chunk_key"] = self._chunk_key(chunk)

        # 4. the stamps: one act, one process_id for every file of the cut
        process_id = dtc_stamp_ms.new_process_id()
        technique = "Metashape Block Model, blocks_size %s m" % ("%.2f" % side).replace(".", ",")
        common = {
            "BuildModel/split_in_blocks": True,
            "BuildModel/blocks_size": float(side),
            "BuildModel/export_blocks": True,
            "BuildModel/build_texture": False,
            "BuildModel/replace_asset": False,
            "BuildModel/source_data": source_used,
            "3DSC/target_area_m2": float(target_area_m2),
            "3DSC/min_faces": min_faces,
            "3DSC/small_tiles": small_mode if min_faces > 0 else "off",
            "3DSC/grid_naming": bool(panel.get("grid_naming", True)),
            "3DSC/grid": grid_info.get("mode", "north"),
        }
        if grid_crs is not None:
            common["3DSC/grid_bearing_deg"] = round(grid_info["bearing"], 4)
            common["BuildModel/blocks_origin"] = grid_info["origin"]
            common["BuildModel/blocks_crs"] = "local oblique Mercator, see grid_crs.wkt"
        if srs_origin:
            common["metadata.xml/SRSOrigin"] = list(srs_origin)
        cache = {}
        results = []
        flagged = set(small_plan["flagged"])
        for block in cut_blocks:
            params = dict(common)
            params["3DSC/tile_source_name"] = block["source_name"]
            if block["merged_from"]:
                params["3DSC/merged_from"] = block["merged_from"]
            if block["source_name"] in flagged:
                params["3DSC/under_min_faces"] = True
            tile_model = tile_models.get(block["name"]) or tile_models.get(block["source_name"])
            sources = [tile_models[n] for n in block["merged_from"] if n in tile_models]
            if source_model is not None:
                sources.append(source_model)
            tls = os.path.join(blocks_folder, block["name"] + ".tls")
            results += self._stamp(
                chunk, tile_model if tile_model is not None else source_model,
                [block["obj_path"], tls if os.path.exists(tls) else None], operator,
                doc=doc, process_id=process_id, dtc_kind=dtc_stamp_ms.KIND_TILING,
                technique=technique, parameters=params,
                sources=sources if tile_model is not None else sources[:-1],
                label=block["name"], measures={block["obj_path"]: {"faces": block["faces"]}},
                cache=cache)
        meta_xml = os.path.join(blocks_folder, "metadata.xml")
        if os.path.exists(meta_xml):
            results += self._stamp(
                chunk, source_model, [meta_xml], operator, doc=doc, process_id=process_id,
                dtc_kind=dtc_stamp_ms.KIND_TILING, technique=technique, parameters=common,
                label="metadata.xml of the blocks", cache=cache)

        # the block models Metashape left in the source chunk: once the blocks
        # live in their own chunk(s), they would only be duplicates
        if panel.get("output") in ("models", "chunks") or output_multi_chunks:
            gone = [m for m in tile_models.values() if m is not None]
            for m in list(chunk.models):
                if m.label in mapping.values() and m not in gone:
                    gone.append(m)
            for m in gone:
                try:
                    chunk.remove(m)
                except Exception:
                    pass
            if source_model is not None:
                try:
                    chunk.model = source_model
                except Exception:
                    pass
        if panel.get("output") == "models":
            tail = "The blocks are models of the chunk «%s_blocks». Next: Texturing." % safe_label
        elif output_multi_chunks:
            tail = "Next: run STEP3 texturing, then STEP5 export."
        else:
            tail = ("Open a few block files to confirm they are distinct spatial "
                    "pieces, then re-run with 'one chunk per block' (or clean them "
                    "in Blender first).")
        small_line = ""
        if min_faces > 0:
            small_line = "Tiles under %d faces: %d (%d merged, %d flagged)\n" % (
                min_faces, len(small_plan["small"]), len(small_plan["merges"]),
                len(small_plan["flagged"]))
        grid_line = ""
        if grid_crs is not None:
            grid_line = "Grid turned by %.2f° (north grid would need %d cells, this one %d).\n" % (
                grid_info["bearing"], grid_info["north_cells"], grid_info["cells"])
        message = grid_line + (
            "STEP2 completed (Block Model, source: %s).\n"
            "Blocks produced: %d, checked distinct; kept: %d\n%s"
            "Output mode: %s\n"
            "Folder: %s\n%s\n\n%s"
            % (
                source_used,
                produced_count,
                len(cut_blocks),
                small_line,
                {"models": "the blocks as models of one chunk", "chunks": "one chunk per block"}.get(
                    panel.get("output"), "one chunk per block" if output_multi_chunks else "files only (no import)"),
                blocks_folder,
                dtc_stamp_ms.report_line(results),
                tail,
            )
        )
        return {
            "message": message, "folder": blocks_folder, "source_used": source_used,
            "source_faces": source_faces, "blocks_size": side, "produced": produced_count,
            "blocks": cut_blocks, "small_plan": small_plan, "merge_lines": merge_lines,
            "mapping": mapping, "process_id": process_id, "stamps": results,
            "tile_models": {k: m.key for k, m in tile_models.items()},
        }

    # ── the panels (ms_panels) ─────────────────────────────────────────────

    def _panels(self):
        import importlib
        here = os.path.dirname(os.path.abspath(ms_blocks.__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        importlib.invalidate_caches()
        import ms_panels
        return ms_panels

    def _need_doc(self):
        if self.doc is None or not len(self.doc.chunks):
            ps.app.messageBox("Open a project with at least one chunk first.")
            return False
        return True

    DOCS_URL = "https://docs.extendedmatrix.org/projects/3D-survey-collection/en/latest/reference/tools/metashape-tool.html"
    TOOL_URL = "https://www.extendedmatrix.org/tools/3dsc-metashape/"

    def about_panel(self):
        self._panels().about(__version__)

    def open_docs(self):
        try:
            from PySide2 import QtCore, QtGui
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(self.DOCS_URL))
        except Exception:
            ps.app.messageBox("Documentation: " + self.DOCS_URL)

    def operator_panel(self):
        P = self._panels()
        P.OperatorDialog(self, P._parent()).exec_()
        self.init_gui()

    def shift_panel(self):
        P = self._panels()
        P.ShiftDialog(self, P._parent()).exec_()
        self.init_gui()

    # master: photos + tie points only, made once, copied for every model
    def create_master(self, chunk):
        m = self._copy_master(chunk, keep_cameras=True)
        m.label = (chunk.label or "chunk") + "_MASTER"
        m.meta["3dsc_master"] = "1"
        m.meta["3dsc_master_from"] = chunk.label or ""
        return m

    def _copy_master(self, chunk, keep_cameras=True):
        """A copy of ``chunk`` with its photos and tie points only."""
        DS = ps.DataSource
        try:
            new_chunk = chunk.copy(items=[DS.TiePointsData])
        except Exception:
            new_chunk = chunk.copy()
        self._prepare_lightweight_chunk(new_chunk)
        try:
            new_chunk.meta["3dsc_master"] = "0"
        except Exception:
            pass
        return new_chunk

    def import_panel(self):
        if self.doc is None:
            return
        P = self._panels()
        dlg = P.ImportDialog(self, P._parent())
        if dlg.exec_() != P.QtWidgets.QDialog.Accepted:
            return
        o = dlg.options()
        if not o["paths"]:
            return
        try:
            rep = self.import_models(o["paths"], o["use_shift"], o["one_chunk"], o["master_key"])
        except Exception as e:
            ps.app.messageBox(f"Import stopped: {e}")
            return
        ps.app.messageBox(rep)

    def import_models(self, paths, use_shift=True, one_chunk=False, master_key=None):
        """Import models: one chunk per model copied from the master, or all in one."""
        self.restore_shift_from_doc()
        shift = self.global_shift_vector if use_shift else None
        crs = self.global_shift_crs if use_shift else None
        master = self._get_chunk_by_key(master_key) if master_key is not None else None

        def target(label):
            if master is not None:
                c = self._copy_master(master)
            else:
                c = self.doc.addChunk()
            c.label = label
            return c

        def load(c, path):
            kw = dict(path=path, format=self._model_format_for(path))
            if shift is not None:
                kw["shift"] = shift
                if crs is not None:
                    kw["crs"] = crs
            c.importModel(**kw)
            m = c.model
            if m is not None:
                m.label = os.path.splitext(os.path.basename(path))[0]
            c.meta["3dsc_imported_from"] = path

        done = []
        if one_chunk:
            c = target("Imported_%d_models" % len(paths))
            for path in paths:
                load(c, path)
                done.append(path)
                ps.app.update()
        else:
            for path in paths:
                c = target(os.path.splitext(os.path.basename(path))[0])
                load(c, path)
                self._set_chunk_textured_flag(c, False)
                done.append(path)
                ps.app.update()
        return ("%d models imported %s%s.\n%s" % (
            len(done), "in one chunk" if one_chunk else "one chunk each",
            " from the master «%s»" % master.label if master is not None else "",
            "Shift applied: " + self.get_global_shift_preview() if shift is not None else "No shift."))

    # masters: geometric (the source), texturable, tileable
    def masters_panel(self):
        if not self._need_doc():
            return
        P = self._panels()
        dlg = P.MastersDialog(self, P._parent())
        if dlg.exec_() != P.QtWidgets.QDialog.Accepted:
            return
        o = dlg.options()
        if not o["plan"]:
            return
        try:
            ps.app.messageBox(self.make_masters(o))
        except Exception as e:
            ps.app.messageBox(f"Masters stopped: {e}")

    def make_masters(self, o):
        """Make what the inventory says is missing: ``o["plan"]`` from ms_masters."""
        chunk = self._get_chunk_by_key(o["chunk_key"])
        models = {m.key: m for m in chunk.models}
        lines = []
        for step in o["plan"]:
            src = models.get(step["from"])
            if src is None:
                continue
            for m in list(chunk.models):     # a re-run replaces the old master of this level
                if self._meta_get(m, "3dsc_master_level") == step["level"]:
                    chunk.remove(m)
            before = {k.key for k in chunk.models}
            chunk.model = src
            chunk.decimateModel(face_count=int(step["faces"]), model=src, replace_asset=False)
            fresh = [k for k in chunk.models if k.key not in before]
            m = fresh[0] if fresh else chunk.model
            m.label = "M_%s_%d" % (step["level"], step["density"])
            m.meta["3dsc_master_level"] = step["level"]
            m.meta["3dsc_density"] = str(step["density"])
            m.meta["3dsc_master_source"] = src.label or "model %d" % (src.key + 1)
            m.meta["3dsc_faces"] = str(len(m.faces))
            lines.append("%s: %s faces from «%s»" % (m.label, m.meta["3dsc_faces"],
                                                     m.meta["3dsc_master_source"]))
            ps.app.update()
            chunk.model = src
        return "Masters of «%s»:\n%s" % (chunk.label, "\n".join(lines) or "nothing made")

    def blocks_panel(self):
        if not self._need_doc():
            return
        P = self._panels()
        dlg = P.BlocksDialog(self, P._parent())
        if dlg.exec_() != P.QtWidgets.QDialog.Accepted:
            return
        panel = dlg.options()
        chunk = self._get_chunk_by_key(panel["chunk_key"])
        try:
            operator = self._ask_operator()
            report = self.run_step2(self.doc, chunk, panel, operator)
            ps.app.messageBox(report["message"])
        except ms_blocks.BlocksRejected as e:
            ps.app.messageBox("Blocks stopped: they are not distinct pieces of the model.\n\n"
                              + "\n".join(p[:400] for p in e.problems))
        except Exception as e:
            ps.app.messageBox(f"Blocks stopped: {e}")

    # texturing with the Demetrescu-D'Annibale rule
    def texturing_panel(self):
        if not self._need_doc():
            return
        P = self._panels()
        dlg = P.TexturingDialog(self, P._parent())
        if dlg.exec_() != P.QtWidgets.QDialog.Accepted:
            return
        o = dlg.options()
        done, lines = 0, []
        for ck, mk in o["targets"]:
            c = self._get_chunk_by_key(ck)
            m = [k for k in (c.models if c else []) if k.key == mk]
            if not m:
                continue
            res = self.texture_model(c, m[0], o["texel"], o["atlas"], o["ratio"], o["cap"])
            lines.append("%s · %s: %d pages, texel %.2f mm" % (c.label, m[0].label or m[0].key,
                                                                res["pages"], res["texel"]))
            done += 1
            ps.app.update()
        ps.app.messageBox("Textured models: %d (texel %.2f mm, atlas %d, UV ratio %.2f%s).\n\n%s" % (
            done, o["texel"], o["atlas"], o["ratio"], ", max %d pages" % o["cap"] if o["cap"] else "",
            "\n".join(lines[:30])))

    def texture_model(self, chunk, model, texel=ms_dd.TEXEL_MM, atlas=ms_dd.ATLAS_PX,
                      ratio=ms_dd.UV_RATIO, cap=None):
        """One model of a chunk, textured with the D-D rule: it becomes the
        active model, gets its own UV pages and texture; the others keep theirs."""
        chunk.model = model
        area = model.area()
        sim = ms_dd.simulate(area, texel, atlas, ratio, cap)
        pages = sim["pages_cap"] if sim["over"] else sim["pages"]
        got = sim["texel_cap"] if sim["over"] else sim["texel"]
        chunk.buildUV(mapping_mode=ps.GenericMapping, page_count=pages, texture_size=atlas)
        chunk.buildTexture(blending_mode=ps.MosaicBlending, texture_size=atlas,
                           fill_holes=True, ghosting_filter=True)
        model.meta["3dsc_dd"] = json.dumps({
            "area_m2": round(area, 3), "pages": pages, "rule_pages": sim["pages"],
            "texel_mm": round(got, 4), "texel_target_mm": texel, "atlas_px": atlas, "uv_ratio": ratio,
            "reference": "Demetrescu et al. 2026, Remote Sensing 18, 203, Eq. 1"})
        model.meta["3dsc_area_m2"] = "%.3f" % area
        self._set_chunk_textured_flag(chunk, True)
        return {"pages": pages, "texel": got}

    def save_subset(self, chunks, path):
        """A new project holding only ``chunks``; the open one is unchanged."""
        new_doc = ps.Document()
        new_doc.append(self.doc, chunks=list(chunks))
        try:
            for k in (self.SHIFT_META_LINE, self.SHIFT_META_FILE):
                new_doc.meta[k] = self.doc.meta[k] or ""
        except Exception:
            pass
        new_doc.save(path)

    # tileset: Cesium 3D Tiles with the screen error, the heights, the check
    def tileset_panel(self):
        if not self._need_doc():
            return
        P = self._panels()
        dlg = P.TilesetDialog(self, P._parent())
        if dlg.exec_() != P.QtWidgets.QDialog.Accepted:
            return
        try:
            ps.app.messageBox(self.export_tileset(dlg.options()))
        except Exception as e:
            ps.app.messageBox(f"Tileset stopped: {e}")

    def _geoid_n(self, chunk, xyz):
        """EGM2008 undulation N at a point of the chunk CRS, if Metashape has
        the geoid; None otherwise."""
        try:
            wgs = ps.CoordinateSystem("EPSG::4326")
            ll = ps.CoordinateSystem.transform(ps.Vector(list(xyz)), chunk.crs, wgs)
            egm = ps.CoordinateSystem("EPSG::9518")      # WGS 84 + EGM2008 height
            h = ps.CoordinateSystem.transform(ps.Vector([ll[0], ll[1], 0.0]), egm, wgs)[2]
            return h
        except Exception:
            return None

    def height_diagnosis(self, chunk):
        crs = getattr(chunk, "crs", None)
        if crs is None:
            return {"text": "local chunk: no height to check.", "suggest": False}
        if "VERT_CS" in crs.wkt or crs.wkt.startswith("COMPD_CS"):
            return {"text": "%s has a vertical datum: heights are already orthometric." % crs.name,
                    "suggest": False}
        refs = [m for m in chunk.markers if m.reference.location is not None and m.reference.enabled]
        with_proj = [m for m in refs if len(m.projections.keys())]
        if not refs:
            return {"text": "%s has no vertical datum and the chunk has no reference markers: "
                            "heights are ellipsoidal as they stand." % crs.name, "suggest": False}
        n = self._geoid_n(chunk, refs[0].reference.location)
        nn = (" EGM2008 here: N ≈ %.2f m." % n) if n is not None else \
            " The EGM2008 geoid is not installed in Metashape: give a table of N per marker (JSON), or add the geoid in Preferences."
        how = ("" if with_proj else " These markers have no projections: the chunk is placed by its "
               "alignment, the correction comes from the chunk they were measured in.")
        return {"text": "%s has no vertical datum, and %d markers carry heights: if those are "
                        "orthometric (levelling, benchmarks), the tileset sits N metres too low.%s%s"
                        % (crs.name, len(refs), nn, how),
                "suggest": bool(with_proj), "geoid": n is not None}

    def _correct_heights(self, chunk, n_table=None):
        """Marker heights onto EGM2008, in memory: returns the undo list.
        N comes from ``n_table`` ({marker label: N}, the n_egm2008.json of
        7 Nov 2026) when given, otherwise from Metashape's geoid."""
        wgs = ps.CoordinateSystem("EPSG::4326")
        undo = [("transform", chunk, chunk.transform.matrix * ps.Matrix.Diag([1, 1, 1, 1]))]
        lines = []
        for m in chunk.markers:
            loc = m.reference.location
            if loc is None or not len(m.projections.keys()):
                continue
            n = (n_table or {}).get(m.label)
            if n is None:
                n = self._geoid_n(chunk, loc)
            if n is None:
                continue
            n = float(n)
            H = loc[2]
            delta = ps.CoordinateSystem.transform(ps.Vector([loc[0], loc[1], H]), chunk.crs, wgs)[2] - H
            undo.append(("marker", m, ps.Vector(loc)))
            m.reference.location = ps.Vector([loc[0], loc[1], H + n - delta])
            lines.append({"marker": m.label, "H": H, "N_egm2008": n, "delta_datum": delta})
        if not lines:
            raise Exception("no marker could be corrected (no projections, or no geoid)")
        chunk.updateTransform()
        return undo, lines

    def _undo(self, undo):
        for kind, obj, value in reversed(undo):
            try:
                if kind == "transform":
                    obj.transform.matrix = value
                else:
                    obj.reference.location = value
            except Exception as e:
                print(f"[3DSC tileset] undo failed: {e}")

    def export_tileset(self, o):
        chunk = self._get_chunk_by_key(o["chunk_key"])
        if chunk is None:
            raise Exception("choose a chunk")
        undo, height_lines = [], []
        t0 = dtc_stamp_ms.new_process_id()
        try:
            if o["fix_heights"]:
                table = None
                if o.get("n_file"):
                    with open(o["n_file"], encoding="utf-8") as fh:
                        table = json.load(fh)
                undo, height_lines = self._correct_heights(chunk, table)
            tiled = None
            if o["build"]:
                if chunk.model is None:
                    raise Exception("no active model to build the tileset from")
                textured = bool(getattr(chunk.model, "textures", None)) and len(chunk.model.textures) > 0
                # textured master: its texture is carried over; otherwise the photos texture it
                chunk.buildTiledModel(source_data=ps.DataSource.ModelData,
                                      pixel_size=ms_dd.TEXEL_MM / 1000.0, tile_size=256,
                                      transfer_texture=textured, replace_asset=False)
                tiled = chunk.tiled_model
            else:
                for t in chunk.tiled_models:
                    if t.key == o["tiled_key"]:
                        tiled = t
            if tiled is None:
                raise Exception("no tiled model in the chunk")
            fmt = getattr(ps.ImageFormat, "ImageFormat" + o["texture"], ps.ImageFormat.ImageFormatJPEG)
            path = o["path"]
            chunk.exportTiledModel(path=path, format=ps.TiledModelFormat.TiledModelFormatCesium,
                                   texture_format=fmt, tiled_model=tiled,
                                   model_compression=bool(o["draco"]),
                                   tileset_version=o["tileset_version"],
                                   use_tileset_transform=bool(o["use_tileset_transform"]),
                                   screen_space_error=float(o["screen_space_error"]),
                                   folder_depth=int(o["folder_depth"]),
                                   clip_to_boundary=bool(o["clip_to_boundary"]))
        finally:
            self._undo(undo)          # the project is never left corrected
        check = ""
        try:
            info = ms_tileset.inspect(path)
            check = ms_tileset.report(info)
        except Exception as e:
            info, check = None, "check not possible: %s" % e
        params = {"ExportTiledModel/screen_space_error": float(o["screen_space_error"]),
                  "ExportTiledModel/tileset_version": o["tileset_version"],
                  "ExportTiledModel/texture_format": o["texture"],
                  "ExportTiledModel/model_compression": bool(o["draco"]),
                  "ExportTiledModel/use_tileset_transform": bool(o["use_tileset_transform"]),
                  "ExportTiledModel/folder_depth": int(o["folder_depth"]),
                  "ExportTiledModel/clip_to_boundary": bool(o["clip_to_boundary"])}
        if height_lines:
            params["3DSC/height_correction"] = height_lines
        if info:
            params["3DSC/check"] = {"levels": info["levels"], "primitives_mean": info["primitives_mean"],
                                    "root": info["root"]}
        stamp = self._stamp(chunk, tiled, [path] if os.path.isfile(path) else [], self._ask_operator(),
                            process_id=t0, label=os.path.basename(path), parameters=params)
        return "Tileset written:\n%s\n\n%s%s\n%s" % (
            path, check, ("\n\nHeights: %d markers moved onto EGM2008 for this export; the project "
                          "is back as it was." % len(height_lines)) if height_lines else "",
            dtc_stamp_ms.report_line(stamp))

    # rename chunks with a pattern
    def rename_panel(self):
        if not self._need_doc():
            return
        P = self._panels()
        dlg = P.RenameDialog(self, P._parent())
        if dlg.exec_() != P.QtWidgets.QDialog.Accepted:
            return
        rows = dlg.names()
        for c, new in rows:
            c.label = new
        ps.app.messageBox("Renamed %d chunks." % len(rows))


    def export_undistorted_images_active_chunk(self):
        try:
            if self.doc.chunk is None:
                ps.app.messageBox("Error - No active chunk found.")
                return

            chunk = self.doc.chunk
            if not chunk.cameras:
                ps.app.messageBox("Error - Active chunk has no cameras.")
                return

            export_root = ps.app.getExistingDirectory("Select destination folder for undistorted images:")
            if not export_root:
                return

            chunk_label = chunk.label if chunk.label else "active_chunk"
            safe_label = "".join(c if c.isalnum() or c in ('_', '-', '.') else '_' for c in chunk_label)
            export_folder = os.path.join(export_root, safe_label + "_undistorted")
            os.makedirs(export_folder, exist_ok=True)

            output_pattern = os.path.join(export_folder, "{filename}.{fileext}")
            chunk.convertImages(
                path=output_pattern,
                use_initial_calibration=True,
                color_correction=False,
                merge_planes=False,
                update_gps_tags=False,
            )

            exported = len([cam for cam in chunk.cameras if cam.photo is not None])
            ps.app.update()
            stamp_results = self._stamp(
                chunk, None, [export_folder], self._ask_operator(),
                dtc_kind="transformation", photos=True,
                technique="Metashape Convert Images (undistort, initial calibration)",
                parameters={"ConvertImages/use_initial_calibration": True,
                            "ConvertImages/color_correction": False,
                            "ConvertImages/merge_planes": False,
                            "ConvertImages/update_gps_tags": False})
            ps.app.messageBox(
                f"Success - Exported {exported} undistorted images to {export_folder}.\n"
                + dtc_stamp_ms.report_line(stamp_results)
            )

        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")

    def rename_chunks(self):
        try:
            number = 1
            for i in range(1, len(self.doc.chunks)):
                chunk = self.doc.chunks[i]
                chunk.label = str(number) + "_mt"
                number += 1
            
            ps.app.messageBox(f"Success - Renamed {number-1} chunks successfully.")
            
        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")
    
    def import_ipad_cameras(self):
        """
        EXPERIMENTAL FEATURE
        Import camera positions from iPad's 3D Scanner App using AR tracking data.
        This feature is still under development and may not work reliably in all cases.
        """
        try:
            # Get the folder containing the iPad captures
            image_folder = ps.app.getExistingDirectory("Select the folder with iPad captured images:")
            if not image_folder:
                return
            
            # Ask for options
            optimize_ar = ps.app.getBool("Optimize AR Alignment?")
            use_ar_constraints = False
            filter_bad_ar = False
            
            if optimize_ar:
                use_ar_constraints = ps.app.getBool("Use AR Data as Constraints?")
                filter_bad_ar = ps.app.getBool("Filter Bad AR Alignments?")
            
            # Create a new chunk for the imported data
            chunk = self.doc.addChunk()
            chunk.label = "iPad_Import_" + os.path.basename(image_folder)
            self.doc.chunk = chunk  # Rende attivo il nuovo chunk
            
            # Find all images and their corresponding JSON files
            image_files = [f for f in os.listdir(image_folder) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            
            if not image_files:
                ps.app.messageBox("Error - No image files found in the selected folder.")
                return
            
            # Load the images into the chunk
            image_list = []
            for img in image_files:
                image_path = os.path.join(image_folder, img)
                image_list.append(image_path)
            
            print(f"Adding {len(image_list)} photos to the chunk...")
            ps.app.update()
            chunk.addPhotos(image_list)
            
            # Initialize region with default values before processing any cameras
            # Questo garantisce che la region sia valida anche in caso di errori successivi
            region = chunk.region
            region.center = ps.Vector([0, 0, 0])
            region.size = ps.Vector([100, 100, 100])  # Dimensioni di default abbastanza grandi
            region.rot = ps.Matrix([[1, 0, 0], [0, 1, 0], [0, 0, 1]])  # Matrice identità
            
            # Find and process the camera alignment data from JSON files
            cameras_with_data = 0
            camera_positions = []  # To track camera positions for region calculation
            
            print("Processing camera alignment data from JSON files...")
            ps.app.update()
            
            for i, camera in enumerate(chunk.cameras):
                # Aggiorna UI periodicamente
                if i % 10 == 0:
                    ps.app.update()
                    print(f"Processed {i}/{len(chunk.cameras)} cameras...")
                
                # Prendi il nome del file senza estensione
                image_name = os.path.splitext(os.path.basename(camera.photo.path))[0]
                json_file = os.path.join(image_folder, image_name + ".json")
                
                if os.path.exists(json_file):
                    with open(json_file, 'r') as f:
                        try:
                            data = json.load(f)
                            
                            # Extract camera pose matrix from AR data
                            if "cameraPoseARFrame" in data:
                                camera_matrix = data["cameraPoseARFrame"]
                                
                                # Verifica dimensioni matrice
                                if len(camera_matrix) != 16:
                                    print(f"Unexpected matrix size for {image_name}: {len(camera_matrix)} elements")
                                    continue
                                
                                # Conversione coordinate ARKit (Y-up) a Metashape (Z-up)
                                arkit_to_metashape = ps.Matrix([
                                    [1, 0, 0, 0],
                                    [0, 0, 1, 0],
                                    [0, -1, 0, 0],
                                    [0, 0, 0, 1]
                                ])
                                
                                # Matrice di trasformazione ARKit
                                ar_transform = ps.Matrix([
                                    [camera_matrix[0], camera_matrix[1], camera_matrix[2], camera_matrix[3]],
                                    [camera_matrix[4], camera_matrix[5], camera_matrix[6], camera_matrix[7]],
                                    [camera_matrix[8], camera_matrix[9], camera_matrix[10], camera_matrix[11]],
                                    [0, 0, 0, 1]
                                ])
                                
                                # Inversione e conversione
                                try:
                                    ar_transform_inv = ar_transform.inv()
                                    transform = ar_transform_inv * arkit_to_metashape
                                    
                                    # Imposta trasformazione
                                    camera.transform = transform
                                    
                                    # Verifica che transform abbia funzionato correttamente
                                    if camera.center:
                                        camera_positions.append(camera.center)
                                        
                                        # Imposta reference
                                        camera.reference.location = camera.center
                                        camera.reference.enabled = True
                                        
                                        cameras_with_data += 1
                                    else:
                                        print(f"Warning: Failed to get camera center for {image_name}")
                                except Exception as matrix_error:
                                    print(f"Matrix error for {image_name}: {str(matrix_error)}")
                                    continue
                                
                                # Extract intrinsics if available
                                if "intrinsics" in data:
                                    intrinsics = data["intrinsics"]
                                    if len(intrinsics) >= 9:
                                        fx = intrinsics[0]
                                        fy = intrinsics[4]
                                        cx = intrinsics[2]
                                        cy = intrinsics[5]
                                        
                                        sensor = camera.sensor
                                        calib = sensor.calibration
                                        calib.f = (fx + fy) / 2
                                        calib.cx = cx - sensor.width / 2
                                        calib.cy = cy - sensor.height / 2
                                        sensor.fixed = True
                        
                        except json.JSONDecodeError:
                            print(f"Error reading JSON file: {json_file}")
                            continue
                        except Exception as e:
                            print(f"Error processing camera {image_name}: {str(e)}")
                            continue
            
            if cameras_with_data == 0:
                ps.app.messageBox("Warning - No AR camera data found in the JSON files.")
                return
            
            # Calculate and set proper region based on camera positions
            if camera_positions:
                print(f"Calculating region based on {len(camera_positions)} camera positions...")
                ps.app.update()
                
                # Trova i bounds delle posizioni delle camere
                min_x = min_y = min_z = float('inf')
                max_x = max_y = max_z = float('-inf')
                
                for pos in camera_positions:
                    min_x = min(min_x, pos.x)
                    max_x = max(max_x, pos.x)
                    min_y = min(min_y, pos.y)
                    max_y = max(max_y, pos.y)
                    min_z = min(min_z, pos.z)
                    max_z = max(max_z, pos.z)
                
                # Calcola centro e dimensioni
                center_x = (min_x + max_x) / 2
                center_y = (min_y + max_y) / 2
                center_z = (min_z + max_z) / 2
                
                size_x = max(abs(max_x - min_x), 1)
                size_y = max(abs(max_y - min_y), 1)
                size_z = max(abs(max_z - min_z), 1)
                
                # Aggiungi margine del 50%
                size_x *= 1.5
                size_y *= 1.5
                size_z *= 1.5
                
                region.center = ps.Vector([center_x, center_y, center_z])
                region.size = ps.Vector([size_x, size_y, size_z])
                chunk.region = region
                
                print(f"Region set: center={center_x:.2f},{center_y:.2f},{center_z:.2f}, size={size_x:.2f},{size_y:.2f},{size_z:.2f}")
            
            # Attempt to save the project
            save_path = None
            try:
                if self.doc.path:
                    save_path = self.doc.path
                    self.doc.save(save_path)
                    print(f"Project saved to {save_path}")
                else:
                    print("Warning: Document has no path. Please save manually.")
            except Exception as save_error:
                print(f"Error saving document: {str(save_error)}. Please save manually.")
            
            # Aggiorna il documento prima di procedere con l'allineamento
            ps.app.update()
            
            # Optimize the alignment if requested
            if optimize_ar:
                print("Optimizing AR alignment...")
                ps.app.update()
                
                if use_ar_constraints:
                    # Prepare AR constraints
                    for camera in chunk.cameras:
                        if camera.transform:
                            if not camera.reference.enabled:
                                camera.reference.location = camera.center
                                camera.reference.enabled = True
                            
                            # Accuracy for constraints
                            camera.reference.accuracy = ps.Vector([0.1, 0.1, 0.1])
                    
                    ps.app.update()
                
                # Match photos
                try:
                    print("Matching photos...")
                    ps.app.update()
                    
                    chunk.matchPhotos(
                        generic_preselection=True, 
                        reference_preselection=use_ar_constraints,
                        keypoint_limit=40000,
                        tiepoint_limit=4000
                    )
                    
                    # Salva dopo il matching
                    ps.app.update()
                    if save_path:
                        self.doc.save(save_path)
                    else:
                        try:
                            self.doc.save()
                        except:
                            pass
                    
                    print("Aligning cameras...")
                    ps.app.update()
                    
                    # Align cameras
                    chunk.alignCameras(
                        reset_alignment=False,
                        adaptive_fitting=True,
                        min_image=2
                    )
                    
                    # Salva dopo l'allineamento
                    ps.app.update()
                    if save_path:
                        self.doc.save(save_path)
                    else:
                        try:
                            self.doc.save()
                        except:
                            pass
                    
                except Exception as align_error:
                    print(f"Error during alignment: {str(align_error)}")
                    ps.app.update()
                    
                    # Alternative approach
                    try:
                        print("Trying alternative alignment approach...")
                        ps.app.update()
                        chunk.alignCameras()
                        ps.app.update()
                        if save_path:
                            self.doc.save(save_path)
                        else:
                            try:
                                self.doc.save()
                            except:
                                pass
                    except Exception as alt_error:
                        print(f"Alternative alignment also failed: {str(alt_error)}")
                        ps.app.update()
                
                # Filter bad alignments if requested
                if filter_bad_ar:
                    print("Filtering bad alignments...")
                    ps.app.update()
                    
                    disabled_count = 0
                    for camera in chunk.cameras:
                        if camera.transform is None:
                            continue
                            
                        if camera.reference.location:
                            # Calculate distance between estimated and reference
                            dist_x = abs(camera.center.x - camera.reference.location.x)
                            dist_y = abs(camera.center.y - camera.reference.location.y)
                            dist_z = abs(camera.center.z - camera.reference.location.z)
                            distance = math.sqrt(dist_x**2 + dist_y**2 + dist_z**2)
                            
                            if distance > 0.5:  # Threshold in meters
                                camera.enabled = False
                                disabled_count += 1
                    
                    print(f"Disabled {disabled_count} cameras due to large alignment differences")
                    ps.app.update()
                    
                    # Salva dopo il filtraggio
                    if save_path:
                        self.doc.save(save_path)
                    else:
                        try:
                            self.doc.save()
                        except:
                            pass
            
            # Final updates
            chunk.resetRegion()  # Reset region to ensure it's correctly set
            ps.app.update()
            
            # Salvataggio finale
            if save_path:
                self.doc.save(save_path)
            else:
                try:
                    self.doc.save()
                except:
                    pass
            
            # Breve pausa prima del messaggio finale
            import time
            time.sleep(0.5)
            
            ps.app.messageBox(f"Success - Imported {len(image_files)} images with {cameras_with_data} AR camera positions.")
            
        except Exception as e:
            ps.app.update()
            print(f"Critical error: {str(e)}")
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")
            
            try:
                # Prova a salvare in caso di errore
                if 'save_path' in locals() and save_path:
                    self.doc.save(save_path)
                else:
                    self.doc.save()
            except:
                pass

# Create the tool (a headless run sets DSC_MS_HEADLESS and builds its own,
# with gui=False, to call the same code the menu calls)
if not os.environ.get("DSC_MS_HEADLESS"):
    tool = MetashapeTools()
