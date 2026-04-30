import time
from collections import namedtuple

from qgis.core import QgsVectorLayer

from utils.Errors import ErrorManager
from processors.FeatureProcessor import FeatureProcess
from processors.GeoKernel import GeoKernel
from utils.Utils import TimerSummary


class GroundwaterProcess(FeatureProcess):
    """
        Processes vector map associated with the groundwater ESRI Shapefile file (.shp) and contains geometries (areas)
        associated with this feature.

        It contains the groundwater processor particular logic.

        * Config File: ./config/config.json


        Attributes:
        ----------
        cells : Dict[namedtuple<Cell>, Dict[str, Dict[str, str|int]]
            Inherited from FeatureProcess class.
            It is used to store cell-feature relationship. It is indexed by groundwater grid cells that
            they have been intersected with the feature map. Because a cell can be intersected by more than one
            map geometry, access is given by: [cell] -> [geo_intersected] -> [cell_feature_relationship_data].
            The stored values are:
                - 'area': area occupied by geometry on the map.
                - 'cell_id': cell ID. (ID in gw vector map grid)
                - 'name': groundwater name.
                - 'map_name': groundwater map name. (name used by GRASS Platform)

        cell_ids: Dict[namedtuple<Cell>, Dict[str, str|int|List<data>]]
            Inherited from FeatureProcess class.
            Store for each cell the geometry (s) that will actually be stored in final file. Structure and stored
            values details are in FeatureProcess class.

        gws : Dict[int, Dict[str, str | int]]
            It is used to store groundwater information obtained from surface map analysis.
            (Stored data details are in GeoKernel class).

        _gw_names : Dict[str, int]
            It is used internally to directly access groundwater data by name.


        Methods:
        -------
        _start(self, linkage_name: str)
            Runs procedure for successful processing between feature map and inital GW grid.
            The 'linkage_name' parameter refers to groundwater grid vector map.

        run(self, linkage_name: str)
            Start processing and records basic statistics of the execution.
            The 'linkage_name' parameter refers to groundwater grid vector map.

        set_data_from_geo(self)
            Extracts groundwater data from analyzed surface maps (arc and node).

        make_cell_data_by_main_map(self, map_name, inter_map_name, inter_map_geo_type)
            Make the structure that store necessary groundwater data of the main map.
            A main map generates a mandatory column for groundwater in final file metadata (even if its values are null).

        make_cell_data_by_secondary_maps(self, map_name, inter_map_name, inter_map_geo_type)
            Currently, this method is not used because there is only one main map for groundwater.


        Example:
        --------
        >>> from processors.GeoKernel import GeoKernel
        >>> from processors.GroundwaterProcessor import GroundwaterProcess
        >>> from utils.Config import ConfigApp
        >>> from utils.Errors import ErrorManager

        >>> epsg_code, gisdb, location, mapset = 30719, '/tmp', 'test', 'PERMANENT'
        >>> file_main_map, linkage_name = '/tmp/gw_map.shp', 'initial_gw_grid'

        >>> config = ConfigApp(epsg_code=epsg_code, gisdb=gisdb, location=location, mapset=mapset)
        >>> error = ErrorManager(config=config)
        >>> geo = GeoKernel(config=config, err=error)

        >>> processor = GroundwaterProcess(geo=geo, config=config, err=error)
        >>> processor.config.set_columns_to_save(processor.get_feature_type(), columns_to_save=1)
        >>> processor.config.set_order_criteria(processor.get_feature_type(), order_criteria='area')
        >>> processor.set_map_name(map_name='gw_vector_map', map_path=file_main_map, is_main_file=True)

        >>> processor.import_maps()
        >>> processor.check_names_with_geo()
        >>> processor.check_names_between_maps()

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

    def __init__(self, geo: GeoKernel = None, debug: bool = False, err: ErrorManager = None):
        super().__init__(geo=geo, debug=debug, err=err)

        self.gws = {}
        self._gw_names = {}

    def _start(self, linkage_name: str):
        #necesito esto?

        # import files to vector maps
        self.import_maps()

        # check catchment maps with geo maps (nodes and arcs)
        self.check_names_with_geo()

        # check catchment geometries
        self.check_names_between_maps()

        if not self.check_errors(types=[self.get_feature_type()]):
            # intersection between C (gw map) and L (linkage map)
            _err_gw, _errors_gw = self.inter_map_with_linkage(linkage_name=linkage_name,
                                                              snap='1e-12')
            if _err_gw:
                self.print_errors()
                raise RuntimeError('[EXIT] ERROR AL INTERSECTAR CON [{}]'.format(linkage_name))

            # make a dictionary grid with cells information in intersection map
            self.make_grid_cell()
        # else:
        #     self.print_errors()

        # stats
        self.stats['PROCESSED CELLS'] = len(self.cells)

    @TimerSummary.timeit
    def run(self, linkage_name: str):
        # Utils.show_title(msg_title='GROUNDWATER', title_color=ui.green)
        ts = time.time()
        self._start(linkage_name=linkage_name)
        te = time.time()

        self.stats['FEATURES PROCESSED'] = '{}'.format(len(self._gw_names))
        self.stats['PROCESSED TIME'] = '{0:.2f} seg'.format(te - ts)

        # Set inputs into summary
        # # set main field in map
        #el nombre sale de QGIS
        # field = self.config.get_config_field_name(feature_type=self.get_feature_type(), field_type='main')
        self.summary.set_input_param(param_name='FIELD NAME', param_value='[{}]'.format(field))

        # # imported file
        map_names = [m for m in self.get_map_names(only_names=True, with_main_file=True, imported=True) if m[1]]
        for map_name in map_names:
            imported = self.map_names[map_name]['imported']
            if imported:
                self.summary.set_input_param(param_name='MAP {}'.format(map_name), param_value='[imported]')
            else:
                self.summary.set_input_param(param_name='MAP {}'.format(map_name), param_value='[not imported]')

        # Set stats into summary
        # # set cells
        self.stats['PROCESSED CELLS'] = len(self.cells)
        for stat_key in self.stats:
            self.summary.set_input_param(param_name=stat_key, param_value='[{}]'.format(self.stats[stat_key]))

    def set_data_from_geo(self):
        if self.geo:  # set [self.gws] and [self._gw_names]
            self.set_groundwaters(self.geo.get_groundwaters())

        return True, []

    def get_feature_id_by_name(self, feature_name):
        feature_id = self._gw_names[feature_name] if feature_name in self._gw_names else None
        return feature_id

    def set_groundwaters(self, groundwaters):
        self.gws = groundwaters

        self._gw_names = {}
        for point_id in self.gws:
            gw_data = self.gws[point_id]
            self._gw_names[gw_data['name']] = point_id

    # @main_task
    def make_cell_data_by_main_map(self, map_name, inter_map_name, inter_map_geo_type):
        # Cargamos la capa vectorial en memoria
        inter_map = QgsVectorLayer(inter_map_name, "inter_map", "ogr")

        # Usamos getFeatures() para iterar en PyQGIS
        for feature_data in inter_map.getFeatures():
            # Si necesitas verificar validez de la entidad, usa .id() o .isValid()
            if not feature_data.isValid(): 
                continue

            Cell = namedtuple('Cell_gw', ['row', 'col'])

            # NOTA: Asegúrate de reemplazar esta lógica si ya no usas config.json
            fields = self.get_needed_field_names(alias=self.get_feature_type())
            main_field = fields['main']['name'] 
            
            field_feature_name = 'a_' + main_field
            
            # Suponiendo que config.fields_db ya no existe, deberás usar cadenas fijas 
            # o importarlas de tu nuevo constants.py (ej. 'b_column', 'b_row')
            col_field = 'b_column' 
            row_field = 'b_row'

            # 1. Extracción de Atributos al estilo PyQGIS (usando corchetes)
            feature_name = feature_data[field_feature_name]
            cell_area_id = feature_data['b_cat'] 
            area_row = feature_data[row_field]
            area_col = feature_data[col_field]
            
            # 2. Cálculo de área con motor GEOS
            feature_area = feature_data.geometry().area()

            data = {
                'area': feature_area,
                'cell_id': cell_area_id,
                'name': feature_name,
                'map_name': map_name
            }

            cell = Cell(area_row, area_col)

            self._set_cell(cell, feature_name, data, by_field=self.get_order_criteria_name())
            if cell:
                self.cells_by_map[map_name].append(cell)

        # En QGIS la capa se maneja por recolector de basura, inter_map.close() ya no es necesario

            data = {
                'area': feature_area,
                'cell_id': cell_area_id,
                'name': feature_name,
                'map_name': map_name
            }

            cell = Cell(area_row, area_col)

            self._set_cell(cell, feature_name, data, by_field=self.get_order_criteria_name())

            self.cells_by_map[map_name].append(cell) if cell else None  # order cells by map name (will be used in DS)

        inter_map.close()

        self.summary.set_process_line(msg_name='make_cell_data_by_main_map', check_error=self.check_errors(types=[self.get_feature_type()]),
                                      map_name=map_name, inter_map_name=inter_map_name,
                                      inter_map_geo_type=inter_map_geo_type)

        return self.check_errors(types=[self.get_feature_type()]), self.get_errors()

    ## hace lo mismo que la principal?
    # # @main_task
    # def make_cell_data_by_secondary_maps(self, map_name, inter_map_name, inter_map_geo_type):
    #     # in this case is the same done with main map to secondary maps
    #     return self.make_cell_data_by_main_map(map_name=map_name, inter_map_name=inter_map_name,
    #                                            inter_map_geo_type=inter_map_geo_type)
