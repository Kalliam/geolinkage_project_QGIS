import time
from collections import namedtuple
from .FeatureProcessor import FeatureProcess


class CatchmentProcess(FeatureProcess):
    """
    Processes the vector layer associated with the catchments.

    It contains the catchment processor particular logic, calculating the intersection
    between the catchment geometries and the groundwater grid.

    Attributes:
    ----------
    cells : Dict[namedtuple<Cell>, Dict[str, Dict[str, str|int|float]]]
        Inherited from FeatureProcess class.
        It is used to store cell-feature relationships. Indexed by grid cells that
        have been intersected with the feature map. Because a cell can be intersected
        by more than one map geometry, access is given by: 
        [cell] -> [geo_intersected] -> [cell_feature_relationship_data].
        The stored values are:
            - 'area': area occupied by geometry on the map.
            - 'cell_id': cell ID. (ID in gw vector map grid)
            - 'name': catchment name.
            - 'map_name': catchment map name.

    cell_ids: Dict[namedtuple<Cell>, Dict[str, str|int|List<data>]]
        Inherited from FeatureProcess class.
        Stores the geometry (or geometries) for each cell that will be stored in the final file.
        Structure and stored values details are in FeatureProcess class.

    _catchment_names : set
        Used internally to track unique catchment names processed.


    Methods:
    -------
    run(self, grid_layer, catchment_layer, col_name, col_row, col_col, col_cat)
        Executes the intersection between the catchment layer and the groundwater grid layer,
        and processes the result to obtain cell-catchment relationships. Returns execution stats.

    process_intersection(self, inter_layer, map_name, col_name, col_row, col_col, col_cat)
        Processes the intersection layer feature by feature. Determines the catchment
        a geometry fragment belongs to, the grid cell it falls into, and its exact area,
        saving this data for the final matrix construction.

    """

    def __init__(self, debug: bool = False):
        super().__init__(debug=debug)
        self._catchment_names = set()
    
    def run(self, grid_layer, catchment_layer, col_name, col_row, col_col, col_cat):
        ts = time.time()

        # intersection between C (catchment map) and L (linkage map)
        _err_cat, intersected_layer = self.inter_map_with_linkage(catchment_layer, grid_layer, col_name)

        if _err_cat:
            raise RuntimeError('[EXIT] ERROR INTERSECTING WITH [{}]'.format(catchment_layer))

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
            self._catchment_names.add(feature_name)
            self._set_cell(cell, feature_name, data, by_field='area')
