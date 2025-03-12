import sys
import lasio
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

class WellLogPlotter(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.las = None  # LAS file object
        self.tracks = []  # Store track plots

    def initUI(self):
        self.setWindowTitle("Well Log Viewer")
        self.setGeometry(100, 100, 800, 600)
        
        layout = QVBoxLayout()
        self.canvas = FigureCanvas(plt.figure(figsize=(6, 8)))
        layout.addWidget(self.canvas)
        
        self.loadButton = QPushButton("Load LAS File")
        self.loadButton.clicked.connect(self.load_las_file)
        layout.addWidget(self.loadButton)
        
        self.addTrackButton = QPushButton("Add Track")
        self.addTrackButton.clicked.connect(self.add_track)
        layout.addWidget(self.addTrackButton)
        
        self.setLayout(layout)
    
    def load_las_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open LAS File", "", "LAS Files (*.las);;All Files (*)", options=options)
        if file_path:
            self.las = lasio.read(file_path)
            print("Loaded LAS file:", file_path)
    
    def add_track(self):
        if self.las is None:
            print("No LAS file loaded!")
            return
        
        self.canvas.figure.clf()
        depth = self.las.index
        curves = self.las.keys()
        
        if len(self.tracks) < len(curves) - 1:
            new_curve = curves[len(self.tracks) + 1]
            ax = self.canvas.figure.add_subplot(1, len(self.tracks) + 1, len(self.tracks) + 1)
            ax.plot(self.las[new_curve], depth)
            ax.set_xlabel(new_curve)
            ax.set_ylabel("Depth")
            ax.invert_yaxis()
            self.tracks.append(ax)
        
        self.canvas.draw()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = WellLogPlotter()
    viewer.show()
    sys.exit(app.exec_())
