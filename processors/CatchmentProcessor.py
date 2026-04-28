import time
from collections import namedtuple

from qgis.core import QgsFeature, QgsVectorLayer

from utils.Errors import ErrorManager
from processors.FeatureProcessor import FeatureProcess
from processors.GeoKernel import GeoKernel
from utils.Utils import TimerSummary

### borre el config app, ya no se usa
### hay que cambiar los feature que usa grass
### Cambiar el VectorTopo por QgsFeature


class CatchmentProcess(FeatureProcess):
    """
        Processes vector map associated with the catchment ESRI Shapefile file (.shp) and contains geometries (areas)
        associated with this feature.

        It contains the catchment processor particular logic.

        * Config File: ./config/config.json


        Attributes:
        ----------
        cells : Dict[namedtuple<Cell>, Dict[str, Dict[str, str|int]]
            Inherited from FeatureProcess class.
            It is used to store cell-feature relationship. It is indexed by catchment grid cells that
            they have been intersected with the feature map. Because a cell can be intersected by more than one
            map geometry, access is given by: [cell] -> [geo_intersected] -> [cell_feature_relationship_data].
            The stored values are:
                - 'area': area occupied by geometry on the map.
                - 'cell_id': cell ID. (ID in gw vector map grid)
                - 'name': catchment name.
                - 'map_name': catchment map name. (name used by GRASS Platform)

        cell_ids: Dict[namedtuple<Cell>, Dict[str, str|int|List<data>]]
            Inherited from FeatureProcess class.
            Store for each cell the geometry (or geometries) that be stored in final file.
            Structure and stored values details are in FeatureProcess class.

        catchments : Dict[int, Dict[str, str | int]]
            It is used to store catchment information obtained from surface map analysis.
            (Stored data details are in GeoKernel class).

        _catchment_names : Dict[str, int]
            It is used internally to directly access catchment data by name.


        Methods:
        -------
        _start(self, linkage_name: str)
            Runs procedure for successful processing between feature map and inital GW grid.
            The 'linkage_name' parameter refers to GW grid vector map.

        run(self, linkage_name: str)
            Start processing and records basic statistics of the execution.
            The 'linkage_name' parameter refers to groundwater grid vector map.

        set_data_from_geo(self)
            Extracts catchment data from analyzed surface maps (arc and node).

        make_cell_data_by_main_map(self, map_name, inter_map_name, inter_map_geo_type)
            Create the structure that store necessary catchment data of the main map.
            A main map generates a mandatory column for catchment in final file metadata (even if its values are null).

        make_cell_data_by_secondary_maps(self, map_name, inter_map_name, inter_map_geo_type)
            Currently, this method is not used because there is only one main map for catchment.


        Example:
        --------
        >>> from processors.GeoKernel import GeoKernel
        >>> from processors.CatchmentProcessor import CatchmentProcess
        >>> from utils.Config import ConfigApp
        >>> from utils.Errors import ErrorManager

        >>> epsg_code, gisdb, location, mapset = 30719, '/tmp', 'test', 'PERMANENT'
        >>> file_main_map, linkage_name = '/tmp/catch_map.shp', 'initial_gw_grid'

        >>> config = ConfigApp(epsg_code=epsg_code, gisdb=gisdb, location=location, mapset=mapset)
        >>> error = ErrorManager(config=config)
        >>> geo = GeoKernel(config=config, err=error)

        >>> processor = CatchmentProcess(geo=geo, config=config, err=error)
        >>> processor.config.set_columns_to_save(processor.get_feature_type(), columns_to_save=1)
        >>> processor.config.set_order_criteria(processor.get_feature_type(), order_criteria='area')
        >>> processor.set_map_name(map_name='catch_vector_map', map_path=file_main_map, is_main_file=True)

        >>> processor.import_maps()
        >>> processor.check_names_with_geo()
        >>> processor.check_names_between_maps()

        >>> if not processor.check_errors():  # or processor.run(linkage_name=grid_vector_map)
        >>>     processor.inter_map_with_linkage(linkage_name=grid_vector_map)
        >>>     processor.make_grid_cell()

        >>>     summary = processor.get_summary()

        >>>     inputs = summary.print_input_params()  # inputs and stats
        >>>     status_lines = summary.get_process_lines(with_ui=True)
        >>>     errors = summary.print_errors()
        >>>     warnings = summary.print_warnings()

        >>>     print(inputs)

    """

    def __init__(self, geo: GeoKernel = None, config: ConfigApp = None, debug: bool = False, err: ErrorManager = None):
        super().__init__(geo=geo, config=config, debug=debug, err=err)

        self.catchments = {}
        self._catchment_names = {}

    def _start(self, linkage_name: str):
        # import files to vector maps
        self.import_maps()

        # check catchment maps with geo maps (nodes and arcs)
        self.check_names_with_geo()

        # check catchment geometries
        self.check_names_between_maps()

        if not self.check_errors(types=[self.get_feature_type()]):
            # intersection between C (catchments map) and L (linkage map)
            _err_c, _errors_c = self.inter_map_with_linkage(linkage_name=linkage_name, snap='1e-12')
            if _err_c:
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
        ts = time.time()
        self._start(linkage_name=linkage_name)
        te = time.time()

        self.stats['FEATURES PROCESSED'] = '{}'.format(len(self._catchment_names))
        self.stats['PROCESSED TIME'] = '{0:.2f} seg'.format(te - ts)

        # Set inputs into summary
        # # set main field in map
        field = self.config.get_config_field_name(feature_type=self.get_feature_type(), field_type='main')
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
        if self.geo:  # set [self.catchments] and [self._catchment_names]
            self.set_catchments(self.geo.get_catchments())

        return True, []

    def get_feature_id_by_name(self, feature_name):
        feature_id = self._catchment_names[feature_name] if feature_name in self._catchment_names else None
        return feature_id

    def set_catchments(self, catchments):
        self.catchments = catchments

        self._catchment_names = {}
        for point_id in self.catchments:
            catchment_data = self.catchments[point_id]
            self._catchment_names[catchment_data['name']] = point_id

    # @main_task
    def make_cell_data_by_main_map(self, map_name, inter_map_name, inter_map_geo_type):
        inter_map = QgsVectorLayer(inter_map_name, "inter_map", "ogr")
        if not inter_map.isValid():
            raise RuntimeError('[EXIT] ERROR AL INTERSECTAR CON [{}]'.format(inter_map_name))

        for feature_data in inter_map.getFeatures():

            Cell = namedtuple('Cell_catchment', ['row', 'col'])

            fields = self.get_needed_field_names(alias=self.get_feature_type())
            main_field, main_needed = fields['main']['name'], fields['main']['needed']
            field_feature_name = 'a_' + main_field
            col_field = 'b_' + self.config.fields_db['linkage']['col_in']
            row_field = 'b_' + self.config.fields_db['linkage']['row_in']

            feature_name = feature_data[field_feature_name]
            cell_area_id = feature_data['b_cat']  # id from cell in linkage map
            area_row, area_col = feature_data[row_field], feature_data[col_field]
            feature_area = feature_data.geometry().area()

            data = {
                'area': feature_area,
                'cell_id': cell_area_id,
                'name': feature_name,
                'map_name': map_name
            }

            cell = Cell(area_row, area_col)

            self._set_cell(cell, feature_name, data, by_field=self.get_order_criteria_name()) if cell else None

            self.cells_by_map[map_name].append(cell) if cell else None  # order cells by map name (be used in DS)

        self.summary.set_process_line(msg_name='make_cell_data_by_main_map', check_error=self.check_errors(types=[self.get_feature_type()]),
                                      map_name=map_name, inter_map_name=inter_map_name,
                                      inter_map_geo_type=inter_map_geo_type)

        return self.check_errors(types=[self.get_feature_type()]), self.get_errors()

    # @main_task
    def make_cell_data_by_secondary_maps(self, map_name, inter_map_name, inter_map_geo_type):
        # in this case is the same but done with main map to secondary maps
        return self.make_cell_data_by_main_map(map_name=map_name, inter_map_name=inter_map_name,
                                               inter_map_geo_type=inter_map_geo_type)

