"""The dialog of the appender between projects (PySide2, as shipped with Metashape)."""

from __future__ import annotations

import os

import Metashape as ps
from PySide2 import QtCore, QtGui, QtWidgets

import ms_appender as ma
import ms_append_ms as am


def _crs_name(wkt):
    if not wkt:
        return "none"
    return wkt.split('"')[1] if '"' in wkt else wkt[:40]


class AppendDialog(QtWidgets.QDialog):
    def __init__(self, target_chunk, parent=None):
        super().__init__(parent)
        self.target = target_chunk
        self.src_doc = None
        self.src_info = []
        self.setWindowTitle("3DSC · Append photos from another project")
        self.setMinimumWidth(620)
        lay = QtWidgets.QVBoxLayout(self)

        # source
        box = QtWidgets.QGroupBox("Source")
        f = QtWidgets.QFormLayout(box)
        row = QtWidgets.QHBoxLayout()
        self.path = QtWidgets.QLineEdit()
        self.path.setReadOnly(True)
        b = QtWidgets.QPushButton("Browse…")
        b.clicked.connect(self.browse)
        row.addWidget(self.path)
        row.addWidget(b)
        f.addRow("Project", row)
        self.chunk = QtWidgets.QComboBox()
        self.chunk.currentIndexChanged.connect(self.chunk_changed)
        f.addRow("Chunk", self.chunk)
        self.r_selected = QtWidgets.QRadioButton("Selected cameras")
        self.r_group = QtWidgets.QRadioButton("Camera group")
        self.r_enabled = QtWidgets.QRadioButton("Enabled cameras")
        self.r_all = QtWidgets.QRadioButton("All cameras")
        self.group = QtWidgets.QComboBox()
        self.r_group.setChecked(True)
        g = QtWidgets.QGridLayout()
        g.addWidget(self.r_selected, 0, 0)
        g.addWidget(self.r_group, 1, 0)
        g.addWidget(self.group, 1, 1)
        g.addWidget(self.r_enabled, 2, 0)
        g.addWidget(self.r_all, 3, 0)
        f.addRow("Photos", g)
        lay.addWidget(box)

        # target
        box = QtWidgets.QGroupBox("Target")
        f = QtWidgets.QFormLayout(box)
        f.addRow("Chunk", QtWidgets.QLabel(f"{target_chunk.label} — {len(target_chunk.cameras)} cameras (active chunk)"))
        self.group_label = QtWidgets.QLineEdit()
        f.addRow("New camera group", self.group_label)
        lay.addWidget(box)

        # what comes along
        box = QtWidgets.QGroupBox("What comes along")
        f = QtWidgets.QFormLayout(box)
        self.calib = QtWidgets.QComboBox()
        self.calib.addItem("Copy the source calibration groups (as initial values)", "copy")
        self.calib.addItem("Reuse the target calibration group with the same name", "reuse")
        self.calib.addItem("New groups from EXIF (Metashape default)", "exif")
        f.addRow("Calibration", self.calib)
        self.fix = QtWidgets.QCheckBox("Fix the copied calibration")
        f.addRow("", self.fix)
        self.markers = QtWidgets.QComboBox()
        self.markers.addItem("Merge into the markers with the same name", "merge")
        self.markers.addItem("Create new markers, with a prefix", "new")
        self.markers.addItem("Leave the markers in the source", "none")
        self.markers.currentIndexChanged.connect(self.update_hint)
        f.addRow("Markers", self.markers)
        self.prefix = QtWidgets.QLineEdit()
        f.addRow("Prefix of new markers", self.prefix)
        self.mref = QtWidgets.QCheckBox("Bring the reference coordinates of new markers")
        self.mref.setChecked(True)
        f.addRow("", self.mref)
        self.hint = QtWidgets.QLabel()
        self.hint.setWordWrap(True)
        f.addRow("", self.hint)
        self.masks = QtWidgets.QCheckBox("Masks")
        self.masks.setChecked(True)
        self.camref = QtWidgets.QCheckBox("Camera reference (GPS positions and angles)")
        self.enabled = QtWidgets.QCheckBox("Keep enabled / disabled as in the source")
        self.enabled.setChecked(True)
        self.dedupe = QtWidgets.QCheckBox("Skip photos already in the target also by content (slower)")
        for w in (self.masks, self.camref, self.enabled, self.dedupe):
            f.addRow("", w)
        lay.addWidget(box)

        note = QtWidgets.QLabel("Nothing is aligned here. Afterwards: Workflow › Align Photos with "
                                "«Reset current alignment» unchecked, then Optimize Cameras.")
        note.setWordWrap(True)
        lay.addWidget(note)
        bb = QtWidgets.QDialogButtonBox()
        self.ok = bb.addButton("Append", QtWidgets.QDialogButtonBox.AcceptRole)
        bb.addButton(QtWidgets.QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.ok.setEnabled(False)
        lay.addWidget(bb)

    def browse(self):
        p, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Metashape project", os.path.dirname(ps.app.document.path or ""),
                                                     "Metashape projects (*.psx *.psz)")
        if not p:
            return
        if os.path.abspath(p) == os.path.abspath(ps.app.document.path or ""):
            QtWidgets.QMessageBox.warning(self, "3DSC", "That is the open project: choose another one.")
            return
        self.path.setText(p)
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
        try:
            self.src_doc = am.open_source(p)
            self.src_info = am.describe_source(self.src_doc)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.chunk.clear()
        for c in self.src_info:
            self.chunk.addItem(f"{c['label']} — {c['cameras']} cameras", c["key"])
        self.ok.setEnabled(bool(self.src_info))

    def current(self):
        k = self.chunk.currentData()
        return next((c for c in self.src_info if c["key"] == k), None)

    def chunk_changed(self, _i):
        c = self.current()
        if c is None:
            return
        self.r_selected.setText(f"Selected cameras ({c['selected']})")
        self.r_enabled.setText(f"Enabled cameras ({c['enabled']})")
        self.r_all.setText(f"All cameras ({c['cameras']})")
        self.group.clear()
        for g in c["groups"]:
            self.group.addItem(f"{g['label']} ({g['cameras']})", g["key"])
        self.r_group.setEnabled(bool(c["groups"]))
        if not c["groups"] and self.r_group.isChecked():
            self.r_selected.setChecked(True)
        self.masks.setText(f"Masks ({c['masks']} in the source)")
        self.group_label.setText(ma.default_group_label(self.path.text(), c["label"]))
        if not self.prefix.text():
            self.prefix.setText(c["label"] + "_")
        self.update_hint()

    def update_hint(self, *_):
        c = self.current()
        if c is None:
            return
        tc = am.marker_crs(self.target)
        tgt = tc.wkt if tc else None
        src = None
        if self.src_doc is not None:
            sch = next(x for x in self.src_doc.chunks if x.key == c["key"])
            sc = am.marker_crs(sch)
            src = sc.wkt if sc else None
        a = ma.reference_action(src, tgt)
        text = {"copy": "same coordinate system: the coordinates are copied as they are.",
                "transform": "different systems: the coordinates are transformed into the target system.",
                "copy_disabled": "one of the two systems is local: the coordinates come along but are left "
                                 "unchecked, so they do not pull the target."}[a]
        self.hint.setText(f"Markers: source {_crs_name(src)} → target {_crs_name(tgt)}; {text}")

    def options(self):
        sel = ("selected" if self.r_selected.isChecked() else "group" if self.r_group.isChecked()
               else "enabled" if self.r_enabled.isChecked() else "all")
        return {"selection": sel, "group_key": self.group.currentData(),
                "group_label": self.group_label.text().strip() or None,
                "calibration": self.calib.currentData(), "fix_calibration": self.fix.isChecked(),
                "markers": self.markers.currentData(), "marker_prefix": self.prefix.text(),
                "marker_reference": self.mref.isChecked(), "masks": self.masks.isChecked(),
                "camera_reference": self.camref.isChecked(), "keep_enabled": self.enabled.isChecked(),
                "dedupe_by_hash": self.dedupe.isChecked()}


def run_append_dialog():
    doc = ps.app.document
    chunk = doc.chunk
    if chunk is None:
        ps.app.messageBox("Open a project and make the target chunk active first.")
        return
    parent = QtWidgets.QApplication.instance().activeWindow()
    dlg = AppendDialog(chunk, parent)
    if dlg.exec_() != QtWidgets.QDialog.Accepted:
        return
    try:
        rep = am.append_from_project(chunk, dlg.path.text(), dlg.chunk.currentData(), dlg.options(),
                                     progress=lambda m: (print("[3DSC append] " + m), ps.app.update()))
    except Exception as e:
        ps.app.messageBox(f"Append stopped: {e}")
        return
    c = rep["counts"]
    ps.app.messageBox(
        f"Group «{rep['group_label']}»: {c['cameras']} photos added"
        f" ({c['skipped']} already in the project, {c['missing_photo']} with the photo missing).\n"
        f"Markers: {c['markers_new']} new, {c['markers_merged']} merged, {c['projections']} projections.\n"
        f"Masks: {c['masks']}. Camera reference: {c['camera_reference']}.\n\n"
        "Next: select the group, Workflow › Align Photos with «Reset current alignment» unchecked, "
        "then Tools › Optimize Cameras. The project is not saved yet.")
