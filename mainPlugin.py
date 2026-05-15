import os
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *

# initialize Qt resources from file resources.py
from PyQt6 import uic
from .GeoChecker.main_QGIS import run

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'geo_checker_dialog.ui'))

# clase ventana
class GeoCheckerDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        super(GeoCheckerDialog, self).__init__(parent)
        self.setupUi(self) # Esto "dibuja" la ventana
        
        #los nombres (btn_explore_linkage) deben coincidir con QT desgner
        self.btn_explore_linkage.clicked.connect(self.select_linkage)
        self.btn_explore_arc.clicked.connect(self.select_arc)
        self.btn_explore_node.clicked.connect(self.select_node)
        self.btn_explore_folder.clicked.connect(self.select_results)
        self.btn_run.clicked.connect(self.run_checks) 

    #logica de los botones
    def select_linkage(self):
        # Abre el buscador limitando la vista a archivos .shp
        filename, _ = QFileDialog.getOpenFileName(self, "Select Linkage File", "", "Shapefiles (*.shp)")
        if filename:
            self.lineEdit_linkage.setText(filename) # Pega la ruta en la caja de texto

    def select_arc(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Arc File", "", "Shapefiles (*.shp)")
        if filename:
            self.lineEdit_arc.setText(filename)

    def select_node(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Node File", "", "Shapefiles (*.shp)")
        if filename:
            self.lineEdit_node.setText(filename)

    def select_results(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Results Folder", "")
        if folder:
            self.lineEdit_folder.setText(folder)

    def run_checks(self):
        #logica para ejecutar los chequeos
        linkage_path = self.lineEdit_linkage.text()
        arc_path = self.lineEdit_arc.text()
        node_path = self.lineEdit_node.text()
        results_folder = self.lineEdit_folder.text()

        catchment_name = self.lineEdit_catchment.text().strip()
        groundwater_name = self.lineEdit_groundwater.text().strip()
        ds_prefix = self.lineEdit_ds_prefix.text().strip()

        if not all([linkage_path, arc_path, node_path, results_folder, catchment_name, groundwater_name, ds_prefix]):
            QMessageBox.warning(self, "Error", "Please select all files, the results folder, and the field names.")
            return

        try:
            #funcion principal
            run(
                linkage=linkage_path,
                arc=arc_path,
                node=node_path,
                results_folder=results_folder,
                catchment_name=catchment_name,
                groundwater_name=groundwater_name,
                ds_prefix=ds_prefix,
            )
            QMessageBox.information(self, "Success", "The checks have been executed correctly.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while executing the checks: {str(e)}")

# clase principal del Plugin (por defecto))
class GeoCheckerPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        self.action = QAction("Run GeoChecker", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("&GeoChecker", self.action)

    def unload(self):
        self.iface.removePluginMenu("&GeoChecker", self.action)
        if self.action:
            self.action.deleteLater()

    def run(self):
        if not self.dialog:
            self.dialog = GeoCheckerDialog(self.iface.mainWindow())
        self.dialog.show()
