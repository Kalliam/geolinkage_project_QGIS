import time
from collections import namedtuple
from qgis.core import QgsVectorLayer, QgsFeature, QgsField, QgsSpatialIndex, QgsGeometry
from qgis.PyQt.QtCore import QVariant

from .FeatureProcessor import FeatureProcess
from ..utils.RiverNode import RiverNode


class RiverProcess(FeatureProcess):
    """
    Contains the river processor particular logic.

    Processes rivers using surface maps (nodes and arcs/rivers).
    By leveraging the node layer, it rebuilds the river network tree to segment 
    rivers exactly where specific nodes (e.g., withdrawals or inflows) interact with them.
    These segments are then spatially intersected with the groundwater grid.

    The final output stores the segment and the river in the form: [river name],[segment name].

    Attributes:
    ----------
    cells : Dict[namedtuple<Cell_river>, Dict[str, Dict[str, str|int|float]]]
        Inherited from FeatureProcess class.
        It is used to store cell-feature relationships. Indexed by grid cells that
        have been intersected with the feature map. Because a cell can be intersected by more than one
        map geometry, access is given by: 
        [cell] -> [geo_intersected] -> [cell_feature_relationship_data].
        The stored values are:
            - 'length': line length representing the river segment within the cell.
            - 'cell_id': cell ID. (ID in gw grid's vector map)
            - 'segment_name': River segment name (e.g., node interaction break).
            - 'river_name': river name.
            - 'name': format: [river name],[segment name].
            - 'map_name': origin map name.

    cell_ids: Dict[namedtuple<Cell_river>, Dict[str, str|int|List<data>]]
        Inherited from FeatureProcess class.
        Stores the geometry (s) that will actually be output in the final file.

    root : RiverNode
        RiverNode instance acting as the root to identify river segments and nodes
        that modify the river flow.


    Methods:
    -------
    run(self, grid_layer, river_layer, node_layer, col_river_name, col_node_type, col_node_name, col_row, col_col, col_cat)
        Starts processing by generating a segmented river layer dynamically in memory,
        then intersecting it with the grid layer and recording statistics.

    _make_river_tree_segments_structure(self, river_layer, node_layer, col_node_type, col_node_name, col_river_name)
        Rebuilds the river tree structure by linking nodes to their closest rivers using QGIS
        spatial indices, calculating line distances to identify flow breaks.

    make_segmented_river_layer(self, river_layer, node_layer, col_node_type, col_node_name, col_river_name)
        Replaces older manual grass methods by generating a new memory layer where original 
        river lines are mathematically split at the nodes' calculated distances.

    get_river_segments_from_tree(self, feature_river, col_river_name)
        Returns the ordered sub-segments for a particular river by querying the rebuilt RiverNode tree.

    process_intersection(self, inter_layer, map_name, col_river, col_segment, col_row, col_col, col_cat)
        Processes the intersection between the segmented rivers and the MODFLOW grid. Calculates the 
        exact length of the river fragment inside the cell to prioritize segments.

    """

    def __init__(self, debug: bool = False):
        super().__init__(debug=debug)
        self.root = None

    def run(self, grid_layer, river_layer, node_layer, col_river_name, col_node_type, col_node_name, col_row, col_col, col_cat):
        ts = time.time()

        segmented_river_layer = self.make_segmented_river_layer(
            river_layer=river_layer,
            node_layer=node_layer,
            col_node_type=col_node_type,
            col_node_name=col_node_name,
            col_river_name=col_river_name
        )

        _err_r, inter_river_layer = self.inter_map_with_linkage(segmented_river_layer, grid_layer, 'river_name')
        if _err_r:
            raise RuntimeError(f'[EXIT] ERROR INTERSECTING RIVERS WITH [{grid_layer.name()}]')

        self.process_intersection(
            inter_layer=inter_river_layer,
            map_name=river_layer.name(),
            col_river='river_name', # col generated
            col_segment='segment_break_name', # col generated
            col_row=col_row, 
            col_col=col_col, 
            col_cat=col_cat
        )

        self._set_cell_by_criteria(by_field='length')

        te = time.time()
        self.stats['PROCESSED TIME'] = '{0:.2f} seg'.format(te - ts)
        self.stats['PROCESSED CELLS'] = len(self.cells)

        return self.stats




    def _make_river_tree_segments_structure(self, river_layer, node_layer, col_node_type, col_node_name, col_river_name):
        # avoid residual data between executions
        RiverNode.segments_list = {}
        self.root = RiverNode(node_id=-1, node_name='root', node_type=0, node_distance=0)

        # Spatial Index of Rivers and rivers by ID
        rivers_index = QgsSpatialIndex(river_layer.getFeatures())
        rivers_dict = {f.id(): f for f in river_layer.getFeatures()}

        # Nodes loop
        for node_feature in node_layer.getFeatures():
            node_type = node_feature[col_node_type]
            
            # Ignore infiltration links
            if node_type == 15:
                continue

            node_geom = node_feature.geometry()
            if not node_geom:
                continue

            # Search for the 2 closest rivers
            nearest_river_ids = rivers_index.nearestNeighbor(node_geom.asPoint(), 2)
            
            if not nearest_river_ids:
                continue

            # The main river is always the closest one (index 0)
            main_river_id = nearest_river_ids[0]
            main_river_feature = rivers_dict[main_river_id]
            main_river_geom = main_river_feature.geometry()
            main_distance = main_river_geom.lineLocatePoint(node_geom)

            node_id = node_feature.id()
            node_name = node_feature[col_node_name]
            main_river_name = main_river_feature[col_river_name]
            main_river_cat = main_river_feature.id() 

            river_node = RiverNode(
                node_id=node_id, node_name=node_name, node_type=node_type,
                node_distance=main_distance, root_node=self.root, parent=self.root
            )
            xy_point = node_geom.asPoint()
            river_node.set_coords(xy_point.x(), xy_point.y())

            river_node.set_main_river(main_river_id, main_river_name, main_river_cat, main_distance)


            # Secondary River
            # If it is a tributary (13) and we find a second river nearby (index 1)
            if node_type == 13 and len(nearest_river_ids) > 1:
                secondary_river_id = nearest_river_ids[1]
                secondary_river_feature = rivers_dict[secondary_river_id]
                secondary_river_geom = secondary_river_feature.geometry()
                secondary_distance = secondary_river_geom.lineLocatePoint(node_geom)
                secondary_river_name = secondary_river_feature[col_river_name]
                secondary_river_cat = secondary_river_feature.id()
                
                # Assign to the node
                river_node.set_secondary_river(
                    secondary_river_id, 
                    secondary_river_name, 
                    secondary_river_cat, 
                    secondary_distance
                )

        return self.root

    def make_segmented_river_layer(self, river_layer, node_layer, col_node_type, col_node_name, col_river_name):
        # Build tree and get the logical distances
        self.root = self._make_river_tree_segments_structure(
            river_layer, node_layer, col_node_type, col_node_name, col_river_name
        )
        
        # If no nodes cutting the river, return the original layer
        if not self.root or not self.root.get_segments_list():
            return river_layer

        # New temporary layer in memory
        crs = river_layer.crs().authid()
        segmented_layer = QgsVectorLayer(f"LineString?crs={crs}", "Segmented_Rivers", "memory")
        provider = segmented_layer.dataProvider()
        
        # Create columns
        provider.addAttributes([
            QgsField("river_name", QVariant.String),
            QgsField("segment_break_name", QVariant.String)
        ])
        segmented_layer.updateFields()

        # Cutting the lines
        new_features = []        
        for feature_river in river_layer.getFeatures():      
            river_segments = self.get_river_segments_from_tree(feature_river, col_river_name)
            for segment in river_segments:
                dist_start = segment['start_distance']
                # If end_distance is None, calculate the real total length
                if segment['end_distance'] is None:
                    dist_end = feature_river.geometry().length()
                else:
                    dist_end = segment['end_distance']
                
                # Extract the generic container
                geom_original = feature_river.geometry()
                
                # Extraction of the primitive:
                if geom_original.isMultipart():
                    base_curve = geom_original.constGet().geometryN(0)
                else:
                    base_curve = geom_original.constGet()
                
                cut_curve = base_curve.curveSubstring(dist_start, dist_end)                
                cut_geometry = QgsGeometry(cut_curve)               
               
                # Package the new piece with its name
                new_feature = QgsFeature(segmented_layer.fields())
                new_feature.setGeometry(cut_geometry)
                new_feature.setAttributes([segment['river_name'], segment['segment_break_name']])
                
                new_features.append(new_feature)

        # Save the pieces in the layer and return it
        provider.addFeatures(new_features)
        segmented_layer.updateExtents()

        return segmented_layer

    def get_river_segments_from_tree(self, feature_river, col_river_name):
        all_nodes = self.root.get_segments_list()
        river_name = feature_river[col_river_name] 
        river_nodes = [node for node in all_nodes if node['river_name'] == river_name]
        river_nodes.sort(key=lambda x: x['distance'])
        
        final_segments = []
        current_distance = 0.0
        
        # Build the ranges of the sub-segments
        for node in river_nodes:
            final_segments.append({
                'river_name': river_name,
                'segment_break_name': node['break_name'],
                'start_distance': current_distance,
                'end_distance': node['distance']
            })
            current_distance = node['distance']
            
        # Add the closing stretch (from the last node to the end of the river)
        final_segments.append({
            'river_name': river_name,
            'segment_break_name': f"{river_name}_Final", 
            'start_distance': current_distance,
            'end_distance': None # None tells curveSubstring to go to the final end
        })
        
        return final_segments

    # @main_task
    def process_intersection(self, inter_layer, map_name, col_river, col_segment, col_row, col_col, col_cat):
        Cell = namedtuple('Cell_river', ['row', 'col'])

        for feature in inter_layer.getFeatures():
            if not feature.hasGeometry():
                continue
            
            river_name = feature[col_river]
            segment_name = feature[col_segment]
            area_row, area_col = feature[col_row], feature[col_col]
            cell_id = feature[col_cat]                
            line_length = feature.geometry().length() 


            data = {
                'length': line_length,
                'cell_id': cell_id,
                'segment_name': segment_name,
                'river_name': river_name,
                'name': f"{river_name},{segment_name}",
                'map_name': map_name
            }

            cell = Cell(area_row, area_col)
            self._set_cell(cell, data['name'], data, by_field="length")