import time
from collections import namedtuple
from .FeatureProcessor import FeatureProcess


class GroundwaterProcess(FeatureProcess):
    """
    Processes the vector layer associated with the groundwater regions.

    It contains the groundwater processor particular logic, executing the spatial intersection
    between groundwater geometries and the MODFLOW grid to establish cell-region links.

    Attributes:
    ----------
    cells : Dict[namedtuple<Cell_gw>, Dict[str, Dict[str, str|int|float]]]
        Inherited from FeatureProcess class.
        It is used to store cell-feature relationships. Indexed by groundwater grid cells that
        have been intersected with the feature map. Because a cell can be intersected by more than one
        map geometry, access is given by: 
        [cell] -> [geo_intersected] -> [cell_feature_relationship_data].
        The stored values are:
            - 'area': area occupied by geometry on the map.
            - 'cell_id': cell ID. (ID in gw vector map grid)
            - 'name': groundwater name.
            - 'map_name': groundwater map name.

    cell_ids: Dict[namedtuple<Cell_gw>, Dict[str, str|int|List<data>]]
        Inherited from FeatureProcess class.
        Stores the geometry (or geometries) for each cell that will be stored in the final file.
        Structure and stored values details are in FeatureProcess class.

    _gw_names : set
        Used internally to track unique groundwater region names processed.


    Methods:
    -------
    run(self, grid_layer, gw_layer, col_name, col_row, col_col, col_cat)
        Executes the spatial intersection between the groundwater layer and the grid layer,
        processes the intersection results, and records basic statistics of the execution.

    process_intersection(self, inter_layer, map_name, col_name, col_row, col_col, col_cat)
        Processes the intersection layer feature by feature. Calculates the area of each
        intersection fragment and associates it with the correct cell and groundwater region.

    """

    def __init__(self, debug: bool = False):
        super().__init__(debug=debug)
        self._gw_names = set()
    
    def run(self, grid_layer, gw_layer, col_name, col_row, col_col, col_cat):
        ts = time.time()

        # intersection between C (gw map) and L (linkage map)
        _err_gw, intersected_layer = self.inter_map_with_linkage(gw_layer, grid_layer, col_name)

        if _err_gw:
            raise RuntimeError('[EXIT] ERROR INTERSECTING WITH [{}]'.format(gw_layer))


        te = time.time()

        self.process_intersection(
            inter_layer=intersected_layer, 
            map_name=gw_layer.name(),
            col_name=col_name, 
            col_row=col_row, 
            col_col=col_col, 
            col_cat=col_cat
        )



        self.stats['PROCESSED CELLS'] = len(self.cells)
        self.stats['FEATURES PROCESSED'] = '{}'.format(len(self._gw_names))
        self.stats['PROCESSED TIME'] = '{0:.2f} seg'.format(te - ts)

        self._set_cell_by_criteria(by_field='area')

        return self.stats


    # @main_task
    def process_intersection(self, inter_layer, map_name, col_name, col_row, col_col, col_cat):
        # Load the vector layer into memory
        Cell = namedtuple('Cell_gw', ['row', 'col'])

        # Use getFeatures() to iterate in PyQGIS
        for feature_data in inter_layer.getFeatures():
            # If you need to verify entity validity, use .id() or .isValid()
            if not feature_data.isValid(): 
                continue

            # PyQGIS style Attribute Extraction (using brackets)
            feature_name = feature_data[col_name]
            area_row, area_col = feature_data[col_row], feature_data[col_col]
            cell_area_id = feature_data[col_cat]  # id from cell in linkage map
            feature_area = feature_data.geometry().area()

            data = {
                'area': feature_area,
                'cell_id': cell_area_id,
                'name': feature_name,
                'map_name': map_name
            }

            cell = Cell(area_row, area_col)
            self._gw_names.add(feature_name)
            self._set_cell(cell, feature_name, data, by_field='area')