import sys
import os
from PyQt5 import uic
import lasio
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QWidget, QVBoxLayout, QPushButton,
    QFileDialog, QListWidget, QLabel, QMessageBox, QScrollArea, QSpinBox, QCheckBox, QMenuBar
)
import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.gridspec as gridspec


class PlotWidget(QWidget):
    def __init__(self, parent=None):
        super(PlotWidget, self).__init__(parent)
        self.setMinimumSize(300, 200)
        self.figure = Figure(figsize=(5, 4), constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    def update_plots(self, las_list, track_count=None, use_track_count=False):
        self.figure.clf()
        N = len(las_list)
        if N == 0:
            return

        n_curves_list = []
        for las in las_list:
            curves = [curve for curve in las.curves if curve.mnemonic.upper() not in ["DEPT", "DEPTH"]]
            n_curves_list.append(len(curves))

        max_cols = max(n_curves_list) if not use_track_count else track_count
        gs = gridspec.GridSpec(N, max_cols, figure=self.figure)

        for i, las in enumerate(las_list):
            curves = las.curves
            depth_curve = next((curve for curve in curves if curve.mnemonic.upper() in ["DEPT", "DEPTH"]), None)
            depth = depth_curve.data if depth_curve else np.arange(len(curves[0].data))

            plot_curves = [curve for curve in curves if curve.mnemonic.upper() not in ["DEPT", "DEPTH"]]
            n_curves = len(plot_curves)

            for j in range(max_cols):
                ax = self.figure.add_subplot(gs[i, j])
                if j < n_curves:
                    curve = plot_curves[j]
                    ax.plot(curve.data, depth)
                    ax.set_xlabel(curve.mnemonic)
                    ax.set_title(curve.descr if curve.descr else curve.mnemonic)
                    ax.invert_yaxis()
                else:
                    ax.axis('off')
                if j == 0:
                    well_name = las.well.WELL.value if las.well.WELL.value else "Unknown"
                    ax.set_ylabel(f"Depth\nWell: {well_name}")

        self.canvas.draw()


class ControlDockWidget(QDockWidget):
    def __init__(self, parent=None):
        super(ControlDockWidget, self).__init__("Control Panel", parent)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.las_files = {}
        self.main_window = parent
        
        widget = QWidget()
        layout = QVBoxLayout()

        self.loaded_label = QLabel("Loaded Wells:")
        self.loaded_list = QListWidget()

        layout.addWidget(self.loaded_label)
        layout.addWidget(self.loaded_list)
        
        self.selected_label = QLabel("Selected Wells:")
        self.selected_list = QListWidget()
        self.loaded_list.itemClicked.connect(self.select_well_on_click)
        self.selected_list.itemClicked.connect(self.remove_selected_well_on_click)

        layout.addWidget(self.selected_label)
        layout.addWidget(self.selected_list)

        self.clear_button = QPushButton("All Clear")
        self.clear_button.clicked.connect(self.clear_selected_wells)
        layout.addWidget(self.clear_button)

        self.track_checkbox = QCheckBox("Enable Track Count Control")
        self.track_checkbox.setChecked(False)
        self.track_checkbox.stateChanged.connect(self.update_plot)

        self.track_label = QLabel("Set Track Count:")
        self.track_spinbox = QSpinBox()
        self.track_spinbox.setRange(1, 10)
        self.track_spinbox.setValue(3)
        self.track_spinbox.valueChanged.connect(self.update_plot)

        layout.addWidget(self.track_checkbox)
        layout.addWidget(self.track_label)
        layout.addWidget(self.track_spinbox)

        widget.setLayout(layout)
        self.setWidget(widget)

    def load_las_file(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Open LAS File(s)", "", "LAS Files (*.las)")
        if file_paths:
            for file_path in file_paths:
                try:
                    las = lasio.read(file_path)
                    well_name = las.well.WELL.value if las.well.WELL.value else os.path.basename(file_path)
                    if well_name not in self.las_files:
                        self.las_files[well_name] = las
                        self.loaded_list.addItem(well_name)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to load LAS file: {str(e)}")

    def select_well_on_click(self, item):
        well_name = item.text()
        if well_name not in [self.selected_list.item(i).text() for i in range(self.selected_list.count())]:
            self.selected_list.addItem(well_name)
        self.update_plot()

    def remove_selected_well_on_click(self, item):
        row = self.selected_list.row(item)
        self.selected_list.takeItem(row)
        self.update_plot()

    def clear_selected_wells(self):
        self.selected_list.clear()
        self.update_plot()    

    def update_plot(self):
        selected_wells = [self.selected_list.item(i).text() for i in range(self.selected_list.count())]
        las_list = [self.las_files[well] for well in selected_wells]
        use_track_count = self.track_checkbox.isChecked()
        track_count = self.track_spinbox.value() if use_track_count else None
        self.main_window.plot_widget.update_plots(las_list, track_count=track_count, use_track_count=use_track_count)
        


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        uic.loadUi("febpro1.ui", self)
        self.setWindowTitle("Well Data Visualization")
        self.setGeometry(100, 100, 1000, 600)

        self.plot_widget = PlotWidget(self)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.plot_widget)
        self.setCentralWidget(self.scroll_area)

        self.control_dock = ControlDockWidget(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.control_dock)

        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        load_action = file_menu.addAction("Load .LAS File(s)")
        load_action.triggered.connect(self.control_dock.load_las_file)
        
        
        toggle_action = menubar.addAction("Show/Hide Control Panel")
        toggle_action.triggered.connect(self.toggle_control_panel)
    
    def toggle_control_panel(self):
        self.control_dock.setVisible(not self.control_dock.isVisible())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())