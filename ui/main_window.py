import math
import os

import cadquery as cq
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAction, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox,
    QCheckBox, QMainWindow, QPushButton, QSlider, QStatusBar, QVBoxLayout, QWidget,
)

from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.IGESControl import IGESControl_Writer
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer

from .constants import MODEL_FILTERS, TPMS_TYPES
from .density import (
    T_MAX, T_MIN, SLIDER_STEPS, family_from_type, rho_range, rho_to_slider,
    rho_to_t, slider_to_rho, slider_to_t, t_to_rho, t_to_slider,
    t_to_w_bot, t_to_w_top,
)
from .generation import GenerateThread
from .geometry_io import import_model_shape
from .viewport import OCCTWidget
from .widgets import (
    BlueSelectedComboBox, divider, form_row, group_box, line_edit,
    make_slider_row, parameter_row,
)


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Explicit TPMS Structure Generator")
        self.resize(1100, 760)
        self._shape = None
        self._thread = None
        self._last_params = None
        self._model_path = ""
        self._model_shape = None
        self._model_bbox = None
        self._syncing = False
        # Internal w values (converted from t via param_w)
        self._w_bot = t_to_w_bot(0.20)
        self._w_top = t_to_w_top(0.20)
        self._build_ui()

    #  Build UI 
    def _build_ui(self):

        menubar = self.menuBar()
        menu_file = menubar.addMenu("File")
        act_exp = QAction("Export", self)
        act_exp.triggered.connect(self._on_export)
        menu_file.addAction(act_exp)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        panel = QWidget()
        panel.setFixedWidth(300)
        panel.setStyleSheet("background: #f5f6fa;")
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(10, 10, 10, 10)
        pv.setSpacing(8)
        pv.setAlignment(Qt.AlignTop)

        #   Lattice type 
        g_type = group_box("Lattice type")
        self.combo_subtype = BlueSelectedComboBox()
        self.combo_subtype.addItems(TPMS_TYPES)
        self.combo_subtype.currentTextChanged.connect(self._on_type_changed)
        self.combo_subtype._update_edit_color()
        g_type.layout().addWidget(self.combo_subtype)
        pv.addWidget(g_type)

        #   Array parameters 
        g_array = group_box("Array parameters")
        self.e_cell = line_edit("10")
        self.e_nx   = line_edit("1")
        self.e_ny   = line_edit("1")
        self.e_nz   = line_edit("1")
        self.row_cell = form_row("Unit cell size (mm):", self.e_cell)
        self.row_nx = form_row("X array number:", self.e_nx)
        self.row_ny = form_row("Y array number:", self.e_ny)
        self.row_nz = form_row("Z array number:", self.e_nz)
        g_array.layout().addWidget(self.row_cell)
        g_array.layout().addWidget(divider())
        g_array.layout().addWidget(self.row_nx)
        g_array.layout().addWidget(self.row_ny)
        g_array.layout().addWidget(self.row_nz)
        pv.addWidget(g_array)

        g_bool = group_box("Model filling")
        self.chk_bool = QCheckBox("Enable model clipping")
        self.chk_bool.stateChanged.connect(self._on_bool_changed)
        self.btn_import_model = QPushButton("Import model")
        self.btn_import_model.setFixedHeight(28)
        self.btn_import_model.clicked.connect(self._on_import_model)
        self.lbl_model_name = QLabel("No model imported")
        self.lbl_model_name.setWordWrap(True)
        self.lbl_model_name.setStyleSheet("color:#666; font-size:11px;")
        self.lbl_bbox = QLabel("BBox: -")
        self.lbl_bbox.setWordWrap(True)
        self.lbl_bbox.setStyleSheet("color:#1565C0; font-size:11px;")
        g_bool.layout().addWidget(self.chk_bool)
        g_bool.layout().addWidget(self.btn_import_model)
        g_bool.layout().addWidget(self.lbl_model_name)
        g_bool.layout().addWidget(self.lbl_bbox)
        self.lbl_fill_counts = QLabel("Auto cells: -")
        self.lbl_fill_counts.setWordWrap(True)
        self.lbl_fill_counts.setStyleSheet("color:#444; font-size:11px;")
        g_bool.layout().addWidget(self.lbl_fill_counts)
        pv.addWidget(g_bool)

        #   Design parameters 
        self.g_design = group_box("Design parameters")

        #  Shell 
        self.w_shell = QWidget()
        vs = QVBoxLayout(self.w_shell)
        vs.setContentsMargins(0, 0, 0, 0)
        vs.setSpacing(4)
        self.e_t = line_edit("0.5")
        vs.addWidget(form_row("Offset value:", self.e_t))
        self.g_design.layout().addWidget(self.w_shell)

        #  Solid 
        self.w_solid = QWidget()
        vso = QVBoxLayout(self.w_solid)
        vso.setContentsMargins(0, 0, 0, 0)
        vso.setSpacing(6)

        #  t 
        lbl_t_sec = QLabel("Thickness  t")
        lbl_t_sec.setStyleSheet(
            "color:#1565C0; font-size:11px; font-weight:bold; margin-top:2px;"
        )
        vso.addWidget(lbl_t_sec)

        self.e_thick = line_edit("0.20")
        t_slider_row, self.slider_t = make_slider_row(
            "#4A90D9",
            f"{T_MIN:.2f}",
            f"{T_MAX:.2f}",
        )
        vso.addWidget(parameter_row("t :", self.e_thick, t_slider_row))

        vso.addWidget(divider())

        #  * 
        self.lbl_rho_sec = QLabel("Relative density rho*")
        self.lbl_rho_sec.setStyleSheet(
            "color:#c07000; font-size:11px; font-weight:bold; margin-top:2px;"
        )
        vso.addWidget(self.lbl_rho_sec)

        self.e_rho = line_edit("0.20")

        # rho slider row with dynamic labels
        self._rho_lbl_min = QLabel("0.000")
        self._rho_lbl_max = QLabel("0.000")
        _lbl_style = "color: #999; font-size: 10px;"
        self._rho_lbl_min.setStyleSheet(_lbl_style)
        self._rho_lbl_max.setStyleSheet(_lbl_style)
        self._rho_lbl_min.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._rho_lbl_max.setAlignment(Qt.AlignLeft  | Qt.AlignVCenter)
        self._rho_lbl_min.setFixedWidth(36)
        self._rho_lbl_max.setFixedWidth(36)

        self.slider_rho = QSlider(Qt.Horizontal)
        self.slider_rho.setRange(0, SLIDER_STEPS)
        self.slider_rho.setFixedHeight(18)
        self.slider_rho.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px; background: #dde3ee; border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #e8a020; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 13px; height: 13px; margin: -5px 0;
                border-radius: 6px;
                background: #e8a020; border: 2px solid white;
            }
        """)

        rho_slider_row = QWidget()
        rho_h = QHBoxLayout(rho_slider_row)
        rho_h.setContentsMargins(0, 0, 0, 0)
        rho_h.setSpacing(6)
        rho_h.addWidget(self._rho_lbl_min)
        rho_h.addWidget(self.slider_rho, stretch=1)
        rho_h.addWidget(self._rho_lbl_max)

        vso.addWidget(parameter_row("rho* :", self.e_rho, rho_slider_row))

        self.g_design.layout().addWidget(self.w_solid)
        pv.addWidget(self.g_design)
        pv.removeWidget(g_bool)
        pv.insertWidget(pv.indexOf(self.g_design) + 1, g_bool)

        #   Buttons 
        self.btn_gen = QPushButton("Generate")
        self.btn_gen.setFixedHeight(40)
        self.btn_gen.setStyleSheet("""
            QPushButton {
                background: #4A90D9; color: white;
                border-radius: 6px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover    { background: #357abd; }
            QPushButton:disabled { background: #aac4e0; }
        """)
        self.btn_gen.clicked.connect(self._on_generate)

        self.btn_exp = QPushButton("Export")
        self.btn_exp.setFixedHeight(40)
        self.btn_exp.setEnabled(False)
        self.btn_exp.setStyleSheet("""
            QPushButton {
                background: #6c757d; color: white;
                border-radius: 6px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover    { background: #545b62; }
            QPushButton:disabled { background: #c0c4c8; }
        """)
        self.btn_exp.clicked.connect(self._on_export)

        pv.addWidget(self.btn_gen)
        pv.addWidget(self.btn_exp)
        pv.addStretch()

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #d0d8e8;")
        self.canvas = OCCTWidget()

        root.addWidget(panel)
        root.addWidget(sep)
        root.addWidget(self.canvas, stretch=1)

        self.status = QStatusBar()
        self.status.setStyleSheet(
            "QStatusBar { background: #f0f2f7; border-top: 1px solid #d0d8e8; }"
        )
        self.setStatusBar(self.status)
        self.status.showMessage(
            "Ready. Select the TPMS type, set parameters, then click Generate."
        )

        # Connect signals
        self.slider_t.valueChanged.connect(self._on_slider_t)
        self.e_thick.editingFinished.connect(self._on_edit_t)
        self.slider_rho.valueChanged.connect(self._on_slider_rho)
        self.e_rho.editingFinished.connect(self._on_edit_rho)
        self.e_nx.editingFinished.connect(self._sync_bool_cell_size_hint)
        self.e_ny.editingFinished.connect(self._sync_bool_cell_size_hint)
        self.e_nz.editingFinished.connect(self._sync_bool_cell_size_hint)
        self.e_cell.editingFinished.connect(self._sync_bool_cell_size_hint)

        self._on_type_changed(self.combo_subtype.currentText())

    def _on_bool_changed(self):
        enabled = self.chk_bool.isChecked()
        self.row_nx.setVisible(True)
        self.row_ny.setVisible(True)
        self.row_nz.setVisible(True)
        self.e_nx.setReadOnly(enabled)
        self.e_ny.setReadOnly(enabled)
        self.e_nz.setReadOnly(enabled)
        self._sync_bool_cell_size_hint()

    def _sync_bool_cell_size_hint(self):
        if not hasattr(self, "lbl_fill_counts") or self._model_bbox is None:
            return
        try:
            a = float(self.e_cell.text())
            if a <= 0:
                raise ValueError
        except ValueError:
            self.lbl_fill_counts.setText("Auto cells: invalid unit cell size")
            return
        bx, by, bz = self._model_bbox.xlen, self._model_bbox.ylen, self._model_bbox.zlen
        nx = max(1, math.ceil(bx / a))
        ny = max(1, math.ceil(by / a))
        nz = max(1, math.ceil(bz / a))
        if self.chk_bool.isChecked():
            self.e_nx.setText(str(nx))
            self.e_ny.setText(str(ny))
            self.e_nz.setText(str(nz))
        self.lbl_fill_counts.setText(
            f"Auto cells: {nx} x {ny} x {nz}  (a = {a:.3f} mm)"
        )

    def _on_import_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import fill model", "", MODEL_FILTERS)
        if not path:
            return
        try:
            shape = import_model_shape(path)
            bbox = shape.BoundingBox()
            self._model_path = path
            self._model_shape = shape
            self._model_bbox = bbox
            self.lbl_model_name.setText(os.path.basename(path))
            self.lbl_bbox.setText(
                f"BBox: {bbox.xlen:.3f} x {bbox.ylen:.3f} x {bbox.zlen:.3f} mm"
            )
            self.chk_bool.setChecked(True)
            self._sync_bool_cell_size_hint()
            self.canvas.display_shape(shape)
            self.status.showMessage(f"Imported model: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Import failed", str(e))
            self.status.showMessage("Model import failed")

    #  Type combo  show/hide
    def _on_type_changed(self, t: str):
        if not t:
            return
        self.w_shell.setVisible(t.endswith("-Shell"))
        self.w_solid.setVisible(t.endswith("-Solid"))
        if t.endswith("-Solid"):
            self._refresh_rho_range()
            self._sync_t_to_rho()

    def _current_family(self) -> str:
        return family_from_type(self.combo_subtype.currentText())

    def _refresh_rho_range(self):
        fam = self._current_family()
        if fam is None:
            return
        lo, hi = rho_range(fam)
        self._rho_lbl_min.setText(f"{lo:.3f}")
        self._rho_lbl_max.setText(f"{hi:.3f}")

    #  t <-> rho* two-way sync
    #  w = param_w(d) = 2.5*d + 0.5
    #  d_bot = -t/2    w_bot = -1.25*t + 0.5
    #  d_top =  t/2    w_top =  1.25*t + 0.5
    def _sync_t_to_rho(self):
        if self._syncing:
            return
        self._syncing = True
        try:
            t = float(self.e_thick.text())
            t = max(T_MIN, min(T_MAX, t))

            # Apply param_w mapping: w = 2.5*d + 0.5
            self._w_bot = t_to_w_bot(t)   # d = -t/2
            self._w_top = t_to_w_top(t)   # d =  t/2

            fam = self._current_family()
            if fam:
                rho = t_to_rho(fam, t) if t > 1e-9 else 0.0
                self.e_rho.setText(f"{rho:.4f}")
                self.slider_rho.setValue(rho_to_slider(fam, rho))
            self.slider_t.setValue(t_to_slider(t))
        except ValueError:
            pass
        finally:
            self._syncing = False

    def _sync_rho_to_t(self):
        if self._syncing:
            return
        self._syncing = True
        try:
            fam = self._current_family()
            if fam is None:
                return
            rho = float(self.e_rho.text())
            lo, hi = rho_range(fam)
            rho = max(lo, min(hi, rho))
            t   = rho_to_t(fam, rho)
            t   = max(T_MIN, min(T_MAX, t))

            self.e_thick.setText(f"{t:.4f}")

            # Apply param_w mapping: w = 2.5*d + 0.5
            self._w_bot = t_to_w_bot(t)   # d = -t/2
            self._w_top = t_to_w_top(t)   # d =  t/2

            self.slider_t.setValue(t_to_slider(t))
            self.slider_rho.setValue(rho_to_slider(fam, rho))
        except ValueError:
            pass
        finally:
            self._syncing = False

    def _on_slider_t(self, v: int):
        if self._syncing:
            return
        self.e_thick.setText(f"{slider_to_t(v):.4f}")
        self._sync_t_to_rho()

    def _on_edit_t(self):
        self._sync_t_to_rho()

    def _on_slider_rho(self, v: int):
        if self._syncing:
            return
        fam = self._current_family()
        if fam is None:
            return
        self.e_rho.setText(f"{slider_to_rho(fam, v):.4f}")
        self._sync_rho_to_t()

    def _on_edit_rho(self):
        self._sync_rho_to_t()

    #  Generate
    def _current_params(self) -> dict:
        t = self.combo_subtype.currentText()
        is_solid = t.endswith("-Solid")
        return {
            'type':      t,
            'cell_size': self.e_cell.text(),
            'nx':        self.e_nx.text(),
            'ny':        self.e_ny.text(),
            'nz':        self.e_nz.text(),
            't':         self.e_t.text(),
            'w_bot': f"{self._w_bot:.6f}" if is_solid else "0",
            'w_top': f"{self._w_top:.6f}" if is_solid else "0",
            'bool_enabled': self.chk_bool.isChecked(),
            'model_path': self._model_path,
        }

    def _on_generate(self):
        t = self.combo_subtype.currentText()
        is_solid = t.endswith("-Solid")
        if self.chk_bool.isChecked() and not self._model_path:
            QMessageBox.warning(self, "Missing model", "Please import a model before Bool generation.")
            return
        if self.chk_bool.isChecked():
            self._sync_bool_cell_size_hint()
        params = {
            'type':      t,
            'cell_size': self.e_cell.text(),
            'nx':        self.e_nx.text(),
            'ny':        self.e_ny.text(),
            'nz':        self.e_nz.text(),
            't':         self.e_t.text(),
            'w_bot': f"{self._w_bot:.6f}" if is_solid else "0",
            'w_top': f"{self._w_top:.6f}" if is_solid else "0",
            'bool_enabled': self.chk_bool.isChecked(),
            'model_path': self._model_path,
        }
        self.btn_gen.setEnabled(False)
        self.btn_exp.setEnabled(False)
        self.status.showMessage(f"Generating {t}, please wait...")
        self._thread = GenerateThread(params)
        self._thread.finished.connect(self._on_gen_done)
        self._thread.error.connect(self._on_gen_error)
        self._last_params = dict(params)   # Cache the generated parameter set.
        self._thread.start()

    def _on_gen_done(self, elapsed: float):
        self._shape = self._thread.result
        self.canvas.display_shape(self._shape)
        self.btn_gen.setEnabled(True)
        self.btn_exp.setEnabled(True)
        self.status.showMessage(f"Done. Elapsed: {elapsed:.8f} s")

    def _on_gen_error(self, msg: str):
        self.btn_gen.setEnabled(True)
        self.status.showMessage("Generation failed")
        QMessageBox.critical(self, "Error", msg)

    #  Export
    def _on_export(self):
        from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
        from OCP.IGESControl import IGESControl_Writer
        from OCP.BRepMesh import BRepMesh_IncrementalMesh

        if self._shape is None:
            QMessageBox.warning(self, "Notice", "Please generate the lattice structure first!")
            return

        # Parameter-change guard.
        if self._last_params is not None and self._current_params() != self._last_params:
            QMessageBox.warning(
                self, "Parameters Changed",
                "The parameters have been modified since the last generation.\n"
                "Please click Generate again before exporting."
            )
            return

        filters = "STEP Files (*.step);;IGES Files (*.igs);;STL Files (*.stl)"
        path, sel = QFileDialog.getSaveFileName(self, "Export", "lattice", filters)
        if not path:
            return

        try:
            wp = (
                self._shape.val().wrapped
                if isinstance(self._shape, cq.Workplane)
                else self._shape.wrapped
            )

            if "step" in sel.lower():
                if not path.lower().endswith(".step"):
                    path += ".step"

                writer = STEPControl_Writer()
                writer.Transfer(wp, STEPControl_AsIs)
                status = writer.Write(path)

                if not os.path.exists(path):
                    raise RuntimeError(f"STEP export failed, file was not created: {path}")

                file_size_mb = os.path.getsize(path) / 1024 / 1024
                print('The STEP file size is:  %s MB' % file_size_mb)

            elif "iges" in sel.lower():
                if not path.lower().endswith(".igs"):
                    path += ".igs"
                writer = IGESControl_Writer()
                writer.AddShape(wp)
                writer.Write(path)

            else:
                if not path.lower().endswith(".stl"):
                    path += ".stl"
                BRepMesh_IncrementalMesh(wp, 0.05, False, 0.3, True).Perform()
                if isinstance(self._shape, cq.Workplane):
                    self._shape.val().exportStl(path)
                else:
                    self._shape.exportStl(path)

            self.status.showMessage(f"Exported to: {path}")

        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))
