"""The panels of 3DSC for Metashape (PySide2, as shipped with Metashape).

One panel per step of the chain: Shift, Import, Masters, Blocks, Texturing,
Tileset, Rename. Each says in one line why the step exists; the work itself is
done by the MetashapeTools methods (3DSC_MS_GUI.py) or by the pure modules
(ms_dd, ms_grid, ms_tileset), so the logic stays testable without Metashape.
"""

from __future__ import annotations

import json
import os

import Metashape as ps
from PySide2 import QtCore, QtWidgets

import ms_dd
import ms_grid

MODEL_EXT = (".obj", ".ply", ".fbx", ".dae", ".stl", ".3ds", ".gltf", ".glb")


# ── small helpers ────────────────────────────────────────────────────────────

def _parent():
    return QtWidgets.QApplication.instance().activeWindow()


def note(text):
    """The one-line narrative of a panel: why this step exists."""
    lab = QtWidgets.QLabel(text)
    lab.setWordWrap(True)
    lab.setStyleSheet("color: palette(mid); font-style: italic;")
    return lab


def bibliography_box():
    box = QtWidgets.QGroupBox("Rule and reference")
    lay = QtWidgets.QVBoxLayout(box)
    lab = QtWidgets.QLabel(ms_dd.RULE_LINE + "<br><br>" + "<br>".join(ms_dd.BIBLIOGRAPHY).replace(
        "https://doi.org/10.3390/rs18020203",
        '<a href="https://doi.org/10.3390/rs18020203">doi.org/10.3390/rs18020203</a>'))
    lab.setWordWrap(True)
    lab.setOpenExternalLinks(True)
    lab.setTextFormat(QtCore.Qt.RichText)
    lab.setStyleSheet("font-size: 11px;")
    lay.addWidget(lab)
    return box


def _dspin(value, lo, hi, dec=2, step=0.01, suffix=""):
    s = QtWidgets.QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(dec)
    s.setSingleStep(step)
    s.setValue(value)
    if suffix:
        s.setSuffix(suffix)
    return s


def _ispin(value, lo, hi, suffix=""):
    s = QtWidgets.QSpinBox()
    s.setRange(lo, hi)
    s.setValue(value)
    if suffix:
        s.setSuffix(suffix)
    return s


def _buttons(dlg, ok="Run"):
    bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
    bb.button(QtWidgets.QDialogButtonBox.Ok).setText(ok)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    return bb


def _chunk_combo(doc, select=None, only_models=False):
    cb = QtWidgets.QComboBox()
    for c in doc.chunks:
        if only_models and not list(getattr(c, "models", []) or []):
            continue
        cb.addItem(c.label or "(no name)", c.key)
    if select is not None:
        i = cb.findData(select.key)
        if i >= 0:
            cb.setCurrentIndex(i)
    return cb


def _chunk_by_key(doc, key):
    for c in doc.chunks:
        if c.key == key:
            return c
    return None


def _model_label(m, i):
    return m.label or ("model %d" % (i + 1))


def is_master(chunk):
    try:
        return chunk.meta["3dsc_master"] == "1"
    except Exception:
        return False


# ── Shift ────────────────────────────────────────────────────────────────────

class ShiftDialog(QtWidgets.QDialog):
    def __init__(self, tool, parent=None):
        super().__init__(parent)
        self.tool = tool
        self.setWindowTitle("3DSC · Shift")
        self.setMinimumWidth(520)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(note("One shift for every import and export: the same numbers Blender used. "
                           "It is saved in the project."))
        f = QtWidgets.QFormLayout()
        self.file = QtWidgets.QLabel()
        self.file.setWordWrap(True)
        self.crs = QtWidgets.QLabel()
        self.xyz = QtWidgets.QLabel()
        self.xyz.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        f.addRow("File", self.file)
        f.addRow("CRS", self.crs)
        f.addRow("Shift X Y Z", self.xyz)
        lay.addLayout(f)
        self.preview = QtWidgets.QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(90)
        lay.addWidget(QtWidgets.QLabel("File content"))
        lay.addWidget(self.preview)
        row = QtWidgets.QHBoxLayout()
        b_load = QtWidgets.QPushButton("Load SHIFT.txt…")
        b_load.clicked.connect(self.load)
        b_clear = QtWidgets.QPushButton("Clear")
        b_clear.clicked.connect(self.clear)
        b_close = QtWidgets.QPushButton("Close")
        b_close.clicked.connect(self.accept)
        row.addWidget(b_load)
        row.addWidget(b_clear)
        row.addStretch(1)
        row.addWidget(b_close)
        lay.addLayout(row)
        self.refresh()

    def refresh(self):
        t = self.tool
        t.restore_shift_from_doc()
        if t.global_shift_vector is None:
            self.file.setText("—")
            self.crs.setText("—")
            self.xyz.setText("no shift: imports and exports use real coordinates")
            self.preview.setPlainText("")
            return
        v = t.global_shift_vector
        self.file.setText(t.global_shift_file or "(from the project)")
        self.crs.setText(t.global_shift_crs_string or "LOCAL")
        self.xyz.setText("%.3f   %.3f   %.3f" % (v.x, v.y, v.z))
        txt = t.global_shift_line or ""
        try:
            if t.global_shift_file and os.path.exists(t.global_shift_file):
                with open(t.global_shift_file, encoding="utf-8") as fh:
                    txt = fh.read(2000)
        except OSError:
            pass
        self.preview.setPlainText(txt)

    def load(self):
        last = ps.app.settings.value("3dsc/last_shift_dir") or ""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "SHIFT.txt", last, "Text (*.txt);;All (*)")
        if not path:
            return
        try:
            self.tool.set_shift_from_file(path)
            ps.app.settings.setValue("3dsc/last_shift_dir", os.path.dirname(path))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "3DSC", "Shift not loaded: %s" % e)
        self.refresh()

    def clear(self):
        self.tool.clear_global_shift(quiet=True)
        self.refresh()


# ── Import ───────────────────────────────────────────────────────────────────

class ImportDialog(QtWidgets.QDialog):
    def __init__(self, tool, parent=None):
        super().__init__(parent)
        self.tool = tool
        doc = tool.doc
        self.setWindowTitle("3DSC · Import models")
        self.setMinimumWidth(600)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(note("Blocks cut physically (not the Cesium tileset). Each one lands in a copy "
                           "of the master — photos and tie points only — so it can be textured "
                           "from the photos."))
        self.files = QtWidgets.QListWidget()
        self.files.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        lay.addWidget(self.files)
        row = QtWidgets.QHBoxLayout()
        for text, fn in (("Add files…", self.add_files), ("Add folder…", self.add_folder),
                         ("Remove", self.remove)):
            b = QtWidgets.QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)

        f = QtWidgets.QFormLayout()
        self.use_shift = QtWidgets.QCheckBox()
        self.use_shift.setChecked(True)
        self.shift_lab = QtWidgets.QLabel()
        srow = QtWidgets.QHBoxLayout()
        srow.addWidget(self.use_shift)
        srow.addWidget(self.shift_lab, 1)
        b = QtWidgets.QPushButton("Shift…")
        b.clicked.connect(self.edit_shift)
        srow.addWidget(b)
        f.addRow("Shift", srow)

        self.r_each = QtWidgets.QRadioButton("One chunk per model, from the master")
        self.r_one = QtWidgets.QRadioButton("All models in one chunk (e.g. to build a tileset)")
        self.r_each.setChecked(True)
        mode = QtWidgets.QVBoxLayout()
        mode.addWidget(self.r_each)
        mode.addWidget(self.r_one)
        f.addRow("Chunks", mode)

        mrow = QtWidgets.QHBoxLayout()
        self.master = QtWidgets.QComboBox()
        mrow.addWidget(self.master, 1)
        b = QtWidgets.QPushButton("Create master from the active chunk")
        b.clicked.connect(self.create_master)
        mrow.addWidget(b)
        f.addRow("Master", mrow)
        lay.addLayout(f)
        lay.addWidget(_buttons(self, "Import"))
        self.fill_masters()
        self.refresh_shift()

    def fill_masters(self, select_key=None):
        self.master.clear()
        doc = self.tool.doc
        masters = [c for c in doc.chunks if is_master(c)]
        others = [c for c in doc.chunks if not is_master(c)]
        for c in masters:
            self.master.addItem("%s  (master)" % c.label, c.key)
        for c in others:
            self.master.addItem(c.label, c.key)
        if select_key is not None:
            i = self.master.findData(select_key)
            if i >= 0:
                self.master.setCurrentIndex(i)

    def refresh_shift(self):
        t = self.tool
        t.restore_shift_from_doc()
        if t.global_shift_vector is None:
            self.shift_lab.setText("none loaded")
            self.use_shift.setChecked(False)
        else:
            v = t.global_shift_vector
            self.shift_lab.setText("%s  %.3f %.3f %.3f" % (t.global_shift_crs_string or "LOCAL", v.x, v.y, v.z))

    def edit_shift(self):
        ShiftDialog(self.tool, self).exec_()
        self.refresh_shift()
        if self.tool.global_shift_vector is not None:
            self.use_shift.setChecked(True)

    def add_files(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Models", "", "3D models (%s);;All (*)" % " ".join("*" + e for e in MODEL_EXT))
        for p in paths:
            self.files.addItem(p)

    def add_folder(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Folder of models")
        if not d:
            return
        for fn in sorted(os.listdir(d)):
            if fn.lower().endswith(MODEL_EXT):
                self.files.addItem(os.path.join(d, fn))
        # a SHIFT.txt beside the models, and no shift loaded yet: offer it
        if self.tool.global_shift_vector is None:
            for fn in os.listdir(d):
                if fn.lower() in ("shift.txt", "global_shift.txt"):
                    if QtWidgets.QMessageBox.question(
                            self, "3DSC", "Use %s as the shift?" % fn) == QtWidgets.QMessageBox.Yes:
                        self.tool.set_shift_from_file(os.path.join(d, fn))
                        self.refresh_shift()
                        self.use_shift.setChecked(True)
                    break

    def remove(self):
        for it in self.files.selectedItems():
            self.files.takeItem(self.files.row(it))

    def create_master(self):
        doc = self.tool.doc
        if doc.chunk is None:
            return
        try:
            m = self.tool.create_master(doc.chunk)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "3DSC", "Master not created: %s" % e)
            return
        self.fill_masters(m.key)

    def options(self):
        return {"paths": [self.files.item(i).text() for i in range(self.files.count())],
                "use_shift": self.use_shift.isChecked(),
                "one_chunk": self.r_one.isChecked(),
                "master_key": self.master.currentData()}


# ── Masters ──────────────────────────────────────────────────────────────────

class MastersDialog(QtWidgets.QDialog):
    def __init__(self, tool, parent=None):
        super().__init__(parent)
        self.tool = tool
        doc = tool.doc
        self.setWindowTitle("3DSC · Masters")
        self.setMinimumWidth(560)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(note("Clean the high model first (trees, scaffolding, noise): the lighter "
                           "masters inherit the cleaning. Re-run after every cleaning."))
        f = QtWidgets.QFormLayout()
        self.chunk = _chunk_combo(doc, doc.chunk, only_models=True)
        self.chunk.currentIndexChanged.connect(self.fill_models)
        self.model = QtWidgets.QComboBox()
        self.model.currentIndexChanged.connect(self.stats)
        self.info = QtWidgets.QLabel()
        f.addRow("Chunk", self.chunk)
        f.addRow("Source model", self.model)
        f.addRow("", self.info)
        lay.addLayout(f)
        g = QtWidgets.QGroupBox("Masters to make (polygons per m² of surface)")
        gl = QtWidgets.QGridLayout(g)
        self.d_tex = _ispin(ms_dd.DENSITY_TEXTURABLE, 100, 1000000)
        self.d_til = _ispin(ms_dd.DENSITY_TILEABLE, 10, 1000000)
        self.c_geo = QtWidgets.QCheckBox("Geometric super master: the source, above %d/m² (print, archive)"
                                         % ms_dd.DENSITY_GEOMETRIC)
        self.c_geo.setChecked(True)
        self.c_tex = QtWidgets.QCheckBox("Texturable master → tileset, normal maps")
        self.c_tex.setChecked(True)
        self.c_til = QtWidgets.QCheckBox("Tileable master = LOD0 → blocks")
        self.c_til.setChecked(True)
        gl.addWidget(self.c_geo, 0, 0, 1, 2)
        gl.addWidget(self.c_tex, 1, 0)
        gl.addWidget(self.d_tex, 1, 1)
        gl.addWidget(self.c_til, 2, 0)
        gl.addWidget(self.d_til, 2, 1)
        lay.addWidget(g)
        lay.addWidget(_buttons(self, "Make masters"))
        self.fill_models()

    def _chunk(self):
        return _chunk_by_key(self.tool.doc, self.chunk.currentData())

    def fill_models(self):
        self.model.clear()
        c = self._chunk()
        if c is None:
            return
        for i, m in enumerate(c.models):
            self.model.addItem(_model_label(m, i), m.key)
            if c.model is not None and m.key == c.model.key:
                self.model.setCurrentIndex(i)
        self.stats()

    def _model(self):
        c = self._chunk()
        if c is None:
            return None
        for m in c.models:
            if m.key == self.model.currentData():
                return m
        return None

    def stats(self):
        faces, area, dens = self.tool._mesh_stats(self._model())
        if not faces:
            self.info.setText("")
            return
        self.info.setText("%s faces · %s m² · %s faces/m²" % (
            "{:,}".format(faces), "{:,.1f}".format(area or 0), "{:,.0f}".format(dens or 0)))

    def options(self):
        return {"chunk_key": self.chunk.currentData(), "model_key": self.model.currentData(),
                "geometric": self.c_geo.isChecked(),
                "texturable": self.d_tex.value() if self.c_tex.isChecked() else 0,
                "tileable": self.d_til.value() if self.c_til.isChecked() else 0}


# ── Blocks (the grid) ────────────────────────────────────────────────────────

class BlocksDialog(QtWidgets.QDialog):
    def __init__(self, tool, parent=None):
        super().__init__(parent)
        self.tool = tool
        doc = tool.doc
        self.setWindowTitle("3DSC · Blocks")
        self.setMinimumWidth(580)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(note("Cut the tileable master (LOD0) into blocks on a grid turned with the "
                           "monument and tight on the mesh. The chunk is never rotated: the grid "
                           "lives only in the cut, and the same settings give the same blocks."))
        f = QtWidgets.QFormLayout()
        self.chunk = _chunk_combo(doc, doc.chunk, only_models=True)
        f.addRow("Chunk (active model)", self.chunk)
        self.area = _dspin(80.0, 1.0, 100000.0, 1, 5.0, " m²")
        self.area.valueChanged.connect(self._side)
        self.side = QtWidgets.QLabel()
        arow = QtWidgets.QHBoxLayout()
        arow.addWidget(self.area)
        arow.addWidget(self.side, 1)
        f.addRow("Block plan area", arow)
        self.r_fit = QtWidgets.QRadioButton("Fit to the mesh (tightest rectangle)")
        self.r_bear = QtWidgets.QRadioButton("Bearing of the main axis")
        self.r_north = QtWidgets.QRadioButton("North (Metashape default)")
        self.r_fit.setChecked(True)
        self.bearing = _dspin(0.0, -180.0, 180.0, 2, 0.5, "°")
        ori = QtWidgets.QGridLayout()
        ori.addWidget(self.r_fit, 0, 0, 1, 2)
        ori.addWidget(self.r_bear, 1, 0)
        ori.addWidget(self.bearing, 1, 1)
        ori.addWidget(self.r_north, 2, 0, 1, 2)
        f.addRow("Grid", ori)
        self.preview_lab = QtWidgets.QLabel("")
        self.preview_lab.setWordWrap(True)
        b = QtWidgets.QPushButton("Preview the grid")
        b.clicked.connect(self.preview)
        prow = QtWidgets.QHBoxLayout()
        prow.addWidget(b)
        prow.addWidget(self.preview_lab, 1)
        f.addRow("", prow)
        self.min_faces = _ispin(2000, 0, 10000000)
        self.merge = QtWidgets.QCheckBox("merge each one into its largest neighbour (off = only flag)")
        self.merge.setChecked(True)
        mrow = QtWidgets.QHBoxLayout()
        mrow.addWidget(self.min_faces)
        mrow.addWidget(self.merge, 1)
        f.addRow("Small tiles under (faces)", mrow)
        self.multi = QtWidgets.QCheckBox("one chunk per block, copied from the master")
        self.multi.setChecked(True)
        self.master = QtWidgets.QComboBox()
        self.master.addItem("(the source chunk, lightened)", None)
        for c in doc.chunks:
            if is_master(c):
                self.master.addItem(c.label, c.key)
        if self.master.count() > 1:
            self.master.setCurrentIndex(1)
        f.addRow("Output", self.multi)
        f.addRow("Master", self.master)
        self.out = QtWidgets.QLineEdit()
        b = QtWidgets.QPushButton("…")
        b.clicked.connect(self.pick_out)
        orow = QtWidgets.QHBoxLayout()
        orow.addWidget(self.out, 1)
        orow.addWidget(b)
        f.addRow("Folder", orow)
        lay.addLayout(f)
        lay.addWidget(_buttons(self, "Cut"))
        self._side()

    def _side(self):
        import math
        self.side.setText("block side %.2f m" % math.sqrt(self.area.value()))

    def pick_out(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Folder for the blocks")
        if d:
            self.out.setText(d)

    def grid(self):
        if self.r_north.isChecked():
            return {"mode": "north"}
        if self.r_bear.isChecked():
            return {"mode": "bearing", "bearing": self.bearing.value()}
        return {"mode": "fit"}

    def preview(self):
        import math
        c = _chunk_by_key(self.tool.doc, self.chunk.currentData())
        if c is None or c.model is None:
            return
        try:
            info = self.tool.grid_preview(c, math.sqrt(self.area.value()), self.grid())
        except Exception as e:
            self.preview_lab.setText("no preview: %s" % e)
            return
        self.preview_lab.setText(info["text"])
        if self.r_fit.isChecked() and info.get("bearing") is not None:
            self.bearing.setValue(info["bearing"])

    def accept(self):
        if not self.out.text():
            QtWidgets.QMessageBox.warning(self, "3DSC", "Choose the folder for the blocks.")
            return
        super().accept()

    def options(self):
        import ms_blocks
        return {"chunk_key": self.chunk.currentData(), "target_area_m2": self.area.value(),
                "grid": self.grid(), "min_faces": self.min_faces.value(),
                "small_mode": ms_blocks.SMALL_MERGE if self.merge.isChecked() else ms_blocks.SMALL_FLAG,
                "output_multi_chunks": self.multi.isChecked(), "master_key": self.master.currentData(),
                "export_root": self.out.text(), "run_step2_now": False, "grid_naming": True}


# ── Texturing ────────────────────────────────────────────────────────────────

class TexturingDialog(QtWidgets.QDialog):
    MANY_CHUNKS = 12

    def __init__(self, tool, parent=None):
        super().__init__(parent)
        self.tool = tool
        doc = tool.doc
        self.setWindowTitle("3DSC · Texturing (Demetrescu-D'Annibale rule)")
        self.setMinimumSize(760, 560)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(note("About a millimetre per texel on the surface. Large areas need no cap: "
                           "either more pages at the same texel, or fewer pages and a coarser texel."))
        prow = QtWidgets.QHBoxLayout()
        self.texel = _dspin(ms_dd.TEXEL_MM, 0.1, 100.0, 2, 0.01, " mm")
        self.atlas = QtWidgets.QComboBox()
        for s in (2048, 4096, 8192):
            self.atlas.addItem(str(s), s)
        self.atlas.setCurrentIndex(1)
        self.ratio = _dspin(ms_dd.UV_RATIO, 0.1, 1.0, 2, 0.05)
        self.cap = _ispin(0, 0, 1000)
        self.cap.setSpecialValueText("no cap")
        for lab, w in (("Texel", self.texel), ("Atlas", self.atlas), ("UV ratio", self.ratio),
                       ("Max pages per chunk", self.cap)):
            prow.addWidget(QtWidgets.QLabel(lab))
            prow.addWidget(w)
        prow.addStretch(1)
        lay.addLayout(prow)
        for w in (self.texel, self.ratio, self.cap):
            w.valueChanged.connect(self.simulate)
        self.atlas.currentIndexChanged.connect(self.simulate)

        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Chunk", "Area m²", "Faces", "Pages", "Texel mm", "MB (raw)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        lay.addWidget(self.table, 1)
        srow = QtWidgets.QHBoxLayout()
        for text, fn in (("Select all", lambda: self.check_all(True)), ("None", lambda: self.check_all(False)),
                         ("Untick masters", self.untick_masters)):
            b = QtWidgets.QPushButton(text)
            b.clicked.connect(fn)
            srow.addWidget(b)
        srow.addStretch(1)
        self.total = QtWidgets.QLabel()
        srow.addWidget(self.total)
        lay.addLayout(srow)
        self.advice = QtWidgets.QLabel()
        self.advice.setWordWrap(True)
        lay.addWidget(self.advice)
        self.b_new = QtWidgets.QPushButton("Work in a new project with the reference chunk and the ticked ones…")
        self.b_new.clicked.connect(self.new_project)
        lay.addWidget(self.b_new)
        lay.addWidget(bibliography_box())
        lay.addWidget(_buttons(self, "Texture the ticked chunks"))
        self.rows = []
        self.fill()

    def fill(self):
        doc = self.tool.doc
        self.rows = []
        self.table.setRowCount(0)
        for c in doc.chunks:
            m = getattr(c, "model", None)
            faces, area, _ = self.tool._mesh_stats(m)
            r = self.table.rowCount()
            self.table.insertRow(r)
            it = QtWidgets.QTableWidgetItem(c.label + ("  (master)" if is_master(c) else ""))
            it.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            ok = bool(m is not None and area)
            it.setCheckState(QtCore.Qt.Checked if ok and not is_master(c) else QtCore.Qt.Unchecked)
            if not ok:
                it.setFlags(QtCore.Qt.ItemIsEnabled)
            self.table.setItem(r, 0, it)
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem("%.1f" % area if area else "—"))
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem("{:,}".format(faces) if faces else "—"))
            self.rows.append((c.key, area or 0.0, ok, is_master(c)))
        self.table.itemChanged.connect(lambda *_: self.simulate())
        self.simulate()

    def params(self):
        return {"texel": self.texel.value(), "atlas": self.atlas.currentData(),
                "ratio": self.ratio.value(), "cap": self.cap.value() or None}

    def simulate(self):
        p = self.params()
        tot_pages = tot_mb = n = 0
        self.table.blockSignals(True)
        for r, (key, area, ok, _m) in enumerate(self.rows):
            if not ok:
                for col in (3, 4, 5):
                    self.table.setItem(r, col, QtWidgets.QTableWidgetItem("—"))
                continue
            s = ms_dd.simulate(area, p["texel"], p["atlas"], p["ratio"], p["cap"])
            pages = s["pages_cap"] if s["over"] else s["pages"]
            texel = s["texel_cap"] if s["over"] else s["texel"]
            self.table.setItem(r, 3, QtWidgets.QTableWidgetItem(
                str(pages) + ("  (rule: %d)" % s["pages"] if s["over"] else "")))
            self.table.setItem(r, 4, QtWidgets.QTableWidgetItem("%.2f" % texel))
            mb = ms_dd.pixels_mb(pages, p["atlas"])
            self.table.setItem(r, 5, QtWidgets.QTableWidgetItem("%.0f" % mb))
            if self.table.item(r, 0).checkState() == QtCore.Qt.Checked:
                tot_pages += pages
                tot_mb += mb
                n += 1
        self.table.blockSignals(False)
        self.total.setText("%d chunks · %d pages · %.1f GB raw" % (n, tot_pages, tot_mb / 1000.0))
        many = len(self.rows) > self.MANY_CHUNKS
        self.advice.setText(
            "This project has %d chunks: texturing is lighter in a new project with the reference "
            "chunk (photos) and the blocks to texture." % len(self.rows) if many else "")
        self.b_new.setVisible(many)

    def check_all(self, on):
        for r, (_k, _a, ok, _m) in enumerate(self.rows):
            if ok:
                self.table.item(r, 0).setCheckState(QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)

    def untick_masters(self):
        for r, (_k, _a, ok, m) in enumerate(self.rows):
            if ok and m:
                self.table.item(r, 0).setCheckState(QtCore.Qt.Unchecked)

    def selected_keys(self):
        return [k for r, (k, _a, ok, _m) in enumerate(self.rows)
                if ok and self.table.item(r, 0).checkState() == QtCore.Qt.Checked]

    def new_project(self):
        doc = self.tool.doc
        names = [c.label for c in doc.chunks]
        ref, ok = QtWidgets.QInputDialog.getItem(self, "3DSC", "Reference chunk (the photos):", names, 0, False)
        if not ok:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "New project", "", "Metashape (*.psx)")
        if not path:
            return
        keys = set(self.selected_keys())
        chunks = [c for c in doc.chunks if c.label == ref or c.key in keys]
        try:
            self.tool.save_subset(chunks, path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "3DSC", "Not saved: %s" % e)
            return
        QtWidgets.QMessageBox.information(
            self, "3DSC", "Saved %d chunks in\n%s\n\nOpen it with File › Open and texture there. "
            "This project is unchanged." % (len(chunks), path))

    def options(self):
        o = self.params()
        o["chunk_keys"] = self.selected_keys()
        return o


# ── Tileset ──────────────────────────────────────────────────────────────────

SSE_PRESETS = (("desktop", 16), ("web", 24), ("mobile", 32))


class TilesetDialog(QtWidgets.QDialog):
    def __init__(self, tool, parent=None):
        super().__init__(parent)
        self.tool = tool
        doc = tool.doc
        self.setWindowTitle("3DSC · Tileset (Cesium 3D Tiles)")
        self.setMinimumWidth(620)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(note("The quadtree for the web, from the texturable master. The screen error "
                           "decides how many tiles a viewer draws: higher, fewer."))
        f = QtWidgets.QFormLayout()
        self.chunk = _chunk_combo(doc, doc.chunk)
        self.chunk.currentIndexChanged.connect(self.fill_tiled)
        f.addRow("Chunk", self.chunk)
        self.tiled = QtWidgets.QComboBox()
        f.addRow("Tiled model", self.tiled)
        self.build = QtWidgets.QCheckBox("build it now from the active model (texel from the D-D rule)")
        f.addRow("", self.build)
        srow = QtWidgets.QHBoxLayout()
        self.sse = _ispin(16, 1, 256)
        srow.addWidget(self.sse)
        for name, v in SSE_PRESETS:
            b = QtWidgets.QPushButton("%s %d" % (name, v))
            b.clicked.connect(lambda _=False, v=v: self.sse.setValue(v))
            srow.addWidget(b)
        f.addRow("Screen space error", srow)
        self.version = QtWidgets.QComboBox()
        self.version.addItems(["1.1", "1.0"])
        f.addRow("Tileset version", self.version)
        self.tex = QtWidgets.QComboBox()
        self.tex.addItem("KTX2 (GPU-compressed)", "KTX")
        self.tex.addItem("JPEG", "JPEG")
        f.addRow("Textures", self.tex)
        self.draco = QtWidgets.QCheckBox("Draco geometry compression")
        self.transform = QtWidgets.QCheckBox("use tileset transform")
        self.transform.setChecked(True)
        self.clip = QtWidgets.QCheckBox("clip to boundary shapes")
        self.clip.setChecked(True)
        self.depth = _ispin(5, 1, 20)
        f.addRow("", self.draco)
        f.addRow("", self.transform)
        f.addRow("", self.clip)
        f.addRow("Folder depth", self.depth)
        self.height = QtWidgets.QCheckBox("correct the heights onto EGM2008 for this export only "
                                          "(the project is not changed)")
        f.addRow("Heights", self.height)
        self.height_info = QtWidgets.QLabel()
        self.height_info.setWordWrap(True)
        f.addRow("", self.height_info)
        nrow = QtWidgets.QHBoxLayout()
        self.n_file = QtWidgets.QLineEdit()
        self.n_file.setPlaceholderText("N per marker, JSON {label: N} (optional if the geoid is installed)")
        b = QtWidgets.QPushButton("…")
        b.clicked.connect(self.pick_n)
        nrow.addWidget(self.n_file, 1)
        nrow.addWidget(b)
        f.addRow("EGM2008 N", nrow)
        orow = QtWidgets.QHBoxLayout()
        self.out = QtWidgets.QLineEdit()
        b = QtWidgets.QPushButton("…")
        b.clicked.connect(self.pick_out)
        orow.addWidget(self.out, 1)
        orow.addWidget(b)
        f.addRow("File (.3tz) or folder", orow)
        lay.addLayout(f)
        lay.addWidget(_buttons(self, "Export"))
        self.fill_tiled()

    def _chunk(self):
        return _chunk_by_key(self.tool.doc, self.chunk.currentData())

    def fill_tiled(self):
        self.tiled.clear()
        c = self._chunk()
        if c is None:
            return
        for i, t in enumerate(getattr(c, "tiled_models", []) or []):
            self.tiled.addItem(t.label or ("tiled model %d" % (i + 1)), t.key)
        self.build.setChecked(self.tiled.count() == 0)
        try:
            diag = self.tool.height_diagnosis(c)
        except Exception as e:
            diag = {"text": "height check failed: %s" % e, "suggest": False}
        self.height_info.setText(diag["text"])
        self.height.setChecked(bool(diag.get("suggest")))

    def pick_n(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "N per marker", "", "JSON (*.json)")
        if path:
            self.n_file.setText(path)

    def pick_out(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Tileset", "", "3D Tiles archive (*.3tz)")
        if path:
            self.out.setText(path)

    def accept(self):
        if not self.out.text():
            QtWidgets.QMessageBox.warning(self, "3DSC", "Choose where to write the tileset.")
            return
        super().accept()

    def options(self):
        return {"chunk_key": self.chunk.currentData(), "tiled_key": self.tiled.currentData(),
                "build": self.build.isChecked(), "screen_space_error": self.sse.value(),
                "tileset_version": self.version.currentText(), "texture": self.tex.currentData(),
                "draco": self.draco.isChecked(), "use_tileset_transform": self.transform.isChecked(),
                "clip_to_boundary": self.clip.isChecked(), "folder_depth": self.depth.value(),
                "fix_heights": self.height.isChecked(), "n_file": self.n_file.text(),
                "path": self.out.text()}


# ── Rename ───────────────────────────────────────────────────────────────────

class RenameDialog(QtWidgets.QDialog):
    def __init__(self, tool, parent=None):
        super().__init__(parent)
        self.tool = tool
        self.setWindowTitle("3DSC · Rename chunks")
        self.setMinimumWidth(560)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(note("Chunk names become the names of the exported files. "
                           "{n} = number, {name} = current name, {model} = model label."))
        f = QtWidgets.QFormLayout()
        self.pattern = QtWidgets.QLineEdit("{name}")
        self.start = _ispin(1, 0, 100000)
        self.digits = _ispin(3, 1, 6)
        self.find = QtWidgets.QLineEdit()
        self.repl = QtWidgets.QLineEdit()
        f.addRow("Pattern", self.pattern)
        f.addRow("Start at", self.start)
        f.addRow("Digits", self.digits)
        f.addRow("Replace", self.find)
        f.addRow("with", self.repl)
        lay.addLayout(f)
        self.list = QtWidgets.QTableWidget(0, 2)
        self.list.setHorizontalHeaderLabels(["Now", "After"])
        self.list.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.list.verticalHeader().setVisible(False)
        lay.addWidget(self.list, 1)
        for w in (self.pattern, self.find, self.repl):
            w.textChanged.connect(self.preview)
        for w in (self.start, self.digits):
            w.valueChanged.connect(self.preview)
        lay.addWidget(_buttons(self, "Rename"))
        self.preview()

    def names(self):
        out = []
        n = self.start.value()
        for c in self.tool.doc.chunks:
            if c.selected or not any(k.selected for k in self.tool.doc.chunks):
                model = (c.model.label if getattr(c, "model", None) is not None else "") or ""
                new = self.pattern.text().replace("{n}", str(n).zfill(self.digits.value())) \
                    .replace("{name}", c.label or "").replace("{model}", model)
                if self.find.text():
                    new = new.replace(self.find.text(), self.repl.text())
                out.append((c, new))
                n += 1
        return out

    def preview(self):
        rows = self.names()
        self.list.setRowCount(len(rows))
        for r, (c, new) in enumerate(rows):
            self.list.setItem(r, 0, QtWidgets.QTableWidgetItem(c.label))
            self.list.setItem(r, 1, QtWidgets.QTableWidgetItem(new))


# ── About ────────────────────────────────────────────────────────────────────

def about(version):
    box = QtWidgets.QMessageBox(_parent())
    box.setWindowTitle("3DSC for Metashape")
    box.setTextFormat(QtCore.Qt.RichText)
    box.setText(
        "<b>3DSC for Metashape %s</b><br>"
        "Photos → alignment → high mesh, cleaned → masters (geometric · texturable 10 000/m² · "
        "tileable 1 000/m²) → tileset from the texturable, blocks from the tileable → texture, "
        "LODs, normal maps → Blender.<br><br>%s<br><br>%s<br><br>"
        '<a href="https://www.extendedmatrix.org">extendedmatrix.org</a>'
        % (version, ms_dd.RULE_LINE, "<br>".join(ms_dd.BIBLIOGRAPHY)))
    box.exec_()
