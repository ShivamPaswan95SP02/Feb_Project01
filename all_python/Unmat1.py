import sys
import os
import lasio
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QFileDialog, QVBoxLayout,
    QHBoxLayout, QWidget, QListWidget, QLabel, QMessageBox
)

class WellDataApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Well Data Visualization")
        self.setGeometry(100, 100, 800, 400)

        # Main layout
        self.main_layout = QHBoxLayout()

        # Left panel - Loaded Wells
        self.loaded_wells_layout = QVBoxLayout()
        self.loaded_label = QLabel("Loaded Wells:")
        self.loaded_list = QListWidget()
        self.load_button = QPushButton("Load .LAS File")
        self.load_button.clicked.connect(self.load_las_file)
        self.clear_button = QPushButton("Clear Loaded Wells")
        self.clear_button.clicked.connect(self.clear_loaded_wells)

        self.loaded_wells_layout.addWidget(self.loaded_label)
        self.loaded_wells_layout.addWidget(self.loaded_list)
        self.loaded_wells_layout.addWidget(self.load_button)
        self.loaded_wells_layout.addWidget(self.clear_button)

        # Right panel - Selected Wells
        self.selected_wells_layout = QVBoxLayout()
        self.selected_label = QLabel("Selected Wells:")
        self.selected_list = QListWidget()
        self.select_button = QPushButton("Select Well")
        self.select_button.clicked.connect(self.select_well)
        self.remove_button = QPushButton("Remove Selected Well")
        self.remove_button.clicked.connect(self.remove_selected_well)

        self.selected_wells_layout.addWidget(self.selected_label)
        self.selected_wells_layout.addWidget(self.selected_list)
        self.selected_wells_layout.addWidget(self.select_button)
        self.selected_wells_layout.addWidget(self.remove_button)

        # Add both sections to the main layout
        self.main_layout.addLayout(self.loaded_wells_layout)
        self.main_layout.addLayout(self.selected_wells_layout)

        # Set central widget
        container = QWidget()
        container.setLayout(self.main_layout)
        self.setCentralWidget(container)

    def load_las_file(self):
        """Loads a LAS file and adds it to the loaded wells list."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Open LAS File", "", "LAS Files (*.las)")
        if file_path:
            try:
                las = lasio.read(file_path)
                well_name = las.well.WELL.value if las.well.WELL.value else os.path.basename(file_path)

                # Avoid duplicate wells in the list
                if well_name not in [self.loaded_list.item(i).text() for i in range(self.loaded_list.count())]:
                    self.loaded_list.addItem(well_name)
                else:
                    QMessageBox.warning(self, "Duplicate Entry", "This well is already loaded.")
            except lasio.exceptions.LASHeaderError:
                QMessageBox.critical(self, "Error", "Invalid LAS file format.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load LAS file:\n{str(e)}")

    def select_well(self):
        """Moves selected wells from loaded list to selected wells list."""
        selected_items = self.loaded_list.selectedItems()
        if selected_items:
            for item in selected_items:
                if item.text() not in [self.selected_list.item(i).text() for i in range(self.selected_list.count())]:
                    self.selected_list.addItem(item.text())
                else:
                    QMessageBox.warning(self, "Duplicate Selection", f"{item.text()} is already selected.")

    def remove_selected_well(self):
        """Removes selected wells from the selected wells list."""
        selected_items = self.selected_list.selectedItems()
        for item in selected_items:
            self.selected_list.takeItem(self.selected_list.row(item))

    def clear_loaded_wells(self):
        """Clears all wells from the loaded list."""
        self.loaded_list.clear()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WellDataApp()
    window.show()
    sys.exit(app.exec_())
