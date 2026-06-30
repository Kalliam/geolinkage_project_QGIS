import os
import tempfile
import uuid
import sys
import subprocess
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.PyQt.QtCore import Qt, QTimer, QVariant
from qgis.PyQt import uic
from qgis.utils import iface
from qgis.core import Qgis
from .GeoLinkage.AppKernel import AppKernel
from qgis.core import (
    QgsMapLayerProxyModel, QgsProject, QgsVectorLayer, QgsMapLayerType, QgsWkbTypes, 
    QgsFields, QgsField, QgsFeature, QgsGeometry, QgsPointXY, QgsVectorFileWriter, 
    QgsCoordinateReferenceSystem, QgsCoordinateTransformContext
)
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'geo_linkage_dialog.ui'))

class GeoLinkageDialog(QDialog, FORM_CLASS):
    """
    GeoLinkageDialog class represents the main user interface dialog for the GeoLinkage plugin.
    It manages user inputs, layer selections, attribute mappings, and triggers the core processing.

    Attributes:
    ----------
    No explicitly defined attributes. All UI elements are inherited from FORM_CLASS and initialized via setupUi.

    Methods:
    --------
    _setup_layer_filters():
        Applies geometry filters to the layer combo boxes (Polygon, Point, Line).
        
    _connect_signals():
        Connects GUI events (clicks, state changes, layer changes) to Python functions.
        
    _sync_initial_layers():
        Forces the synchronization between active layers and their respective field combo boxes on startup.
        
    _populate_ds_list():
        Searches all polygon layers in the project and populates the Demand Sites list widget.
        
    _update_field_layer(layer, field_comboboxes):
        Updates a list of field combo boxes to show the attributes of a given layer.
        
    toggle_grid_inputs():
        Toggles the visibility between the extracted grid and MODFLOW generation frames based on user selection.
        
    select_results_folder():
        Opens a directory dialog for selecting the output results folder.
        
    select_modflow_file():
        Opens a file dialog for selecting a MODFLOW (.dis or .nam) file.
        
    select_ds_file():
        Opens a file dialog for selecting a text file containing demand site information.
        
    _generate_grid_from_modflow(modflow_file_path, x_ll, y_ll, z_rot):
        Generates a temporary QGIS vector layer representing the grid from a MODFLOW file using the flopy library.
        
    run_geolinkage():
        Gathers all user inputs from the UI, packages them into a payload, and invokes the AppKernel to process the data.
    """
    def __init__(self, parent=None):
        super(GeoLinkageDialog, self).__init__(parent)
        self.setupUi(self)

        self._setup_layer_filters()
        self._connect_signals()
        self._populate_ds_list() 
        QTimer.singleShot(200, self._sync_initial_layers)
        self.toggle_grid_inputs()

    def _setup_layer_filters(self):
        self.cmb_layer_malla.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.cmb_layer_cuencas.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.cmb_layer_gw.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.cmb_layer_nodes.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.cmb_layer_arcs.setFilters(QgsMapLayerProxyModel.LineLayer)

    def _connect_signals(self):        
        self.btn_explore_folder.clicked.connect(self.select_results_folder)
        self.btn_explore_modflow.clicked.connect(self.select_modflow_file)
        self.btn_explore_ds.clicked.connect(self.select_ds_file)
        self.btn_refresh_ds.clicked.connect(self._populate_ds_list)
        
        # run
        self.btn_run.clicked.connect(self.run_geolinkage)
        
        # modflow checkbox
        self.chk_modflow.stateChanged.connect(self.toggle_grid_inputs)

        # layer - column vinculation
        self.cmb_layer_malla.layerChanged.connect(lambda layer: self._update_field_layer(layer, [self.cmb_field_row, self.cmb_field_col, self.cmb_field_cat]))
        self.cmb_layer_cuencas.layerChanged.connect(lambda layer: self._update_field_layer(layer, [self.cmb_field_nombre_cuenca]))
        self.cmb_layer_gw.layerChanged.connect(lambda layer: self._update_field_layer(layer, [self.cmb_field_nombre_gw]))
        self.cmb_layer_nodes.layerChanged.connect(lambda layer: self._update_field_layer(layer, [self.cmb_field_node_name, self.cmb_field_node_type]))
        self.cmb_layer_arcs.layerChanged.connect(lambda layer: self._update_field_layer(layer, [self.cmb_field_arc_name]))

    def _sync_initial_layers(self):
        if self.cmb_layer_malla.currentLayer():
            self._update_field_layer(self.cmb_layer_malla.currentLayer(), [self.cmb_field_row, self.cmb_field_col, self.cmb_field_cat])
            
        if self.cmb_layer_cuencas.currentLayer():
            self._update_field_layer(self.cmb_layer_cuencas.currentLayer(), [self.cmb_field_nombre_cuenca])
            
        if self.cmb_layer_gw.currentLayer():
            self._update_field_layer(self.cmb_layer_gw.currentLayer(), [self.cmb_field_nombre_gw])
            
        if self.cmb_layer_nodes.currentLayer():
            self._update_field_layer(self.cmb_layer_nodes.currentLayer(), [self.cmb_field_node_name, self.cmb_field_node_type])
            
        if self.cmb_layer_arcs.currentLayer():
            self._update_field_layer(self.cmb_layer_arcs.currentLayer(), [self.cmb_field_arc_name])

    def _populate_ds_list(self):
        # clean the list in case of reloads
        self.list_widget_ds.clear() 
        
        # iterate over all layers loaded in the current project
        layers = QgsProject.instance().mapLayers().values()
        
        for layer in layers:
            if layer.type() == QgsMapLayerType.VectorLayer and layer.geometryType() == QgsWkbTypes.PolygonGeometry:
                item = QListWidgetItem(layer.name())
                
                # enable checkbox
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked) # unchecked by default
                item.setData(Qt.ItemDataRole.UserRole, layer.id()) 
                
                self.list_widget_ds.addItem(item)

    def _update_field_layer(self, layer, field_comboboxes):
        for cmb in field_comboboxes:
            cmb.setLayer(layer)

    def toggle_grid_inputs(self):
        if self.chk_modflow.isChecked():
            self.frame_extracted_grid.setVisible(False)
            self.frame_modflow.setVisible(True)
        else:
            self.frame_extracted_grid.setVisible(True)
            self.frame_modflow.setVisible(False)

    # path selection functions 
    def select_results_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select results folder", "")
        if folder:
            self.txt_output_folder.setText(folder)

    def select_modflow_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select .dis or .nam file", "", "MODFLOW files (*.dis *.nam)")
        if filename:
            self.txt_modflow_path.setText(filename)

    def select_ds_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select file with Demand Sites", "", "Text files (*.txt)")
        if filename:
            self.txt_ds_file.setText(filename)

    def _generate_grid_from_modflow(self, modflow_file_path: str, x_ll: float, y_ll: float, z_rot: float) -> QgsVectorLayer:
        try:
            import flopy
        except ImportError:
            raise RuntimeError("The 'flopy' library is not installed in the QGIS Python environment.")

        # MODFLOW load
        model_dir = os.path.dirname(modflow_file_path)
        model_name = os.path.basename(modflow_file_path)
        
        try:
            ml = flopy.modflow.Modflow.load(model_name, model_ws=model_dir, exe_name='mf2005', verbose=False, check=False)
        except Exception as e:
            raise RuntimeError(f"Failed to read the MODFLOW model with flopy: {e}")

        # qgis project crs
        crs = QgsProject.instance().crs()
        if not crs.isValid():
            raise RuntimeError("The current QGIS project does not have a Coordinate Reference System defined. Please assign one before processing.")
        # crs check
        if crs.isGeographic():
            raise ValueError(
                f"Topological Error: The QGIS project is configured in a geographic system ({crs.authid()}). "
                "MODFLOW strictly requires a projected system (in meters or feet, e.g. UTM). "
                "Change the project CRS in the QGIS settings before compiling the mesh."
            )

        epsg_code = crs.postgisSrid()

        # spatial config
        try:
            ml.modelgrid.set_coord_info(xoff=x_ll, yoff=y_ll, angrot=z_rot, epsg=epsg_code, merge_coord_info=True)
        except ValueError as e:
            raise ValueError(f"FloPy's spatial engine rejected the input coordinates: {e}")

        # temp file name to avoid windows file lock
        temp_dir = tempfile.gettempdir()
        unique_id = uuid.uuid4().hex
        shapefile_path = os.path.join(temp_dir, f"mf_grid_{unique_id}.shp")
        
        # physical write through pyqgis
        try:            
            nrow = ml.modelgrid.nrow
            ncol = ml.modelgrid.ncol
            
            # .shp field structure
            fields = QgsFields()
            fields.append(QgsField("row", QVariant.Int))
            fields.append(QgsField("column", QVariant.Int))
            fields.append(QgsField("node", QVariant.Int))
            
            # Extract MODFLOW projection if exists, otherwise use local coordinate system
            epsg = ml.modelgrid.epsg
            crs = QgsCoordinateReferenceSystem(f"EPSG:{epsg}") if epsg else QgsCoordinateReferenceSystem()
            
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "ESRI Shapefile"
            options.fileEncoding = "UTF-8"
            
            # QGIS writer 
            writer = QgsVectorFileWriter.create(
                shapefile_path,
                fields,
                QgsWkbTypes.Polygon,
                crs,
                QgsCoordinateTransformContext(),
                options
            )            
            if writer.hasError() != QgsVectorFileWriter.NoError:
                raise RuntimeError(f"The QGIS engine failed to create the file: {writer.errorMessage()}")
                
            # Extract each cell and write it to disk
            for i in range(nrow):
                for j in range(ncol):
                    node_id = i * ncol + j + 1
                    
                    # cell vertices coordinates
                    vertices = ml.modelgrid.get_cell_vertices(i, j)
                    
                    # pyqgis polygon
                    points = [QgsPointXY(v[0], v[1]) for v in vertices]
                    geom = QgsGeometry.fromPolygonXY([points])
                    
                    # attributes
                    feat = QgsFeature(fields)
                    feat.setGeometry(geom)
                    feat.setAttribute("row", i + 1)
                    feat.setAttribute("column", j + 1)
                    feat.setAttribute("node", int(node_id))
                    
                    writer.addFeature(feat)
                    
            # clear ram
            del writer 
            
        except Exception as e:
            raise RuntimeError(f"Critical failure when compiling the mesh with PyQGIS: {e}")

        # Convert to QgsVectorLayer and strict validation
        grid_layer = QgsVectorLayer(shapefile_path, "Malla MODFLOW (Temporal)", "ogr")
        
        if not grid_layer.isValid():
            raise RuntimeError("QGIS failed to load the Shapefile generated by flopy.")

        # Force QGIS to understand that this layer uses the same CRS as the project
        grid_layer.setCrs(crs)

        return grid_layer

    def run_geolinkage(self):
        output_path = self.txt_output_folder.text()
        run_geochecker = self.chk_run_geochecker.isChecked()

        if not output_path:
            QMessageBox.warning(self, "Validation Error", "You must define an output directory.")
            return

        # Build payload for the backend
        data_payload = {}
        resolved_mesh_layer = None
        
        try:
            # MODFLOW Mesh layer resolution
            if self.chk_modflow.isChecked():
                mf_path = self.txt_modflow_path.text()
                x_val = self.spin_x.value()
                y_val = self.spin_y.value()
                z_val = self.spin_z.value()
                
                if not mf_path or not os.path.exists(mf_path):
                    QMessageBox.warning(self, "Error", "You must provide a valid path to the MODFLOW file (.dis or .nam).")
                    return
                    
                resolved_mesh_layer = self._generate_grid_from_modflow(mf_path, x_val, y_val, z_val)
                
                col_row_name = 'row'
                col_col_name = 'column'
                col_cat_name = 'node' 
            else:
                resolved_mesh_layer = self.cmb_layer_malla.currentLayer()
                col_row_name = self.cmb_field_row.currentText()
                col_col_name = self.cmb_field_col.currentText()
                col_cat_name = self.cmb_field_cat.currentText()

                if not resolved_mesh_layer:
                    QMessageBox.warning(self, "Error", "You must select an Extracted Mesh layer.")
                    return

            data_payload['grid'] = {
                'col_row': col_row_name,
                'col_col': col_col_name,
                'col_cat': col_cat_name
            }

            # Catchment data extraction 
            if self.cmb_layer_cuencas.currentLayer():
                data_payload['catchment'] = {
                    'catchment_layer': self.cmb_layer_cuencas.currentLayer(),
                    'col_name': self.cmb_field_nombre_cuenca.currentText()
                }

            # Groundwater data extraction
            if self.cmb_layer_gw.currentLayer():
                data_payload['gw'] = {
                    'gw_layer': self.cmb_layer_gw.currentLayer(),
                    'col_name': self.cmb_field_nombre_gw.currentText()
                }

            # River data extraction
            if self.cmb_layer_arcs.currentLayer() and self.cmb_layer_nodes.currentLayer():
                data_payload['river'] = {
                    'river_layer': self.cmb_layer_arcs.currentLayer(),
                    'node_layer': self.cmb_layer_nodes.currentLayer(),
                    'col_river_name': self.cmb_field_arc_name.currentText(),
                    'col_node_name': self.cmb_field_node_name.currentText(),
                    'col_node_type': self.cmb_field_node_type.currentText()
                }

            # Demand Sites extraction
            selected_ds_layers = []
            for i in range(self.list_widget_ds.count()):
                item = self.list_widget_ds.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    layer_id = item.data(Qt.ItemDataRole.UserRole)
                    capa = QgsProject.instance().mapLayer(layer_id)
                    if capa:
                        selected_ds_layers.append(capa)

            wells_txt_file = self.txt_ds_file.text()

            data_payload['ds'] = {
                'wells_file_path': wells_txt_file if wells_txt_file else None,
                'demand_site_layers': selected_ds_layers,
                'col_name': self.txt_ds_prefix.text() 
            }
            
            kernel = AppKernel(debug=True)
            
            # Message Bar with infinite progress
            progress_msg = iface.messageBar().createMessage("GeoLinkage", "Running plugin, please wait...")
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 0)
            progress_msg.layout().addWidget(progress_bar)
            iface.messageBar().pushWidget(progress_msg, Qgis.MessageLevel.Info)
            
            # Set wait cursor
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            QApplication.processEvents()
            
            try:
                kernel.run(
                    grid_layer=resolved_mesh_layer, 
                    layers_dict=data_payload,
                    output_path=output_path,
                    run_geochecker=run_geochecker
                )
            finally:
                # reset cursor and clean message bar
                QApplication.restoreOverrideCursor()
                iface.messageBar().clearWidgets()
            
            if run_geochecker:
                QMessageBox.information(self, "Success", "GeoLinkage and Geochecker processing completed successfully.")
            else:
                QMessageBox.information(self, "Success", "GeoLinkage processing completed successfully.")

            # open results folder
            if sys.platform == 'win32':
                os.startfile(output_path)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', output_path])
            else:
                subprocess.Popen(['xdg-open', output_path])

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Processing Error", f"Backend execution failed:\n{str(e)}")


class GeoLinkagePlugin:
    """
    GeoLinkagePlugin class is the main entry point for the QGIS plugin.
    It handles the initialization, integration with the QGIS interface, and execution of the plugin's dialog.

    Attributes:
    ----------
    iface : QgisInterface
        Reference to the QGIS interface instance.
    
    action : QAction
        The action added to the QGIS menu to trigger the plugin.
        
    dialog : GeoLinkageDialog
        The main dialog window of the plugin.

    Methods:
    --------
    initGui():
        Initializes the plugin's graphical user interface, creating the menu action.
        
    unload():
        Removes the plugin menu item and cleans up resources when the plugin is disabled.
        
    run():
        Instantiates (if necessary) and displays the main plugin dialog.
    """
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        self.action = QAction("Run GeoLinkage", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("&GeoLinkage", self.action)

    def unload(self):
        self.iface.removePluginMenu("&GeoLinkage", self.action)
        if self.action:
            self.action.deleteLater()

    def run(self):
        if not self.dialog:
            self.dialog = GeoLinkageDialog(self.iface.mainWindow())
        self.dialog.show()