import sys
import os
import lasio
import numpy as np
import pandas as pd
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QMainWindow, QFileDialog, QDockWidget, QListWidget,
                             QListWidgetItem, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
                             QComboBox, QPushButton, QCheckBox, QSpinBox, QScrollArea, QTabWidget)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# ----------------------------------------------------------------------
# WellLogViewer Class: Main window with a QTabWidget as central area.
# Each selected well gets its own canvas (tab) that plots its tracks.
# ----------------------------------------------------------------------
class WellLogViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.wells = {}           # Store loaded wells by well name
        self.tracks = []          # List of active track controls
        self.canvas_dict = {}     # Map well name -> {'figure': Figure, 'canvas': FigureCanvas, 'widget': widget}
        self.initUI()
       
        
    def initUI(self):
        self.setWindowTitle('Modern Well Log Viewer')
        self.setGeometry(100, 100, 1200, 800)
        
        # Instead of a single canvas, use a QTabWidget to hold one canvas per well.
        self.tab_widget = QTabWidget()
        # Set the tab text color so it’s visible.
        self.tab_widget.setStyleSheet("QTabBar::tab { color: white; }")
        self.setCentralWidget(self.tab_widget)
        
        # Create a menubar with a File menu for folder loading.
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        load_folder_action = QtWidgets.QAction("Load LAS Folder", self)
        load_folder_action.triggered.connect(self.load_las_folder)
        file_menu.addAction(load_folder_action)
        
        # Create a dock widget for controls.
        self.dock = QDockWidget("Controls", self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        
        dock_widget = QWidget()
        layout = QVBoxLayout()
        
        # (Optional) Remove the old Load LAS File button since folder loading is in the menu.
        # List widget to display loaded wells (as checkable items, now unchecked by default).
        self.well_list = QListWidget()
        self.well_list.itemChanged.connect(self.update_plot)
        layout.addWidget(QLabel("Loaded Wells:"))
        layout.addWidget(self.well_list)
        
        # Scroll area to hold interactive track controls.
        self.scroll_area = QScrollArea()
        self.scroll_widget = QWidget()
        self.track_container = QVBoxLayout(self.scroll_widget)
        self.scroll_widget.setLayout(self.track_container)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.scroll_widget)
        layout.addWidget(self.scroll_area)

        # Button to add a new track control.
        btn_add_track = QPushButton("Add Track")
        btn_add_track.clicked.connect(self.add_track)
        layout.addWidget(btn_add_track)

        dock_widget.setLayout(layout)
        self.dock.setWidget(dock_widget)
        
        self.statusBar().showMessage('Ready')

    def load_las_folder(self):
        # Open a directory chooser.
        folder = QFileDialog.getExistingDirectory(self, "Select Folder Containing LAS Files")
        if folder:
            # Iterate over files in the folder with .las extension.
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
            # Identify a valid depth column (DEPT, DEPTH, or MD)
            depth_col = next((col for col in df.columns if col.upper() in ["DEPT", "DEPTH", "MD"]), None)
            if depth_col is None:
                raise ValueError("No valid depth column found.")
            df.rename(columns={depth_col: "DEPT"}, inplace=True)

            # Use the well name if available; otherwise, use the filename.
            well_name = las.well.WELL.value if las.well.WELL.value else os.path.basename(path)
            # Avoid reloading a well with the same name.
            if well_name in self.wells:
                return
            self.wells[well_name] = {'data': df, 'path': path}
            
            # Create a checkable list item; unchecked by default.
            item = QListWidgetItem(well_name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.well_list.addItem(item)
            
            self.statusBar().showMessage(f"Loaded: {well_name}")
        except Exception as e:
            self.statusBar().showMessage(f"Error loading {path}: {str(e)}")

    def add_track(self):
        # If no wells are loaded, alert the user.
        if not self.wells:
            self.statusBar().showMessage("No wells loaded!")
            return

        # Create the union of all available curves from loaded wells.
        curves_set = set()
        for well in self.wells.values():
            curves_set.update(well['data'].columns)
        curves = sorted(list(curves_set))
        
        track = TrackControl(len(self.tracks) + 1, curves)
        # Connect the track's signals to update plot.
        track.changed.connect(self.update_plot)
        track.deleteRequested.connect(self.delete_track)
        self.tracks.append(track)
        self.track_container.addWidget(track)
        self.statusBar().showMessage(f"Added Track {track.number}")
        self.update_plot()

    def delete_track(self, track):
        # Remove track widget from layout and list.
        if track in self.tracks:
            self.tracks.remove(track)
            track.setParent(None)
            track.deleteLater()
            self.statusBar().showMessage(f"Deleted Track {track.number}")
            self.update_plot()

    def update_plot(self):
        # Determine which wells are selected (checked).
        selected_wells = []
        for i in range(self.well_list.count()):
            item = self.well_list.item(i)
            if item.checkState() == Qt.Unchecked:
                continue
            well_name = item.text()
            if well_name in self.wells:
                selected_wells.append(well_name)
                
        # Remove tabs for wells that are no longer selected.
        for well in list(self.canvas_dict.keys()):
            if well not in selected_wells:
                index = self.tab_widget.indexOf(self.canvas_dict[well]['widget'])
                if index != -1:
                    self.tab_widget.removeTab(index)
                del self.canvas_dict[well]
                
        # For each selected well, create or update its canvas.
        for well in selected_wells:
            if well not in self.canvas_dict:
                # Create a new Figure and Canvas.
                fig = Figure()
                canvas = FigureCanvas(fig)
                self.canvas_dict[well] = {'figure': fig, 'canvas': canvas, 'widget': canvas}
                self.tab_widget.addTab(canvas, well)
            # Update the plot for this well.
            data = self.wells[well]['data']
            fig = self.canvas_dict[well]['figure']
            fig.clear()
            n_tracks = len(self.tracks)
            if n_tracks == 0:
                ax = fig.add_subplot(111)
                ax.text(0.5, 0.5, "No track controls", horizontalalignment='center', verticalalignment='center')
            else:
                # Create one subplot per track (sharing the y-axis for depth).
                axes = fig.subplots(1, n_tracks, sharey=True)
                if n_tracks == 1:
                    axes = [axes]
                depth = data['DEPT']
                for ax, track in zip(axes, self.tracks):
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
                    # Set y-axis label "Depth" on the first subplot.
                    ax.set_ylabel("Depth")
                    ax.grid(track.grid.isChecked())
                    if track.flip.isChecked():
                        ax.invert_xaxis()
                    ax.set_ylim(depth.max(), depth.min())
                    ax.legend([well])
            fig.subplots_adjust(wspace=0.1)
            self.canvas_dict[well]['canvas'].draw()

    

# ----------------------------------------------------------------------
# TrackControl Class: Interactive control widget for each track.
# Added a "Delete" button.
# ----------------------------------------------------------------------
class TrackControl(QWidget):
    changed = QtCore.pyqtSignal()
    deleteRequested = QtCore.pyqtSignal(object)  # Signal to request deletion of this track

    def __init__(self, number, curves):
        super().__init__()
        self.number = number
        self.initUI(curves)

    def initUI(self, curves):
        layout = QHBoxLayout()
        
        # ComboBox for selecting a curve from the union of curves.
        self.curve = QComboBox()
        self.curve.addItems(["Select Curve"] + curves)
        self.curve.currentIndexChanged.connect(self.changed)
        
        # ComboBox for plot color.
        self.color = QComboBox()
        self.color.addItems(["black", "red", "blue", "green", "orange"])
        self.color.currentIndexChanged.connect(self.changed)
        
        # ComboBox for line style.
        self.style = QComboBox()
        self.style.addItems(["-", "--", ":", "-."])
        self.style.currentIndexChanged.connect(self.changed)
        
        # SpinBox for line width.
        self.width = QSpinBox()
        self.width.setRange(1, 5)
        self.width.setValue(1)
        self.width.valueChanged.connect(self.changed)
        
        # CheckBox for grid display.
        self.grid = QCheckBox("Grid")
        self.grid.stateChanged.connect(self.changed)
        
        # CheckBox to flip the x-axis.
        self.flip = QCheckBox("Flip")
        self.flip.stateChanged.connect(self.changed)
        
        # Delete button for this track.
        self.btn_delete = QPushButton("Delete")
        self.btn_delete.clicked.connect(self.handle_delete)
        
        layout.addWidget(QLabel(f"Track {self.number}"))
        layout.addWidget(self.curve)
        layout.addWidget(QLabel("Color:"))
        layout.addWidget(self.color)
        layout.addWidget(QLabel("Style:"))
        layout.addWidget(self.style)
        layout.addWidget(QLabel("Width:"))
        layout.addWidget(self.width)
        layout.addWidget(self.grid)
        layout.addWidget(self.flip)
        layout.addWidget(self.btn_delete)
        self.setLayout(layout)
    
    def handle_delete(self):
        # Emit signal to request deletion of this track.
        self.deleteRequested.emit(self)

# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    viewer = WellLogViewer()
    viewer.show()
    sys.exit(app.exec_())