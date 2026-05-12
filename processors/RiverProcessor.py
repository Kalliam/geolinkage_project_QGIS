import time
from collections import namedtuple
from qgis.core import QgsVectorLayer, QgsFeature, QgsField, QgsSpatialIndex
from PyQt5.QtCore import QVariant

from processors.FeatureProcessor import FeatureProcess
from utils.RiverNode import RiverNode


class RiverProcess(FeatureProcess):
    """
        It contains the DS processor particular logic.

        Process rivers generating a vector map from surface maps (node and arc maps).
        Through the water injection or extraction nodes present in the surface maps, it determines the river segments o
        identifying for one of these nodes, if the segment is the upper or lower one according to river flow.
        This is required because for linking it is necessary to know where the water is drawn from.

        By default, 1 column is generated in final file metadata (shapefile with linking grid). In which it is stored
        segment and the river following the form: [segment name],[river name].


        Attributes:
        ----------
        cells : Dict[namedtuple<Cell>, Dict[str, Dict[str, str|int]]
            Inherited from FeatureProcess class.
            It is used to store cell-feature relationship. It is indexed by DS grid cells that
            they have been intersected with the feature map. Because a cell can be intersected by more than one
            map geometry, access is given by: [cell] -> [geo_intersected] -> [cell_feature_relationship_data].
            The stored values are:
                - 'length': arc length which represents the river subsegment within the cell.
                - 'cell_id': cell ID. (ID in gw grid's vector map)
                - 'segment_name': River segment name. (ex: before [node_in_river])
                - 'river_name': river name in surface arc map.
                - 'name': name used to make the link. Format: [river name],[segment name].
                - 'map_name': map name. (name used by GRASS)

        cell_ids: Dict[namedtuple<Cell>, Dict[str, str|int|List<data>]]
            Inherited from FeatureProcess class.
            Store for each cell the geometry (s) that will actually be stored in final file. Structure and stored
            values details are in FeatureProcess class.

        rivers : Dict[int, Dict[str, str | int]]
            It is used to store river information obtained from surface map analysis.
            (Stored data details are in GeoKernel class).

        _river_names : Dict[str, int]
            It is used internally to directly access rivers data by name.

        river_break_nodes : Dict[int, Dict[str, str | int | bool]]
            Stores nodes that modify the river flow. Indexed by node ID.

                Almacena los nodos que intervienen el flujo del rio. obtenidos del analisis de las geometrias del
                mapa de nodos del esquema superficial. Indexado por el ID del nodo.

        root : RiverNode
            RiverNode instance that identifies access point to river segments, using the nodes of the surface map
            that affect the river flow.



        Methods:
        -------
        _start(self, linkage_name: str)
            Runs procedure for successful processing between feature map and inital GW grid.
            The 'linkage_name' parameter refers to GW grid vector map.

        run(self, linkage_name: str)
            Starts processing and records basic statistics of the execution.
            The 'linkage_name' parameter refers to groundwater grid vector map.

        set_data_from_geo(self)
            Extracts rivers and nodes data from analyzed surface maps (arc and node).

        make_cell_data_by_main_map(self, map_name, inter_map_name, inter_map_geo_type)
            Creates the structure that store necessary river and segments data of the main map.
            A main map generates a mandatory column for segments in final file metadata (even if its values are null).

        make_cell_data_by_secondary_maps(self, map_name, inter_map_name, inter_map_geo_type)
            Currently, this method is not used because there is only one main map for rivers.

        _make_river_tree_segments_structure(self)
            Create necessary structure to identify river segments through an RiverNode instance.
            All nodes involved in the river flows are checked, identifying the anterior and posterior segment
            each one of them.

        _set_break_names_in_segments_map(self, segments_map_name='arc_segments')
            Create segments vector map from rivers found in surface arc map. The parameters 'segments_map_name' is used
            to give the name to the map, That map is intersected with GW grid vector map.



        Example:
        --------
        >>> from processors.GeoKernel import GeoKernel
        >>> from processors.RiverProcessor import RiverProcess
        >>> from utils.Config import ConfigApp
        >>> from utils.Errors import ErrorManager

        >>> epsg_code, gisdb, location, mapset = 30719, '/tmp', 'test', 'PERMANENT'
        >>> file_main_map, grid_vector_map = '/tmp/arc_map.shp', 'initial_gw_grid'

        >>> config = ConfigApp(epsg_code=epsg_code, gisdb=gisdb, location=location, mapset=mapset)
        >>> error = ErrorManager(config=config)
        >>> geo = GeoKernel(config=config, err=error)

        >>> processor = RiverProcess(geo=geo, config=config, err=error)
        >>> processor.config.set_columns_to_save(processor.get_feature_type(), columns_to_save=1)
        >>> processor.config.set_order_criteria(processor.get_feature_type(), order_criteria='length')
        >>> processor.set_map_name(map_name='arc_vector_map', map_path=file_main_map, is_main_file=True)

        >>> processor.import_maps()
        >>> processor.check_names_with_geo()
        >>> processor.check_names_between_maps()
        >>> processor.make_segment_map(is_main_file=True)

        >>> if not processor.check_errors():  # or processor.run(linkage_name=grid_vector_map)
        >>>     processor.inter_map_with_linkage(linkage_name=grid_vector_map)
        >>>     processor.make_grid_cell()

        >>>     summary = processor.get_summary()

        >>>     inputs = summary.print_input_params()  # inputs and stats
        >>>     real_lines = summary.get_process_lines(with_ui=True)
        >>>     errors = summary.print_errors()
        >>>     warnings = summary.print_warnings()

        >>>     print(inputs)

        """

    def __init__(self, debug: bool = False):
        super().__init__(debug=debug)
        self.root = None

    #@TimerSummary.timeit
    def run(self, grid_layer, river_layer, node_layer, col_river, col_segment, col_node_type, col_node_name, col_row, col_col, col_cat):
        # Utils.show_title(msg_title='RIVERS', title_color=ui.green)
        ts = time.time()

        segmented_river_layer = self.make_segmented_river_layer(
            river_layer=river_layer,
            node_layer=node_layer,
            col_node_type=col_node_type,
            col_node_name=col_node_name,
            col_river_name=col_river
        )

        # 2. Intersección con la Malla
        _err_r, inter_river_layer = self.inter_map_with_linkage(segmented_river_layer, grid_layer, 'river_name')
        
        if _err_r:
            raise RuntimeError(f'[EXIT] ERROR AL INTERSECTAR RÍOS CON [{grid_layer.name()}]')

        # 3. Procesamiento Interno
        self.process_intersection(
            inter_layer=inter_river_layer,
            map_name=river_layer.name(),
            col_river='river_name', # Columna generada en el paso 1
            col_segment='segment_break_name', # Columna generada en el paso 1
            col_row=col_row, 
            col_col=col_col, 
            col_cat=col_cat
        )

        self._set_cell_by_criteria(by_field='length')

        te = time.time()
        # Set stats into summary
        # # set cells
        self.stats['PROCESSED TIME'] = '{0:.2f} seg'.format(te - ts)
        self.stats['PROCESSED CELLS'] = len(self.cells)

        return self.stats




    def _make_river_tree_segments_structure(self, river_layer, node_layer, col_node_type, col_node_name, col_river_name):
        """
        Reconstruye el árbol de RiverNode leyendo directamente desde QGIS y calculando
        las distancias de los nodos a lo largo de las líneas de los ríos.
        """
        self.root = RiverNode(node_id=-1, node_name='root', node_type=0, node_distance=0)

        # 1. Crear un Índice Espacial de los Ríos para búsquedas ultra rápidas
        indice_rios = QgsSpatialIndex(river_layer.getFeatures())
        
        # Diccionario auxiliar para acceder a los ríos por ID rápidamente
        dict_rios = {f.id(): f for f in river_layer.getFeatures()}

        # 2. Recorremos los nodos (puntos) del esquema WEAP
        for feature_nodo in node_layer.getFeatures():
            tipo_nodo = feature_nodo[col_node_type]
            
            # [WEAP LOGIC]: Ignoramos los Canales (Tipo 15 en WEAP)
            if tipo_nodo == 15:
                continue

            geom_nodo = feature_nodo.geometry()
            if not geom_nodo:
                continue

            # 3. Encontrar el río más cercano a este nodo
            # nearestNeighbor devuelve una lista de IDs (pedimos el primero: [0])
            id_rio_cercano = indice_rios.nearestNeighbor(geom_nodo.asPoint(), 1)[0]
            feature_rio = dict_rios[id_rio_cercano]
            geom_rio = feature_rio.geometry()

            # --- LA MAGIA MATEMÁTICA DE PYQGIS ---
            # lineLocatePoint te dice exactamente a cuántos metros desde el inicio del río 
            # se encuentra proyectado este punto. ¡Reemplaza todo el motor de GRASS!
            distancia_al_nodo = geom_rio.lineLocatePoint(geom_nodo)

            # Extraemos atributos para el RiverNode
            nodo_id = feature_nodo.id()
            nodo_nombre = feature_nodo[col_node_name]
            rio_id = feature_rio.id()
            rio_nombre = feature_rio[col_river_name]
            
            # Asumimos que cat es el ID para simplificar (ajusta según tu lógica)
            rio_cat = feature_rio.id() 

            # 4. Crear la instancia de RiverNode (Mantenemos tu lógica original)
            river_node = RiverNode(
                node_id=nodo_id, 
                node_name=nodo_nombre, 
                node_type=tipo_nodo,
                node_distance=distancia_al_nodo, # ¡Calculado nativamente!
                root_node=self.root, 
                parent=self.root
            )
            
            # Guardamos las coordenadas X, Y
            punto_xy = geom_nodo.asPoint()
            river_node.set_coords(punto_xy.x(), punto_xy.y())

            # Asignamos el río principal al nodo
            river_node.set_main_river(rio_id, rio_nombre, rio_cat, distancia_al_nodo)

            # [WEAP LOGIC]: Si es un nodo Tributario (Tipo 13), habría que buscar el río secundario.
            if tipo_nodo == 13:
                # Nota: Aquí deberías implementar la búsqueda del 2do río más cercano
                # (el tributario que desemboca aquí) usando indice_rios.nearestNeighbor(..., 2)
                pass

        # Devolvemos el árbol construido
        return self.root

    def make_segmented_river_layer(self, river_layer, node_layer, col_node_type, col_node_name, col_river_name):
        """
        Reemplaza a make_segment_map() y _set_break_names_in_segments_map().
        Corta las líneas de los ríos en memoria basándose en el árbol de RiverNode.
        """
        # 1. Llamamos al "Cerebro" para armar el árbol y obtener las distancias lógicas
        self.root = self._make_river_tree_segments_structure(
            river_layer, node_layer, col_node_type, col_node_name, col_river_name
        )
        
        if not self.root or not self.root.get_segments_list():
            # Si no hay nodos que corten el río, devolvemos la capa original intacta
            return river_layer

        # 2. Crear una nueva capa temporal en memoria (El lienzo en blanco)
        crs = river_layer.crs().authid() # Copiamos el sistema de coordenadas
        segmented_layer = QgsVectorLayer(f"LineString?crs={crs}", "Rios_Segmentados", "memory")
        provider = segmented_layer.dataProvider()
        
        # Le creamos las columnas que necesitamos para el cruce final
        provider.addAttributes([
            QgsField("river_name", QVariant.String),
            QgsField("segment_break_name", QVariant.String)
        ])
        segmented_layer.updateFields()

        # 3. La Matemática (Cortar las líneas)
        new_features = []
        
        # Iteramos sobre los ríos originales
        for feature_river in river_layer.getFeatures():
            # (Aquí viene la lógica de conexión con RiverNode)
            # Le preguntamos al árbol: "¿En cuántos pedazos se divide este río y a qué distancias?"
            # Supongamos que el árbol nos dice: "Se divide en 2: de 0m a 400m, y de 400m a 1000m"
            
            river_segments = self.get_river_segments_from_tree(feature_river) 

            
            for segment in river_segments:
                dist_start = segment['start_distance']
                dist_end = segment['end_distance']
                
                # LA MAGIA DE QGIS: Cortar la línea matemáticamente
                cut_geometry = feature_river.geometry().curveSubstring(dist_start, dist_end)
               
                # Empaquetar el nuevo pedazo con su nombre
                new_feature = QgsFeature(segmented_layer.fields())
                new_feature.setGeometry(cut_geometry)
                new_feature.setAttributes([segment['river_name'], segment['segment_break_name']])
                
                new_features.append(new_feature)

        # 4. Guardar los pedazos en la capa y devolverla
        provider.addFeatures(new_features)
        segmented_layer.updateExtents()

        return segmented_layer

    def get_river_segments_from_tree(self, feature_river):
        """
        TODO: PENDIENTE DE IMPLEMENTACIÓN.
        Debe interactuar con self.root (RiverNode) y retornar una lista de diccionarios 
        con este formato basándose en los cortes del río específico:
        [
            {'start_distance': 0.0, 'end_distance': 450.5, 'river_name': 'Rio_A', 'segment_break_name': 'Upper'},
            {'start_distance': 450.5, 'end_distance': 1000.0, 'river_name': 'Rio_A', 'segment_break_name': 'Lower'}
        ]
        """
        # Lógica provisional para evitar crash. Corta el río en un solo segmento completo.
        length = feature_river.geometry().length()
        return [{
            'start_distance': 0.0, 
            'end_distance': length, 
            'river_name': 'TEST', 
            'segment_break_name': 'TEST'
        }]

    # @main_task
    ## procesa la interseccion del mapa de rios con la malla de MODFLOW
    def process_intersection(self, inter_layer, map_name, col_river, col_segment, col_row, col_col, col_cat):
        Cell = namedtuple('Cell_river', ['row', 'col'])

        for feature in inter_layer.getFeatures():
            if not feature.hasGeometry():  # when topology has some errors
                # print("[ERROR] ", a.cat, a.id)
                continue
            
            river_name = feature[col_river]
            segment_name = feature[col_segment]
            area_row, area_col = feature[col_row], feature[col_col]
            cell_id = feature[col_cat]                

            line_length = feature.geometry().length() #porque es una linea (Arc)


            data = {
                'length': line_length,
                'cell_id': cell_id,
                'segment_name': segment_name,
                'river_name': river_name,
                'name': f"{river_name},{segment_name}",
                'map_name': map_name
            }

            cell = Cell(area_row, area_col)

            cell = Cell(area_row, area_col)
            self._set_cell(cell, river_name, data, by_field="length")