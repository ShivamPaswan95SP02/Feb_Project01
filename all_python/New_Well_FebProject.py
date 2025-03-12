import sys
import os
import lasio
import numpy as np
import pandas as pd
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QMainWindow, QFileDialog, QDockWidget, QListWidget,
                             QListWidgetItem, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
                             QComboBox, QPushButton, QCheckBox, QSpinBox, QScrollArea, QAction, QStackedWidget,
                             QMenu, QDialog, QFormLayout, QDialogButtonBox, QColorDialog)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from PyQt5.QtGui import QIcon

# ----------------------------------------------------------------------
# Custom Well List Widget: Toggles check state on click outside checkbox area.
# ----------------------------------------------------------------------
class WellListWidget(QListWidget):
    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if item is not None:
            rect = self.visualItemRect(item)
            # Assume the checkbox is within the left 20 pixels.
            if event.pos().x() > rect.left() + 20:
                if item.checkState() == Qt.Checked:
                    item.setCheckState(Qt.Unchecked)
                else:
                    item.setCheckState(Qt.Checked)
                return
        super().mousePressEvent(event)

# ----------------------------------------------------------------------
# PrimaryCurveControl: Always visible control for the primary curve.
# ----------------------------------------------------------------------
class PrimaryCurveControl(QWidget):
    changed = QtCore.pyqtSignal()
    
    def __init__(self, curves, parent=None):
        super().__init__(parent)
        self.curves = curves
        self.initUI()
    
    def initUI(self):
        layout = QHBoxLayout()
        layout.addWidget(QLabel("Primary:"))
        self.curve_combo = QComboBox()
        self.curve_combo.addItems(["Select Primary Curve"] + self.curves)
        self.curve_combo.currentIndexChanged.connect(self.changed)
        layout.addWidget(self.curve_combo)
        # Color selection (only for primary)
        layout.addWidget(QLabel("Color:"))
        self.color_combo = QComboBox()
        self.color_combo.addItems(["black", "red", "blue", "green", "orange"])
        self.color_combo.currentIndexChanged.connect(self.changed)
        layout.addWidget(self.color_combo)
        # Line style selection
        layout.addWidget(QLabel("Style:"))
        self.style_combo = QComboBox()
        self.style_combo.addItems(["-", "--", ":", "-."])
        self.style_combo.currentIndexChanged.connect(self.changed)
        layout.addWidget(self.style_combo)
        # Line width selection
        layout.addWidget(QLabel("Width:"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 10)
        self.width_spin.setValue(1)
        self.width_spin.valueChanged.connect(self.changed)
        layout.addWidget(self.width_spin)
        self.setLayout(layout)
    
    def get_settings(self):
        curve = self.curve_combo.currentText()
        if curve == "Select Primary Curve":
            return None
        return {
            "curve": curve,
            "color": self.color_combo.currentText(),
            "style": self.style_combo.currentText(),
            "width": self.width_spin.value(),
            "primary": True
        }

# ----------------------------------------------------------------------
# TrackControl Class: Combines a primary curve control and secondary curves list.
# ----------------------------------------------------------------------
class TrackControl(QWidget):
    changed = QtCore.pyqtSignal()
    deleteRequested = QtCore.pyqtSignal(object)

    def __init__(self, number, curves):
        super().__init__()
        self.number = number
        self.curves = curves
        # List for secondary curves (each is a dict without color)
        self.secondary_curve_settings = []
        self.initUI()

    def initUI(self):
        main_layout = QVBoxLayout()
        # Top row: Track label and Delete Track button.
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel(f"Track {self.number}"))
        self.btn_delete = QPushButton("X")
        self.btn_delete.clicked.connect(self.handle_delete)
        top_layout.addWidget(self.btn_delete)
        main_layout.addLayout(top_layout)
        
        # Primary curve control (always visible)
        self.primary_control = PrimaryCurveControl(self.curves)
        self.primary_control.changed.connect(self.changed)
        main_layout.addWidget(self.primary_control)
        
        # Secondary curves control
        sec_layout = QVBoxLayout()
        sec_layout.addWidget(QLabel("Secondary Curves:"))
        self.secondary_list = QListWidget()
        sec_layout.addWidget(self.secondary_list)
        btn_layout = QHBoxLayout()
        self.btn_add_secondary = QPushButton("Add Secondary")
        self.btn_add_secondary.clicked.connect(self.add_secondary)
        btn_layout.addWidget(self.btn_add_secondary)
        self.btn_remove_secondary = QPushButton("Remove Secondary")
        self.btn_remove_secondary.clicked.connect(self.remove_secondary)
        btn_layout.addWidget(self.btn_remove_secondary)
        sec_layout.addLayout(btn_layout)
        main_layout.addLayout(sec_layout)
        
        self.setLayout(main_layout)

    def add_secondary(self):
        item, ok = QtWidgets.QInputDialog.getItem(self, "Select Secondary Curve", "Curve:", self.curves, 0, False)
        if ok and item:
            # Secondary curves do not include a color option.
            settings = {"curve": item, "style": "-", "width": 1, "primary": False}
            self.secondary_curve_settings.append(settings)
            self.secondary_list.addItem(item)
            self.changed.emit()

    def remove_secondary(self):
        selected_items = self.secondary_list.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            row = self.secondary_list.row(item)
            self.secondary_list.takeItem(row)
            del self.secondary_curve_settings[row]
        self.changed.emit()

    def get_selected_curves(self):
        settings_list = []
        primary_settings = self.primary_control.get_settings()
        if primary_settings is not None:
            settings_list.append(primary_settings)
        settings_list.extend(self.secondary_curve_settings)
        return settings_list

    def handle_delete(self):
        self.deleteRequested.emit(self)

# ----------------------------------------------------------------------
# CurveSettingsDialog: Dialog to modify a curve's appearance.
# For primary curves the dialog shows the color option; for secondary curves it does not.
# ----------------------------------------------------------------------
class CurveSettingsDialog(QDialog):
    def __init__(self, line, is_primary=True, parent=None):
        super().__init__(parent)
        self.line = line
        self.is_primary = is_primary
        self.setWindowTitle("Edit Curve Settings")
        self.initUI()

    def initUI(self):
        layout = QFormLayout(self)
        if self.is_primary:
            self.color_button = QPushButton()
            self.current_color = self.line.get_color()
            self.color_button.setStyleSheet(f"background-color: {self.current_color}")
            self.color_button.clicked.connect(self.chooseColor)
            layout.addRow("Color:", self.color_button)
        self.style_combo = QComboBox()
        self.style_combo.addItems(["-", "--", ":", "-."])
        current_style = self.line.get_linestyle()
        index = self.style_combo.findText(current_style)
        if index != -1:
            self.style_combo.setCurrentIndex(index)
        layout.addRow("Style:", self.style_combo)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 10)
        self.width_spin.setValue(int(self.line.get_linewidth()))
        layout.addRow("Width:", self.width_spin)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def chooseColor(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.current_color = color.name()
            self.color_button.setStyleSheet(f"background-color: {self.current_color}")

    def getSettings(self):
        settings = {
            "style": self.style_combo.currentText(),
            "width": self.width_spin.value()
        }
        if self.is_primary:
            settings["color"] = self.current_color
        return settings

# ----------------------------------------------------------------------
# FigureWidget Class: Embeds a matplotlib figure, handles zoom/pan, and right-click editing.
# ----------------------------------------------------------------------
class FigureWidget(QWidget):
    zoomChanged = QtCore.pyqtSignal(object)  # Signal emitted after a zoom event

    def __init__(self, well_name, parent=None):
        super().__init__(parent)
        self.well_name = well_name
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.zoom_mode = "Pan"  # Default zoom mode
        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        # Variables for custom zoom/pan.
        self._dragging = False
        self._press_event = None
        self._rect = None  # For rectangular zoom
        self._zoom_history = []  # Stack to store zoom states

        # Connect mouse events.
        self.canvas.mpl_connect("button_press_event", self.onMousePress)
        self.canvas.mpl_connect("motion_notify_event", self.onMouseMove)
        self.canvas.mpl_connect("button_release_event", self.onMouseRelease)
        self.canvas.mpl_connect("scroll_event", self.onScroll)
        self.canvas.mpl_connect("pick_event", self.onPick)

    def onZoomModeChanged(self, mode):
        self.zoom_mode = mode
        if mode == "Pan":
            self.canvas.setCursor(Qt.OpenHandCursor)
        elif mode == "Rectangular":
            self.canvas.setCursor(Qt.CrossCursor)
        elif mode == "Horizontal":
            self.canvas.setCursor(Qt.SizeHorCursor)
        elif mode == "Vertical":
            self.canvas.setCursor(Qt.SizeVerCursor)
        else:
            self.canvas.setCursor(Qt.ArrowCursor)

    def onMousePress(self, event):
        if event.inaxes is None:
            return
        if self.zoom_mode == "Rectangular":
            self._dragging = True
            self._press_event = event
            ax = event.inaxes
            self._rect = Rectangle((event.xdata, event.ydata), 0, 0,
                                   fill=False, edgecolor='red', linestyle='--')
            ax.add_patch(self._rect)
            self.canvas.draw()
        elif self.zoom_mode == "Pan":
            self._dragging = True
            self._press_event = event

    def onMouseMove(self, event):
        if not self._dragging or event.inaxes is None or self._press_event is None:
            return
        ax = event.inaxes
        if self.zoom_mode == "Pan":
            dx = event.xdata - self._press_event.xdata
            dy = event.ydata - self._press_event.ydata
            if event.key == "control":
                y0, y1 = ax.get_ylim()
                ax.set_ylim(y0 - dy, y1 - dy)
            else:
                x0, x1 = ax.get_xlim()
                ax.set_xlim(x0 - dx, x1 - dx)
            self.canvas.draw()
            self._press_event = event
        elif self.zoom_mode == "Rectangular" and self._rect is not None:
            x0, y0 = self._press_event.xdata, self._press_event.ydata
            x1, y1 = event.xdata, event.ydata
            xmin = min(x0, x1)
            ymin = min(y0, y1)
            width = abs(x1 - x0)
            height = abs(y1 - y0)
            self._rect.set_xy((xmin, ymin))
            self._rect.set_width(width)
            self._rect.set_height(height)
            self.canvas.draw()

    def onMouseRelease(self, event):
        if not self._dragging or event.inaxes is None:
            return
        ax = event.inaxes
        if self.zoom_mode == "Rectangular" and self._rect is not None:
            x0, y0 = self._press_event.xdata, self._press_event.ydata
            x1, y1 = event.xdata, event.ydata
            xmin, xmax = sorted([x0, x1])
            ymin, ymax = sorted([y0, y1])
            ax.set_xlim(xmin, xmax)
            ax.set_ylim(ymin, ymax)
            self._rect.remove()
            self._rect = None
            self.canvas.draw()
        self._dragging = False
        self._press_event = None
        self.recordZoomState()
        self.zoomChanged.emit(self)

    def onScroll(self, event):
        if event.inaxes is None:
            return
        ax = event.inaxes
        base_scale = 1.1
        if event.button == "up":
            scale_factor = 1 / base_scale
        elif event.button == "down":
            scale_factor = base_scale
        else:
            scale_factor = 1

        if self.zoom_mode == "Horizontal":
            if event.key == "control":
                y0, y1 = ax.get_ylim()
                ydata = event.ydata
                new_range = (y1 - y0) * scale_factor
                ax.set_ylim([ydata - new_range / 2, ydata + new_range / 2])
            else:
                x0, x1 = ax.get_xlim()
                xdata = event.xdata
                new_range = (x1 - x0) * scale_factor
                ax.set_xlim([xdata - new_range / 2, xdata + new_range / 2])
            self.canvas.draw()
        elif self.zoom_mode == "Vertical":
            if event.key == "control":
                x0, x1 = ax.get_xlim()
                xdata = event.xdata
                new_range = (x1 - x0) * scale_factor
                ax.set_xlim([xdata - new_range / 2, xdata + new_range / 2])
            else:
                y0, y1 = ax.get_ylim()
                ydata = event.ydata
                new_range = (y1 - y0) * scale_factor
                ax.set_ylim([ydata - new_range / 2, ydata + new_range / 2])
            self.canvas.draw()
        else:
            self.canvas.draw()
        self.recordZoomState()
        self.zoomChanged.emit(self)

    def recordZoomState(self):
        state = []
        for ax in self.figure.axes:
            state.append((ax.get_xlim(), ax.get_ylim()))
        self._zoom_history.append(state)

    def undoZoom(self):
        if len(self._zoom_history) > 1:
            self._zoom_history.pop()
            prev_state = self._zoom_history[-1]
            for ax, limits in zip(self.figure.axes, prev_state):
                ax.set_xlim(limits[0])
                ax.set_ylim(limits[1])
            self.canvas.draw()

    def resetZoom(self):
        if not hasattr(self, '_initial_limits'):
            return
        for ax, limits in zip(self.figure.axes, self._initial_limits):
            ax.set_xlim(limits[0])
            ax.set_ylim(limits[1])
        self.canvas.draw()
        self._zoom_history = [self._initial_limits.copy()]

    def update_plot(self, data, tracks, well_name):
        self.figure.clear()
        n_tracks = len(tracks)
        if n_tracks == 0:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, "No track controls", horizontalalignment='center', verticalalignment='center')
        else:
            axes = self.figure.subplots(1, n_tracks, sharey=True)
            if n_tracks == 1:
                axes = [axes]
            depth = data['DEPT']
            for idx, (ax, track) in enumerate(zip(axes, tracks)):
                curve_settings_list = track.get_selected_curves()
                if not curve_settings_list:
                    ax.text(0.5, 0.5, "No curve added", horizontalalignment='center', verticalalignment='center')
                    continue
                for settings in curve_settings_list:
                    if settings["curve"] in data.columns:
                        # For primary curves, use the specified color; for secondary, default to black.
                        color = settings.get("color", "black")
                        line, = ax.plot(data[settings["curve"]], depth,
                                        color=color,
                                        linewidth=settings["width"],
                                        linestyle=settings["style"],
                                        picker=5)
                        line.custom_settings = settings  # Tag the line with its settings.
                ax.set_xlabel(", ".join([s["curve"] for s in curve_settings_list if "curve" in s]))
                ax.set_ylabel("Depth")
                ax.grid(True)
                ax.set_ylim(depth.max(), depth.min())
        self.figure.subplots_adjust(wspace=0.1)
        self.canvas.draw()
        self._initial_limits = []
        state = []
        for ax in self.figure.axes:
            limits = (ax.get_xlim(), ax.get_ylim())
            self._initial_limits.append(limits)
            state.append(limits)
        self._zoom_history = [state]

    def onPick(self, event):
        if not hasattr(event.artist, "get_linestyle"):
            return
        if event.mouseevent.button != 3:
            return
        line = event.artist
        # Determine whether the picked line is primary or secondary.
        is_primary = line.custom_settings.get("primary", False)
        menu = QMenu(self)
        change_action = menu.addAction("Change Settings")
        delete_action = menu.addAction("Delete Curve")
        action = menu.exec_(event.mouseevent.guiEvent.globalPos())
        if action == change_action:
            dialog = CurveSettingsDialog(line, is_primary, self)
            if dialog.exec_() == QDialog.Accepted:
                new_settings = dialog.getSettings()
                line.set_linestyle(new_settings["style"])
                line.set_linewidth(new_settings["width"])
                if is_primary:
                    line.set_color(new_settings["color"])
                    line.custom_settings.update(new_settings)
                else:
                    line.custom_settings.update(new_settings)
                self.canvas.draw()
        elif action == delete_action:
            line.remove()
            self.canvas.draw()
        self.recordZoomState()
        self.zoomChanged.emit(self)

# ----------------------------------------------------------------------
# WellLogViewer Class: Main window holding controls and figure widgets.
# ----------------------------------------------------------------------
class WellLogViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.wells = {}  # well name -> {'data': DataFrame, 'path': filepath}
        self.tracks = []  # list of TrackControl widgets
        self.track_buttons = []  # buttons for track selection
        self.figure_widgets = {}  # well name -> FigureWidget
        self.sync_zoom_enabled = False
        self.initUI()
        self.setWindowIcon(QIcon('ongc.png'))

    def initUI(self):
        self.setWindowTitle('WellVision ONGC')
        self.setGeometry(100, 100, 1200, 800)
        
        # Toolbar for global zoom controls.
        self.toolbar = QtWidgets.QToolBar("Zoom Controls", self)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)
        spacer = QWidget()
        spacer.setFixedWidth(20)
        self.toolbar.addWidget(spacer)
        self.globalZoomCombo = QComboBox()
        self.globalZoomCombo.addItems(["Pan", "Rectangular", "Horizontal", "Vertical"])
        self.globalZoomCombo.currentTextChanged.connect(self.onGlobalZoomModeChanged)
        self.toolbar.addWidget(QLabel("Global Zoom Mode: "))
        self.toolbar.addWidget(self.globalZoomCombo)
        spacer = QWidget()
        spacer.setFixedWidth(20)
        self.toolbar.addWidget(spacer)
        self.syncZoomCheck = QCheckBox("Sync Zoom")
        self.syncZoomCheck.toggled.connect(self.onSyncZoomToggled)
        self.toolbar.addWidget(self.syncZoomCheck)
        self.toolbar.addSeparator()
        btn_undo_zoom = QPushButton("Undo Zoom")
        btn_undo_zoom.clicked.connect(self.undoZoom)
        self.toolbar.addWidget(btn_undo_zoom)
        self.toolbar.addSeparator()
        btn_reset_zoom = QPushButton("Reset Zoom")
        btn_reset_zoom.clicked.connect(self.resetZoom)
        self.toolbar.addWidget(btn_reset_zoom)
        
        # Central scroll area for figure widgets.
        self.figure_scroll = QScrollArea()
        self.figure_container = QWidget()
        self.figure_layout = QHBoxLayout(self.figure_container)
        self.figure_container.setLayout(self.figure_layout)
        self.figure_scroll.setWidgetResizable(True)
        self.figure_scroll.setWidget(self.figure_container)
        self.setCentralWidget(self.figure_scroll)
        
        # Menubar and File menu.
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        load_folder_action = QAction("Load LAS Folder", self)
        load_folder_action.triggered.connect(self.load_las_folder)
        file_menu.addAction(load_folder_action)
        toggle_controls_action = QAction("Toggle Controls", self)
        toggle_controls_action.triggered.connect(self.toggle_controls)
        menubar.addAction(toggle_controls_action)
        menubar.addMenu("Settings")
        menubar.addMenu("Show DataTop")
        
        # Dock widget for controls.
        self.dock = QDockWidget("Controls", self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        dock_widget = QWidget()
        dock_layout = QVBoxLayout()
        # Use custom WellListWidget for loaded wells.
        self.well_list = WellListWidget()
        self.well_list.itemChanged.connect(self.update_plot)
        dock_layout.addWidget(QLabel("Loaded Wells:"))
        dock_layout.addWidget(self.well_list)
        # Track controls.
        self.track_selector_widget = QWidget()
        self.track_selector_layout = QHBoxLayout(self.track_selector_widget)
        dock_layout.addWidget(QLabel("Track Selection:"))
        dock_layout.addWidget(self.track_selector_widget)
        self.track_stack = QStackedWidget()
        dock_layout.addWidget(self.track_stack)
        btn_add_track = QPushButton("Add Track")
        btn_add_track.clicked.connect(self.add_track)
        dock_layout.addWidget(btn_add_track)
        dock_widget.setLayout(dock_layout)
        self.dock.setWidget(dock_widget)
        self.statusBar().showMessage('Ready')

    def onGlobalZoomModeChanged(self, mode):
        for widget in self.figure_widgets.values():
            widget.onZoomModeChanged(mode)

    def onSyncZoomToggled(self, checked):
        self.sync_zoom_enabled = checked
        if checked:
            self.sync_zoom()

    def toggle_controls(self):
        self.dock.setVisible(not self.dock.isVisible())

    def load_las_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder Containing LAS Files")
        if folder:
            for filename in os.listdir(folder):
                if filename.lower().endswith(".las"):
                    full_path = os.path.join(folder, filename)
                    self.load_las_file(full_path)
            self.update_plot()
    
    def load_las_file(self, path):
        try:
            las = lasio.read(path)
            df = las.df()
            df.reset_index(inplace=True)
            df.dropna(inplace=True)
            depth_col = df.index.name if df.index.name else next((col for col in df.columns if col.upper() in ["DEPT", "DEPTH", "MD"]), None)
            if depth_col is None:
                raise ValueError("No valid depth column found.")
            df.rename(columns={depth_col: "DEPT"}, inplace=True)
            well_name = las.well.WELL.value if las.well.WELL.value else os.path.basename(path)
            if well_name in self.wells:
                return
            self.wells[well_name] = {'data': df, 'path': path}
            item = QListWidgetItem(well_name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.well_list.addItem(item)
            self.statusBar().showMessage(f"Loaded: {well_name}")
        except Exception as e:
            self.statusBar().showMessage(f"Error loading {path}: {str(e)}")

    def add_track(self):
        if not self.wells:
            self.statusBar().showMessage("No wells loaded!")
            return
        curves_set = set()
        for well in self.wells.values():
            curves_set.update(well['data'].columns)
        curves = sorted(list(curves_set))
        track = TrackControl(len(self.tracks) + 1, curves)
        track.changed.connect(self.update_plot)
        track.deleteRequested.connect(self.delete_track)
        self.tracks.append(track)
        self.track_stack.addWidget(track)
        btn = QPushButton(f"Track {track.number}")
        btn.setCheckable(True)
        btn.clicked.connect(lambda _, idx=len(self.tracks)-1: self.switch_track(idx))
        self.track_selector_layout.addWidget(btn)
        self.track_buttons.append(btn)
        if len(self.tracks) == 1:
            btn.setChecked(True)
            self.track_stack.setCurrentIndex(0)
        self.statusBar().showMessage(f"Added Track {track.number}")
        self.update_plot()

    def switch_track(self, index):
        self.track_stack.setCurrentIndex(index)
        for i, btn in enumerate(self.track_buttons):
            btn.setChecked(i == index)

    def delete_track(self, track):
        if track in self.tracks:
            index = self.tracks.index(track)
            self.tracks.remove(track)
            self.track_stack.removeWidget(track)
            btn = self.track_buttons.pop(index)
            self.track_selector_layout.removeWidget(btn)
            btn.deleteLater()
            for i, t in enumerate(self.tracks):
                t.number = i + 1
                self.track_buttons[i].setText(f"Track {t.number}")
            self.statusBar().showMessage(f"Deleted Track {track.number}")
            self.update_plot()

    def sync_zoom(self):
        if not self.figure_widgets:
            self.statusBar().showMessage("No figures to sync.")
            return
        ref_widget = list(self.figure_widgets.values())[0]
        ref_axes = ref_widget.figure.axes
        for widget in self.figure_widgets.values():
            for i, ax in enumerate(widget.figure.axes):
                if i < len(ref_axes):
                    ax.set_xlim(ref_axes[i].get_xlim())
                    ax.set_ylim(ref_axes[i].get_ylim())
            widget.canvas.draw()
        self.statusBar().showMessage("Zoom synchronized across figures.")

    def handleZoomChanged(self, sender):
        if self.sync_zoom_enabled:
            self.sync_zoom()

    def resetZoom(self):
        for widget in self.figure_widgets.values():
            widget.resetZoom()

    def undoZoom(self):
        for widget in self.figure_widgets.values():
            widget.undoZoom()

    def update_plot(self):
        selected_wells = []
        for i in range(self.well_list.count()):
            item = self.well_list.item(i)
            if item.checkState() == Qt.Checked:
                well_name = item.text()
                if well_name in self.wells:
                    selected_wells.append(well_name)
        for well in list(self.figure_widgets.keys()):
            if well not in selected_wells:
                widget = self.figure_widgets[well]
                self.figure_layout.removeWidget(widget)
                widget.setParent(None)
                widget.deleteLater()
                del self.figure_widgets[well]
        for well in selected_wells:
            if well not in self.figure_widgets:
                fig_widget = FigureWidget(well)
                fig_widget.zoomChanged.connect(self.handleZoomChanged)
                self.figure_widgets[well] = fig_widget
                self.figure_layout.addWidget(fig_widget)
            data = self.wells[well]['data']
            self.figure_widgets[well].update_plot(data, self.tracks, well)

# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    viewer = WellLogViewer()
    viewer.show()
    sys.exit(app.exec_())