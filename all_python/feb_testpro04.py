import sys
import os
import lasio
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QWidget, QVBoxLayout, QPushButton,
    QFileDialog, QListWidget, QLabel, QMessageBox
)
import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class PlotWidget(QWidget):
    """Widget for displaying an individual LAS file plot in a dock widget."""
    def __init__(self, las, parent=None):
        super(PlotWidget, self).__init__(parent)
        self.figure = Figure(figsize=(5, 4), constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.las = las
        self.init_plot()

        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    def init_plot(self):
        """Create a plot for the given LAS file."""
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        # Extract depth curve
        depth_curve = next((curve for curve in self.las.curves if curve.mnemonic.upper() in ["DEPT", "DEPTH"]), None)
        depth = depth_curve.data if depth_curve else np.arange(len(self.las.curves[0].data))

        # Extract and plot all other curves
        for curve in self.las.curves:
            if curve.mnemonic.upper() not in ["DEPT", "DEPTH"]:
                ax.plot(curve.data, depth, label=curve.mnemonic)

        ax.set_xlabel("Values")
        ax.set_ylabel("Depth")
        ax.legend()
        ax.invert_yaxis()
        well_name = self.las.well.WELL.value if self.las.well.WELL.value else "Unknown"
        ax.set_title(f"Well: {well_name}")

        self.canvas.draw()


class WellDockWidget(QDockWidget):
    """Dock widget containing a plot for a single LAS file."""
    def __init__(self, well_name, las, parent=None):
        super(WellDockWidget, self).__init__(well_name, parent)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.plot_widget = PlotWidget(las, self)
        self.setWidget(self.plot_widget)

        # Reference to parent control dock for cleanup
        self.parent_control = parent.control_dock

        # Connect close event to auto-remove from selected list
        self.closeEvent = self.on_close

    def on_close(self, event):
        """Handle closing of the dock widget and remove from the selected list."""
        well_name = self.windowTitle()
        self.parent_control.remove_well_from_selected_list(well_name)
        event.accept()  # Allow the dock widget to close


class ControlDockWidget(QDockWidget):
    """Control panel for managing LAS files and plots."""
    def __init__(self, parent=None):
        super(ControlDockWidget, self).__init__("Control Panel", parent)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.las_files = {}
        self.dock_widgets = {}  # Store references to dock widgets
        self.main_window = parent

        widget = QWidget()
        layout = QVBoxLayout()

        self.loaded_label = QLabel("Loaded LAS Files:")
        self.loaded_list = QListWidget()
        layout.addWidget(self.loaded_label)
        layout.addWidget(self.loaded_list)

        self.selected_label = QLabel("Selected LAS Files:")
        self.selected_list = QListWidget()
        self.loaded_list.itemClicked.connect(self.select_well)
        self.selected_list.itemClicked.connect(self.remove_selected_well)

        layout.addWidget(self.selected_label)
        layout.addWidget(self.selected_list)

        self.clear_button = QPushButton("Clear All")
        self.clear_button.clicked.connect(self.clear_selected_wells)
        layout.addWidget(self.clear_button)

        self.load_button = QPushButton("Load LAS Files")
        self.load_button.clicked.connect(self.load_las_files)
        layout.addWidget(self.load_button)

        widget.setLayout(layout)
        self.setWidget(widget)

    def load_las_files(self):
        """Load multiple LAS files and add to the list."""
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Open LAS Files", "", "LAS Files (*.las)")
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

    def select_well(self, item):
        """Create a separate dock widget for the selected LAS file."""
        well_name = item.text()
        if well_name not in [self.selected_list.item(i).text() for i in range(self.selected_list.count())]:
            self.selected_list.addItem(well_name)

        if well_name in self.las_files and well_name not in self.dock_widgets:
            las = self.las_files[well_name]
            dock = WellDockWidget(well_name, las, self.main_window)
            self.main_window.addDockWidget(Qt.RightDockWidgetArea, dock)
            self.dock_widgets[well_name] = dock  # Store reference to the dock widget

    def remove_selected_well(self, item):
        """Remove a well from the selected list and delete its associated dock widget."""
        well_name = item.text()
        self.remove_well_from_selected_list(well_name)

    def remove_well_from_selected_list(self, well_name):
        """Remove a well from the selected list and delete its dock widget."""
        # Remove the dock widget
        if well_name in self.dock_widgets:
            dock_widget = self.dock_widgets.pop(well_name)  # Remove from dictionary
            self.main_window.removeDockWidget(dock_widget)
            dock_widget.deleteLater()  # Ensure proper deletion

        # Remove item from the selected list
        for i in range(self.selected_list.count()):
            if self.selected_list.item(i).text() == well_name:
                self.selected_list.takeItem(i)
                break

    def clear_selected_wells(self):
        """Clear selected wells and remove all associated dock widgets."""
        while self.selected_list.count():
            item = self.selected_list.item(0)
            self.remove_well_from_selected_list(item.text())  # Calls the remove function for each item


class MainWindow(QMainWindow):
    """Main application window."""
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowTitle("Advanced LAS File Visualizer")
        self.setGeometry(100, 100, 1200, 700)

        self.control_dock = ControlDockWidget(self)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.control_dock)

        # Menu bar
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        load_action = file_menu.addAction("Load .LAS Files")
        load_action.triggered.connect(self.control_dock.load_las_files)

        toggle_action = menubar.addAction("Show/Hide Control Panel")
        toggle_action.triggered.connect(self.toggle_control_panel)

        # Theme Menu
        theme_menu = menubar.addMenu("Themes")
        light_theme_action = theme_menu.addAction("Light Mode")
        dark_theme_action = theme_menu.addAction("Dark Mode")

        light_theme_action.triggered.connect(lambda: self.set_theme("light"))
        dark_theme_action.triggered.connect(lambda: self.set_theme("dark"))

    def toggle_control_panel(self):
        """Show or hide the control panel."""
        self.control_dock.setVisible(not self.control_dock.isVisible())

    def set_theme(self, theme):
        """Change the application theme dynamically."""
        if theme == "dark":
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #2b2b2b;
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
