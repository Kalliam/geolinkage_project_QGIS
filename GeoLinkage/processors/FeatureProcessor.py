from abc import ABCMeta
import processing

class FeatureProcess(metaclass=ABCMeta):
    """
    Feature processors parent class. Contains the generic logic for all processors.
    Currently 4 processors are implemented for layers of: catchments, groundwater, rivers and demand sites.

    It handles common operations such as spatial intersection between feature layers 
    and the groundwater grid using QGIS native processing tools (reprojecting on the fly if needed).
    It accumulates the geometry fragments mapping to each cell, and organizes them
    to populate the final output table needed by WEAP.

    Attributes:
    ----------
    cells : dict
        It is used to store cell-feature relationship data. Because a cell can be intersected 
        by more than one map geometry, it accumulates them. Structure and stored values 
        depend on feature type, usually grouping by [cell] -> [feature_name] -> [data].

    cell_ids : dict
        Stores the sorted or filtered geometries for each cell that will be output 
        to the final file. Includes metadata like cell_id, row, col, and the list of data.

    cells_by_map : dict
        Stores geometries organized by their origin map name.

    stats : dict
        Stores basic statistics of the processing execution (e.g., number of cells processed, time taken).


    Methods:
    -------
    _cell_order_criteria_default(cell, cells_dict, by_field='area')
        Static method that returns the geometries of a cell sorted by a specific field (e.g., area) descending.

    _set_cell(self, cell, area_name, data, by_field='area')
        Accumulates feature fragments into the self.cells dictionary. If a feature already exists in a cell, 
        its metric (like area or length) is added up.

    _set_cell_by_criteria(self, criteria_func=None, by_field='area')
        Orders the processed cells according to a criteria function and stores the ordered
        results in the self.cell_ids dictionary for final output.

    inter_map_with_linkage(self, source_layer, grid_layer, col_name_source)
        Calculates the spatial intersection between a source vector layer and the MODFLOW grid layer.
        Reprojects the source layer on the fly if coordinate systems differ, returning a temporary result layer.

    get_data_to_save(self, cell, map_name, main_data=True, is_demand_site=False, export_column_names=None)
        Formats the list of features for a specific cell into a dictionary mapping 
        column names to feature names for exporting.

    get_cell_data_by_map(self, map_name: str, cell)
        Filters and returns the data for a given cell that originated from a specific map.

    """

    def __init__(self, debug: bool = False):
        self.cells = {}
        self.cell_ids = {}
        self.cells_by_map = {}

        self.__debug = debug
        self._feature_type = self.__class__.__name__

        # stats
        self.stats = {}

    @staticmethod
    # orders the polygons/lines of a cell and returns them as a list
    def _cell_order_criteria_default(cell, cells_dict, by_field='area'):
        area_targets = cells_dict[cell]
        area_targets_sorted = sorted(area_targets.items(), key=lambda x: x[1][by_field], reverse=True)
        area_targets_sorted = [area_target for area_key, area_target in area_targets_sorted]

        return area_targets_sorted  # (key, data_key)

    # accumulates fragments into self.cells
    def _set_cell(self, cell, area_name, data, by_field='area'):
        if cell in self.cells:
            # watch if exist catchment
            if area_name in self.cells[cell]:
                area_area = data[by_field]
                self.cells[cell][area_name][by_field] += area_area
            else:
                self.cells[cell][area_name] = data
        else:
            self.cells[cell] = {}

            self.cells[cell][area_name] = data

    # orders the processed cells and stores them in another array
    def _set_cell_by_criteria(self, criteria_func=None, by_field='area'):
        # watch what is the best area by criteria for a cell
        if criteria_func is None:
            # Sorts the cell data from highest to lowest based on 'by_field'
            criteria_func = lambda c, all_cells, by_field: sorted(
                all_cells[c].values(), 
                key=lambda item: item.get(by_field, 0), 
                reverse=True
            )

        for cell in self.cells:
            area_targets_ordered = criteria_func(cell, self.cells, by_field=by_field)

            self.cell_ids[cell] = {
                'number_of_data': len(area_targets_ordered),
                'cell_id': area_targets_ordered[0]['cell_id'],
                'row': cell.row,
                'col': cell.col,
                'data': area_targets_ordered
            }

    #@main_task
    def inter_map_with_linkage(self, source_layer, grid_layer, col_name_source):
        # 1.  validation
        if not source_layer.isValid() or not grid_layer.isValid():
            raise ValueError(f"Error: One of the layers is invalid ({source_layer.name()} or {grid_layer.name()})")

        # 2. Filtering nameless geometries
        source_layer.setSubsetString(f'"{col_name_source}" IS NOT NULL AND "{col_name_source}" != \'\'')

        try:
            # 3. Evaluation and On-the-fly Reprojection
            crs_origen = source_layer.crs()
            crs_destino = grid_layer.crs()
            
            # By default, the layer to intersect is the original one
            layer_to_intersect = source_layer

            if crs_origen != crs_destino:
                # Systems differ. Create a temporary reprojected layer in RAM.
                reproject_params = {
                    'INPUT': source_layer,
                    'TARGET_CRS': crs_destino,
                    'OUTPUT': 'memory:'
                }
                reproject_result = processing.run("native:reprojectlayer", reproject_params)
                layer_to_intersect = reproject_result['OUTPUT']

            # 4. QGIS Native Geoprocessing (Intersection)
            intersect_params = {
                'INPUT': layer_to_intersect,
                'OVERLAY': grid_layer,
                'INPUT_FIELDS': [],
                'OVERLAY_FIELDS': [], 
                'OVERLAY_FIELDS_PREFIX': '',
                'OUTPUT': 'memory:'
            }
            
            result = processing.run("native:intersection", intersect_params)
            intersected_layer = result['OUTPUT']
            
            # 5. Cleaning original filter
            source_layer.setSubsetString('')
            
            return False, intersected_layer # (Error=False, Result Layer)

        except Exception as e:
            # Restore filter for safety in case of failure
            source_layer.setSubsetString('')
            raise RuntimeError(f"Critical failure when intersecting {source_layer.name()} with {grid_layer.name()}. Detail: {e}")


    # Returns 'cell' data. The 'main_data' parameter 
    # has by default the value True, which refers to
    # main map data. 
    # formats the list into shapefile format
    # cols_number = self.config.get_columns_to_save(feature_type=self.get_feature_type()), looks for COLUMNS_FOR_FEATURE in config

    def get_data_to_save(self, cell, map_name, main_data=True, is_demand_site=False, export_column_names=None):
        
        #main_map = self.get_main_map_name(only_name=True, imported=True)
        col_data = self.get_cell_data_by_map(map_name=map_name, cell=cell)
        #col_names = self.get_column_to_export(alias=self.get_feature_type(), with_type=False)
        cols_number = len(export_column_names)
        data_dict = {}
        if col_data and len(col_data) > cols_number and is_demand_site == True:
            # send error message to QGIS 
            pass
        
        values_to_save = min(cols_number, len(col_data)) if col_data else 0

        for i in range(cols_number):
            col_names = export_column_names[i]

            if i < values_to_save:
            # Assign the winning geometry name
                data_dict[col_names] = col_data[i]['name']
            else:
                # Fill the "gaps" with empty strings to maintain DB integrity
                data_dict[col_names] = ''
        return data_dict


    # filters the cell data coming from the map 'map_name' 
    def get_cell_data_by_map(self, map_name: str, cell):
        ret = []
        if cell in self.cell_ids:
            ret = [d for d in self.cell_ids[cell]['data'] if d['map_name'] == map_name]
        return ret





