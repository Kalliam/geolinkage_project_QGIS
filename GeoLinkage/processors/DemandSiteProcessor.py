import time
from collections import namedtuple
from .FeatureProcessor import FeatureProcess


class DemandSiteProcess(FeatureProcess):
    """
    Contains the Demand Site (DS) processor logic.

    Processes both well-type demand sites and demand site areas.
    A plain text file optionally identifies by name which demand sites are actually wells.
    Demand sites can be processed from point layers (wells) or polygon layers (areas),
    and their spatial intersection with the groundwater grid is calculated.

    Attributes:
    ----------
    cells : Dict[namedtuple<Cell_ds>, Dict[str, Dict[str, str|int|float]]]
        Inherited from FeatureProcess class.
        Used to store cell-feature relationships. Indexed by grid cells that
        have been intersected with the feature map. Because a cell can be intersected
        by more than one map geometry, access is given by:
        [cell] -> [geo_intersected] -> [cell_feature_relationship_data].
        The stored values are:
            - 'area': area occupied by geometry on the map (0 for wells).
            - 'cell_id': cell ID. (ID in gw vector map grid)
            - 'name': DS name.
            - 'map_name': DS map name.

    cell_ids: Dict[namedtuple<Cell_ds>, Dict[str, str|int|List<data>]]
        Inherited from FeatureProcess class.
        Stores the geometries for each cell that will actually be stored in the final file.
        Structure and stored values details are in FeatureProcess class.


    Methods:
    -------
    run(self, grid_layer, well_layer, area_layers_list, wells_txt_path, col_name, col_row, col_col, col_cat, col_well_name=None)
        Starts processing by reading well names from the text file, then computes
        intersections for the well layer (if provided) and any area layers against the
        groundwater grid layer.

    process_intersection(self, inter_layer, map_name, col_name, col_row, col_col, col_cat, well_names=None, is_well=True)
        Processes the intersected features. For areas, it calculates the intersected area.
        For wells, it validates their names against the provided well names list and records
        their grid cell locations.

    read_well_files(self, path_archivo_txt)
        Reads the plain text file containing well names, parsing them into a clean list
        of strings used for filtering the features.

    """

    def __init__(self, debug: bool = False):
        super().__init__(debug=debug)

    def run(self, grid_layer, well_layer, area_layers_list, wells_txt_path, col_name, col_row, col_col, col_cat, col_well_name=None):
        ts = time.time()
        well_names = self.read_well_files(wells_txt_path)

        if well_layer is not None and col_well_name is not None:
            _err_well, inter_well_layer = self.inter_map_with_linkage(well_layer, grid_layer, col_well_name)
            if not _err_well:
                self.process_intersection(inter_well_layer, well_layer.name(), col_well_name, col_row, col_col, col_cat, well_names, True)

        for area_layer in area_layers_list:
            _err_area, inter_area_layer = self.inter_map_with_linkage(area_layer, grid_layer, col_name)
            if not _err_area:
                self.process_intersection(inter_area_layer, area_layer.name(), col_name, col_row, col_col, col_cat, None, False)

        self._set_cell_by_criteria(by_field='area')
        self.stats['PROCESSED CELLS'] = len(self.cells)
        self.stats['PROCESSED TIME'] = round(time.time() - ts, 2)
        return self.stats

    #@main_task
    def process_intersection(self, inter_layer, map_name, col_name, col_row, col_col, col_cat, well_names=None, is_well=True):
        Cell = namedtuple('Cell_ds', ['row', 'col'])

        for feature in inter_layer.getFeatures():
            # shapefiles Bypass for areas that dont posses the specified column
            try:
                feature_name = feature[col_name]
            except KeyError:
                feature_name = f"{map_name}_{feature.id()}"
            
            # Strict filtering without hidden characters
            if is_well and well_names:
                clean_names = [str(n).strip() for n in well_names if n]
                if str(feature_name).strip() not in clean_names:
                    continue

            area_row, area_col, cell_area_id = feature[col_row], feature[col_col], feature[col_cat]
            feature_area, criteria = (0, None) if is_well else (feature.geometry().area(), "area")

            data = {'area': feature_area, 'cell_id': cell_area_id, 'name': feature_name, 'map_name': map_name}
            self._set_cell(Cell(area_row, area_col), feature_name, data, by_field=criteria)
            


    def read_well_files(self, wells_txt_path):
        well_names = []
        # If no file is provided (None), return the empty list so as not to interrupt the processor.
        if not wells_txt_path:
            return well_names

        try:
            with open(wells_txt_path, 'r', encoding='utf-8', errors='replace') as file:
                lines = file.readlines()
                
                # Parsing
                for line in lines:
                    name = line.strip() 
                    if name and not name.startswith('#'):
                        well_names.append(name)
                        
        except Exception as e:
            # Error thrown if the user provided a path but the file is unreadable
            raise ValueError(f"I/O Error in wells file [{wells_txt_path}]: {e}")
            
        return well_names