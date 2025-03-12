import sys
import os
from PyQt5 import uic
import lasio
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QHBoxLayout, QMainWindow, QDockWidget, QWidget, QVBoxLayout, QPushButton,
    QFileDialog, QListWidget, QLabel, QMessageBox, QLineEdit, QScrollArea
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

    def update_plots(self, tracks):
        """ Updates the plots dynamically based on subplot settings """
        self.figure.clf()
        N = len(tracks)
        if N == 0:
            self.canvas.draw()
            return

        gs = gridspec.GridSpec(N, 1, figure=self.figure)

        for i, track in enumerate(tracks):
            well_name = track["well_selector"].currentText()
            if well_name not in track["parent"].las_files:
                continue

            las = track["parent"].las_files[well_name]
            depth_curve = next((c for c in las.curves if c.mnemonic.upper() in ["DEPT", "DEPTH"]), None)
            depth = depth_curve.data if depth_curve else np.arange(len(las.curves[0].data))

            curve_name = track["curve_selector"].currentText()
            curve = next((c for c in las.curves if c.mnemonic == curve_name), None)
            if not curve:
                continue

            ax = self.figure.add_subplot(gs[i, 0])
            ax.plot(curve.data, depth, label=curve.mnemonic)

            ax.set_xlabel("Values")
            ax.set_ylabel("Depth")
            ax.legend()
            ax.invert_yaxis()
            ax.set_title(f"Well: {well_name}")

            # Apply user settings
            if track["grid"].isChecked():
                ax.grid(True)
            if track["flip"].isChecked():
                ax.invert_xaxis()
            
            try:
                x_min = float(track["x_min"].text())
                x_max = float(track["x_max"].text())
                ax.set_xlim(x_min, x_max)
            except ValueError:
                pass  # Ignore invalid inputs

        self.canvas.draw()


class ControlDockWidget(QDockWidget):
    def __init__(self, parent=None):
        super(ControlDockWidget, self).__init__("Control Panel", parent)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.las_files = {}
        self.main_window = parent
        self.tracks = []

        widget = QWidget()
        layout = QVBoxLayout()

        self.loaded_label = QLabel("Loaded Wells:")
        self.loaded_list = QListWidget()
        layout.addWidget(self.loaded_label)
        layout.addWidget(self.loaded_list)

        self.tracks_container = QVBoxLayout()
        layout.addLayout(self.tracks_container)

        self.add_subplot_button = QPushButton("Add Subplot")
        self.add_subplot_button.clicked.connect(self.add_subplot)
        layout.addWidget(self.add_subplot_button)

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

    def add_subplot(self):
        new_ui_widget = QWidget()
        uic.loadUi("controls.ui", new_ui_widget)
        self.tracks_container.addWidget(new_ui_widget)

        subplot_settings = {
            "widget": new_ui_widget,
            "parent": self,
            "visible": new_ui_widget.findChild(QCheckBox, "g_5"),
            "well_selector": new_ui_widget.findChild(QComboBox, "g_3"),
            "curve_selector": new_ui_widget.findChild(QComboBox, "g_4"),
            "x_min": new_ui_widget.findChild(QLineEdit, "lineEdit"),
            "x_max": new_ui_widget.findChild(QLineEdit, "lineEdit_2"),
            "flip": new_ui_widget.findChild(QCheckBox, "d"),
            "grid": new_ui_widget.findChild(QCheckBox, "s"),
            "delete_button": new_ui_widget.findChild(QPushButton, "g"),
        }

        # Populate well dropdown
        for well in self.las_files:
            subplot_settings["well_selector"].addItem(well)

        # Populate curve dropdown based on well selection
        subplot_settings["well_selector"].currentTextChanged.connect(
            lambda: self.update_curves(subplot_settings)
        )

        # Delete subplot on button click
        subplot_settings["delete_button"].clicked.connect(lambda: self.remove_subplot(subplot_settings))

        self.tracks.append(subplot_settings)

    def update_curves(self, subplot_settings):
        """ Updates the curve selection dropdown based on the selected well """
        well_name = subplot_settings["well_selector"].currentText()
        if well_name in self.las_files:
            las = self.las_files[well_name]
            subplot_settings["curve_selector"].clear()
            for curve in las.curves:
                subplot_settings["curve_selector"].addItem(curve.mnemonic)

    def remove_subplot(self, subplot_settings):
        """ Removes the selected subplot """
        self.tracks.remove(subplot_settings)
        subplot_settings["widget"].deleteLater()
        self.main_window.plot_widget.update_plots(self.tracks)


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

         # Theme Menu
        theme_menu = menubar.addMenu("Themes")
        light_theme_action = theme_menu.addAction("Light Mode")
        dark_theme_action = theme_menu.addAction("Dark Mode")
        
        light_theme_action.triggered.connect(lambda: self.set_theme("light"))
        dark_theme_action.triggered.connect(lambda: self.set_theme("dark"))

    def toggle_control_panel(self):
        self.control_dock.setVisible(not self.control_dock.isVisible())

    def set_theme(self, theme):
        """ Change the application theme dynamically """
        if theme == "dark":
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #2b2b2b;
                    color: white;
                }
                QMenuBar {
                    background-color: #444;
                    color: white;
                }
                QMenu {
                    background-color: #333;
                    color: white;
                }
                QMenu::item:selected {
                    background-color: #555;
                }
                QPushButton {
                    background-color: #555;
                    color: white;
                }
            """)
        else:
            self.setStyleSheet("")  # Reset to default light theme 


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
