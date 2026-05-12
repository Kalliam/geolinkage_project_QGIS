import time
from collections import namedtuple

from qgis.core import QgsFeature, QgsVectorLayer

from processors.FeatureProcessor import FeatureProcess


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

    def __init__(self, debug: bool = False):
        super().__init__(debug=debug)

    def run(self, grid_layer, catchment_layer, col_name, col_row, col_col, col_cat):
        ts = time.time()

        # intersection between C (catchment map) and L (linkage map)
        _err_cat, intersected_layer = self.inter_map_with_linkage(catchment_layer, grid_layer, col_name)

        if _err_cat:
            raise RuntimeError('[EXIT] ERROR AL INTERSECTAR CON [{}]'.format(catchment_layer))

        # make a dictionary grid with cells information in intersection map
        
        te = time.time()

        self.process_intersection(
            inter_layer=intersected_layer, 
            map_name=catchment_layer.name(),
            col_name=col_name, 
            col_row=col_row, 
            col_col=col_col, 
            col_cat=col_cat
        )


        self.stats['PROCESSED CELLS'] = len(self.cells)
        self.stats['FEATURES PROCESSED'] = '{}'.format(len(self._catchment_names))
        self.stats['PROCESSED TIME'] = '{0:.2f} seg'.format(te - ts)

        self._set_cell_by_criteria(by_field='area')
        
        return self.stats

    # @main_task
    ##Esta función recorre un pedacitos de poligono, uno por uno. Por cada fragmento:
    ## A que cuenca pertenece? (feature_name)
    ## En que celda de la malla cayo? (row, col)
    ## Cual es el tamaño exacto de ese fragmento? (feature_data.geometry().area())
    ##guarda esto en un diccionario (data) para que el programa pueda construir la matriz final.
    def process_intersection(self, inter_layer, map_name, col_name, col_row, col_col, col_cat):
        Cell = namedtuple('Cell', ['row', 'col'])

        for feature in inter_layer.getFeatures():
            if not feature.isValid() or not feature.hasGeometry(): 
                continue

            feature_name = feature[col_name]
            area_row, area_col = feature[col_row], feature[col_col]
            cell_id = feature[col_cat]
            feature_area = feature.geometry().area()

            data = {
                'area': feature_area,
                'cell_id': cell_id,
                'name': feature_name,
                'map_name': map_name
            }

            cell = Cell(area_row, area_col)
            self._set_cell(cell, feature_name, data, by_field='area')
