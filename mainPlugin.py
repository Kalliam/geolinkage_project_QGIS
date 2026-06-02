import os
import tempfile
import uuid
import numpy as np
from flopy.export.shapefile_utils import write_grid_shapefile
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt import uic
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsVectorLayer, QgsMapLayerType, QgsWkbTypes
from .GeoLinkage.AppKernel import AppKernel

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'geo_linkage_dialog.ui'))

class GeoLinkageDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        super(GeoLinkageDialog, self).__init__(parent)
        self.setupUi(self)

        self._setup_layer_filters()
        self._connect_signals()
        self._populate_ds_list() 
        QTimer.singleShot(200, self._sync_initial_layers)
        self.toggle_grid_inputs()

    def _setup_layer_filters(self):
        """Aplica filtros restrictivos de geometría a los selectores de capa."""
        self.cmb_layer_malla.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.cmb_layer_cuencas.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.cmb_layer_gw.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.cmb_layer_nodes.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.cmb_layer_arcs.setFilters(QgsMapLayerProxyModel.LineLayer)

    def _connect_signals(self):
        """Conecta eventos de la interfaz gráfica a funciones de Python."""
        
        # exploracion de archivos
        self.btn_explore_folder.clicked.connect(self.select_results_folder)
        self.btn_explore_modflow.clicked.connect(self.select_modflow_file)
        self.btn_explore_ds.clicked.connect(self.select_ds_file)
        self.btn_refresh_ds.clicked.connect(self._populate_ds_list)
        
        # run
        self.btn_run.clicked.connect(self.run_geolinkage)
        
        # modflow checkbox
        self.chk_modflow.stateChanged.connect(self.toggle_grid_inputs)

        # vinculacion capa - columnas
        self.cmb_layer_malla.layerChanged.connect(lambda layer: self._update_field_layer(layer, [self.cmb_field_row, self.cmb_field_col, self.cmb_field_cat]))
        self.cmb_layer_cuencas.layerChanged.connect(lambda layer: self._update_field_layer(layer, [self.cmb_field_nombre_cuenca]))
        self.cmb_layer_gw.layerChanged.connect(lambda layer: self._update_field_layer(layer, [self.cmb_field_nombre_gw]))
        self.cmb_layer_nodes.layerChanged.connect(lambda layer: self._update_field_layer(layer, [self.cmb_field_node_name, self.cmb_field_node_type]))
        self.cmb_layer_arcs.layerChanged.connect(lambda layer: self._update_field_layer(layer, [self.cmb_field_arc_name]))

    def _sync_initial_layers(self):
        """Fuerza la sincronización entre capas y campos al abrir el plugin."""
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
        """Busca todas las capas de polígonos en el proyecto y las añade al QListWidget."""
        # Limpiar la lista en caso de recargas
        self.list_widget_ds.clear() 
        
        # Iterar sobre todas las capas cargadas en el proyecto actual
        layers = QgsProject.instance().mapLayers().values()
        
        for layer in layers:
            # filtrar por capas poligonales
            if layer.type() == QgsMapLayerType.VectorLayer and layer.geometryType() == QgsWkbTypes.PolygonGeometry:
                item = QListWidgetItem(layer.name())
                
                # habilitar el checkbox en el item
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked) # Desmarcado por defecto
                item.setData(Qt.ItemDataRole.UserRole, layer.id()) 
                
                self.list_widget_ds.addItem(item)

    def _update_field_layer(self, layer, field_comboboxes):
        """Asigna la capa activa a los selectores de campos."""
        for cmb in field_comboboxes:
            cmb.setLayer(layer)

    def toggle_grid_inputs(self):
        """Alterna la visibilidad entre malla extraída y generación MODFLOW."""
        if self.chk_modflow.isChecked():
            self.frame_extracted_grid.setVisible(False)
            self.frame_modflow.setVisible(True)
        else:
            self.frame_extracted_grid.setVisible(True)
            self.frame_modflow.setVisible(False)

    #  funciones de selección de rutas 
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
        """
        Read a MODFLOW file using flopy, generate a shapefile with the grid,
        ensure CRS compatibility and prevent file locks in Windows.
        """
        try:
            import flopy
        except ImportError:
            raise RuntimeError("La librería 'flopy' no está instalada en el entorno de Python de QGIS.")

        # Carga MODFLOW
        model_dir = os.path.dirname(modflow_file_path)
        model_name = os.path.basename(modflow_file_path)
        
        try:
            ml = flopy.modflow.Modflow.load(model_name, model_ws=model_dir, exe_name='mf2005', verbose=False, check=False)
        except Exception as e:
            raise RuntimeError(f"Fallo al leer el modelo MODFLOW con flopy: {e}")

        # Sistema de Coordenadas del proyecto QGIS, reemplaza al antiguo input manual de EPSG
        crs = QgsProject.instance().crs()
        if not crs.isValid():
            raise RuntimeError("El proyecto actual de QGIS no tiene un Sistema de Coordenadas definido. Asigne uno antes de procesar.")
        
        epsg_code = crs.postgisSrid()

        # Configuración Espacial
        ml.modelgrid.set_coord_info(xoff=x_ll, yoff=y_ll, angrot=z_rot, epsg=epsg_code, merge_coord_info=True)

        # Generación de Nombre Único para evitar PermissionError (File Lock en Windows)
        temp_dir = tempfile.gettempdir()
        unique_id = uuid.uuid4().hex
        shapefile_path = os.path.join(temp_dir, f"mf_grid_{unique_id}.shp")
        
        # Escritura Física - colapso por array vacio en Flopy
        try:
            # matriz estructurada de MODFLOW
            nrow = ml.modelgrid.nrow
            ncol = ml.modelgrid.ncol
            
            # matrices 2D con los índices correspondientes 
            row_arr = np.repeat(np.arange(1, nrow + 1)[:, None], ncol, axis=1)
            col_arr = np.repeat(np.arange(1, ncol + 1)[None, :], nrow, axis=0)
            node_arr = np.arange(1, nrow * ncol + 1).reshape((nrow, ncol))
            
            # atributos requeridos por GeoLinkage
            atributos_grilla = {
                'row': row_arr,
                'column': col_arr,
                'node': node_arr
            }
            
            # Escribir el Shapefile llamando a la funcion directamente
            write_grid_shapefile(
                filename=shapefile_path, 
                mg=ml.modelgrid, 
                array_dict=atributos_grilla
            )
            
        except Exception as e:
            raise RuntimeError(f"Error de flopy al escribir el Shapefile: {e}")

        # Conversión a QgsVectorLayer y validación estricta
        grid_layer = QgsVectorLayer(shapefile_path, "Malla MODFLOW (Temporal)", "ogr")
        
        if not grid_layer.isValid():
            raise RuntimeError("QGIS falló al cargar el Shapefile generado por flopy.")

        # Forzamos a QGIS a entender que esta capa usa el mismo CRS del proyecto
        grid_layer.setCrs(crs)

        return grid_layer

    def run_geolinkage(self):
        """Recolecta los datos de la interfaz y ejecuta el backend."""
        ruta_salida = self.txt_output_folder.text()
        run_geochecker = self.chk_run_geochecker.isChecked()

        if not ruta_salida:
            QMessageBox.warning(self, "Error de Validación", "Debe definir un directorio de salida.")
            return

        # Construcción del Payload para el Backend
        data_payload = {}
        capa_malla_resuelta = None
        
        try:
            # Resolución de la Capa de Malla
            if self.chk_modflow.isChecked():
                mf_path = self.txt_modflow_path.text()
                x_val = self.spin_x.value()
                y_val = self.spin_y.value()
                z_val = self.spin_z.value()
                
                if not mf_path or not os.path.exists(mf_path):
                    QMessageBox.warning(self, "Error", "Debe proporcionar una ruta válida al archivo MODFLOW (.dis o .nam).")
                    return
                    
                capa_malla_resuelta = self._generate_grid_from_modflow(mf_path, x_val, y_val, z_val)
                
                col_row_name = 'row'
                col_col_name = 'column'
                col_cat_name = 'node' 
            else:
                capa_malla_resuelta = self.cmb_layer_malla.currentLayer()
                col_row_name = self.cmb_field_row.currentText()
                col_col_name = self.cmb_field_col.currentText()
                col_cat_name = self.cmb_field_cat.currentText()

                if not capa_malla_resuelta:
                    QMessageBox.warning(self, "Error", "Debe seleccionar una capa de Malla Extraída.")
                    return

            data_payload['grid'] = {
                'col_row': col_row_name,
                'col_col': col_col_name,
                'col_cat': col_cat_name
            }

            # Extracción de datos de Cuencas 
            if self.cmb_layer_cuencas.currentLayer():
                data_payload['catchment'] = {
                    'catchment_layer': self.cmb_layer_cuencas.currentLayer(),
                    'col_name': self.cmb_field_nombre_cuenca.currentText()
                }

            # Extracción de datos de Aguas Subterráneas
            if self.cmb_layer_gw.currentLayer():
                data_payload['gw'] = {
                    'gw_layer': self.cmb_layer_gw.currentLayer(),
                    'col_name': self.cmb_field_nombre_gw.currentText()
                }

            # Extracción del Esquema de Ríos
            if self.cmb_layer_arcs.currentLayer() and self.cmb_layer_nodes.currentLayer():
                data_payload['river'] = {
                    'river_layer': self.cmb_layer_arcs.currentLayer(),
                    'node_layer': self.cmb_layer_nodes.currentLayer(),
                    'col_river_name': self.cmb_field_arc_name.currentText(),
                    'col_node_name': self.cmb_field_node_name.currentText(),
                    'col_node_type': self.cmb_field_node_type.currentText()
                }

            # Extracción de Sitios de Demanda
            capas_ds_seleccionadas = []
            for i in range(self.list_widget_ds.count()):
                item = self.list_widget_ds.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    layer_id = item.data(Qt.ItemDataRole.UserRole)
                    capa = QgsProject.instance().mapLayer(layer_id)
                    if capa:
                        capas_ds_seleccionadas.append(capa)

            archivo_pozos_txt = self.txt_ds_file.text()

            data_payload['ds'] = {
                'wells_file_path': archivo_pozos_txt if archivo_pozos_txt else None,
                'demand_site_layers': capas_ds_seleccionadas,
                'col_name': self.txt_ds_prefix.text() 
            }
            
            kernel = AppKernel(debug=True)
            
            kernel.run(
                grid_layer=capa_malla_resuelta, 
                layers_dict=data_payload,
                output_path=ruta_salida,
                run_geochecker=run_geochecker
            )
            
            if run_geochecker:
                QMessageBox.information(self, "Éxito", "El procesamiento de GeoLinkage y Geochecker ha concluido correctamente.")
            else:
                QMessageBox.information(self, "Éxito", "El procesamiento de GeoLinkage ha concluido correctamente.")

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error de Procesamiento", f"Fallo en la ejecución del backend:\n{str(e)}")


class GeoLinkagePlugin:
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