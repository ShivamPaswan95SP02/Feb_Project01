import sys
import os
import lasio
import numpy as np
import pandas as pd
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QGroupBox
from PyQt5.QtWidgets import QColorDialog
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QMainWindow, QFileDialog, QDockWidget, QListWidget,
                             QListWidgetItem, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
                             QComboBox, QPushButton, QCheckBox, QSpinBox, QScrollArea, QAction)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# ----------------------------------------------------------------------
# FigureWidget Class: A widget that embeds a matplotlib figure and canvas.
# This widget displays the plot for a single well.
# ----------------------------------------------------------------------
class FigureWidget(QWidget):
    def __init__(self, well_name, parent=None):
        super().__init__(parent)
        self.well_name = well_name
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
       
        layout = QVBoxLayout(self)
       
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    
    def update_plot(self, data, tracks, well_name):
        self.figure.clear()
        n_tracks = len(tracks)
        if n_tracks == 0:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, "No track controls", horizontalalignment='center', verticalalignment='center')
            
        else:
            # Create one subplot per track sharing the y-axis.
            axes = self.figure.subplots(1, n_tracks, sharey=True)
            if n_tracks == 1:
                axes = [axes]
                
            depth = data['DEPT']
            for idx, (ax, track) in enumerate(zip(axes, tracks)):
                curve = track.curve.currentText()
                if curve == "Select Curve":
                    ax.text(0.5, 0.5, "No curve selected", horizontalalignment='center', verticalalignment='center')
                    continue
                if curve in data.columns:
                    ax.plot(data[curve], depth,
                            color=track.color.currentText(),
                            linewidth=track.width.value(),
                            linestyle=track.style.currentText())
                ax.set_xlabel(curve)
                # Only the first subplot gets the "Depth" label.
                if idx == 0:
                    ax.set_ylabel("Depth")
                else:
                    ax.set_ylabel("")
                ax.grid(track.grid.isChecked())
                if track.flip.isChecked():
                    ax.invert_xaxis()
                ax.set_ylim(depth.max(), depth.min())
                ax.legend([well_name])

        self.figure.subplots_adjust(wspace=0.1)
        self.canvas.draw()

# ----------------------------------------------------------------------
# WellLogViewer Class: Main window that holds controls and a horizontal scrollable area
# for displaying multiple figures (one per selected well) side-by-side.
# ----------------------------------------------------------------------
class WellLogViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.wells = {}               # Loaded wells: well name -> {'data': DataFrame, 'path': filepath}
        self.tracks = []              # List of active track controls
        self.figure_widgets = {}      # Map well name -> FigureWidget
        self.initUI()
       
        
    def initUI(self):
        self.setWindowTitle('Modern Well Log Viewer')
        self.setGeometry(100, 100, 1200, 800)
        
        # Create a central scroll area to hold all figure widgets arranged horizontally.
        self.figure_scroll = QScrollArea()
        self.figure_container = QWidget()
        # Change vertical layout to horizontal layout.
        self.figure_layout = QHBoxLayout(self.figure_container)
        self.figure_container.setLayout(self.figure_layout)
        self.figure_scroll.setWidgetResizable(True)
        self.figure_scroll.setWidget(self.figure_container)
        self.setCentralWidget(self.figure_scroll)
        
        # Menubar with "File" menu actions.
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        
        load_folder_action = QAction("Load LAS Folder", self)
        load_folder_action.triggered.connect(self.load_las_folder)
        file_menu.addAction(load_folder_action)
        
        toggle_controls_action = QAction("Toggle Controls", self)
        toggle_controls_action.triggered.connect(self.toggle_controls)
        menubar.addAction(toggle_controls_action)

         # New action: Change Background Color
        change_bg_action = QAction("Change Background Color", self)
        change_bg_action.triggered.connect(self.change_background_color)
        menubar.addAction(change_bg_action)
        
        # Create a dock widget for controls.
        self.dock = QDockWidget("Controls", self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        
        dock_widget = QWidget()
        dock_layout = QVBoxLayout()
        
        # Wells list (checkable items, unchecked by default).
        self.well_list = QListWidget()
        self.well_list.itemChanged.connect(self.update_plot)
        dock_layout.addWidget(QLabel("Loaded Wells:"))
        dock_layout.addWidget(self.well_list)
        
        # Scroll area for track controls.
        self.scroll_area = QScrollArea()
        self.scroll_widget = QWidget()
        self.track_container = QVBoxLayout(self.scroll_widget)
        self.scroll_widget.setLayout(self.track_container)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.scroll_widget)
        dock_layout.addWidget(self.scroll_area)

        # Button to add a new track control.
        btn_add_track = QPushButton("Add Track")
        btn_add_track.setStyleSheet("background-color: White; border-radius: 5px; color: blue; font: 15pt;")
        btn_add_track.clicked.connect(self.add_track)
        dock_layout.addWidget(btn_add_track)
        
        dock_widget.setLayout(dock_layout)
        self.dock.setWidget(dock_widget)
        
        self.statusBar().showMessage('Ready')


    def change_background_color(self):
        """Opens a color picker to change the background color."""
        color = QColorDialog.getColor()
        if color.isValid():
            self.setStyleSheet(f"QWidget {{ background-color: {color.name()}; }}")    

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
            # Find a valid depth column.
            depth_col = next((col for col in df.columns if col.upper() in ["DEPT", "DEPTH", "MD"]), None)
            if depth_col is None:
                raise ValueError("No valid depth column found.")
            df.rename(columns={depth_col: "DEPT"}, inplace=True)
            well_name = las.well.WELL.value if las.well.WELL.value else os.path.basename(path)
            if well_name in self.wells:
                return
            self.wells[well_name] = {'data': df, 'path': path}
            # Create checkable list item (unchecked by default).
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
        self.track_container.addWidget(track)
        self.statusBar().showMessage(f"Added Track {track.number}")
        self.update_plot()

    def delete_track(self, track):
        if track in self.tracks:
            self.tracks.remove(track)
            track.setParent(None)
            track.deleteLater()
            self.statusBar().showMessage(f"Deleted Track {track.number}")
            self.update_plot()

    def update_plot(self):
        # Gather selected wells.
        selected_wells = []
        for i in range(self.well_list.count()):
            item = self.well_list.item(i)
            if item.checkState() == Qt.Checked:
                well_name = item.text()
                if well_name in self.wells:
                    selected_wells.append(well_name)
                    
        # Remove figure widgets for deselected wells.
        for well in list(self.figure_widgets.keys()):
            if well not in selected_wells:
                widget = self.figure_widgets[well]
                self.figure_layout.removeWidget(widget)
                widget.setParent(None)
                widget.deleteLater()
                del self.figure_widgets[well]
                
        # For each selected well, create/update its FigureWidget.
        for well in selected_wells:
            if well not in self.figure_widgets:
                fig_widget = FigureWidget(well)
                self.figure_widgets[well] = fig_widget
                self.figure_layout.addWidget(fig_widget)
            data = self.wells[well]['data']
            self.figure_widgets[well].update_plot(data, self.tracks, well)

    

# ----------------------------------------------------------------------
# TrackControl Class: Widget for each track control with a "Delete" button.
# ----------------------------------------------------------------------
class TrackControl(QWidget):
    changed = QtCore.pyqtSignal()
    deleteRequested = QtCore.pyqtSignal(object)  # Signal to request deletion of this track

    def __init__(self, number, curves):
        super().__init__()
        self.number = number
        self.initUI(curves)

    def initUI(self, curves):
        # Create a group box to hold the track controls
        self.group_box = QGroupBox(f"Track {self.number}")
        self.group_box.setStyleSheet("QGroupBox { background-color: white; border-radius: 5px; padding: 5px; }")
        group_layout = QVBoxLayout()

        # Create a horizontal layout for the close button
        header_layout = QHBoxLayout()
        self.btn_close = QPushButton("X")
        self.btn_close.setFixedSize(20, 20)  # Small size for top-left button
        self.btn_close.clicked.connect(self.handle_delete)

        header_layout.addWidget(self.btn_close)
        header_layout.addStretch()  # Push the close button to the left

        # Create track controls
        controls_layout = QHBoxLayout()

        self.curve = QComboBox()
        self.curve.addItems(["Select Curve"] + curves)
        self.curve.currentIndexChanged.connect(self.changed)

        self.color = QComboBox()
        self.color.addItems(["black", "red", "blue", "green", "orange"])
        self.color.currentIndexChanged.connect(self.changed)

        self.style = QComboBox()
        self.style.addItems(["-", "--", ":", "-."])
        self.style.currentIndexChanged.connect(self.changed)

        self.width = QSpinBox()
        self.width.setRange(1, 5)
        self.width.setValue(1)
        self.width.valueChanged.connect(self.changed)

        self.grid = QCheckBox("Grid")
        self.grid.stateChanged.connect(self.changed)

        self.flip = QCheckBox("Flip")
        self.flip.stateChanged.connect(self.changed)

        controls_layout.addWidget(QLabel("Curve:"))
        controls_layout.addWidget(self.curve)
        controls_layout.addWidget(QLabel("Color:"))
        controls_layout.addWidget(self.color)
        controls_layout.addWidget(QLabel("Style:"))
        controls_layout.addWidget(self.style)
        controls_layout.addWidget(QLabel("Width:"))
        controls_layout.addWidget(self.width)
        controls_layout.addWidget(self.grid)
        controls_layout.addWidget(self.flip)

        # Add layouts into the group box
        group_layout.addLayout(header_layout)
        group_layout.addLayout(controls_layout)
        self.group_box.setLayout(group_layout)

        # Main layout for TrackControl
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.group_box)
        self.setLayout(main_layout)

    def handle_delete(self):
        self.deleteRequested.emit(self)

# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    viewer = WellLogViewer()
    viewer.show()
    sys.exit(app.exec_())
