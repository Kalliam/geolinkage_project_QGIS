import time
from collections import namedtuple

# from grass.exceptions import GrassError
# from grass.pygrass.vector import VectorTopo

# from utils.Utils import GrassCoreAPI, TimerSummary
from utils.Config import ConfigApp
from utils.Errors import ErrorManager
from processors.FeatureProcessor import FeatureProcess
from processors.GeoKernel import GeoKernel
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

    def __init__(self, config: ConfigApp = None, debug: bool = False, err: ErrorManager = None):
        super().__init__(config=config, debug=debug, err=err)

        self.rivers = {}
        self._river_names = {}
        self.river_break_nodes = {}
        self.root = RiverNode(node_id=-1, node_name='root', node_type=0, node_distance=0)

    def _start(self, linkage_name: str):
        # import files to vector maps
        self.import_maps()

        # check catchment maps with geo maps (nodes and arcs)
        self.check_names_with_geo()

        # check catchment geometries
        self.check_names_between_maps()

        # make rivers hierarchy with tree segment nodes
        _err_r, _errors_r = self.make_segment_map(is_main_file=True)

        if not self.check_errors(types=[self.get_feature_type()]):
            # intersection between WEAPArc and L (linkage map)
            _err_r, _errors_r = self.inter_map_with_linkage(linkage_name=linkage_name, snap='1e-12')
            if _err_r:
                # self.print_errors()
                raise RuntimeError('[EXIT] ERROR AL INTERSECTAR CON [{}]'.format(linkage_name))
            else:
                # make a dictionary grid with cell information in intersection map
                self.make_grid_cell()

            # stats
            self.stats['PROCESSED CELLS'] = len(self.cells)

    @TimerSummary.timeit
    def run(self, linkage_name: str):
        # Utils.show_title(msg_title='RIVERS', title_color=ui.green)
        ts = time.time()
        self._start(linkage_name=linkage_name)
        te = time.time()

        self.stats['FEATURES PROCESSED'] = '{}'.format(len(self._river_names))
        self.stats['PROCESSED TIME'] = '{0:.2f} seg'.format(te - ts)

        # Set inputs into summary
        # # set main field in map
        field_river = self.config.get_config_field_name(feature_type=self.get_feature_type(), field_type='main')
        field_segment = self.config.get_config_field_name(feature_type=self.get_feature_type(), field_type='secondary')
        self.summary.set_input_param(param_name='FIELDS NAME', param_value='[{}] and [{}]'.format(field_river, field_segment))

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
            self.set_rivers(rivers=self.geo.get_rivers(), river_break_nodes=self.geo.get_river_break_nodes())

    def get_feature_id_by_name(self, feature_name):
        feature_id = self._river_names[feature_name] if feature_name in self._river_names else None
        return feature_id

    def set_rivers(self, rivers, river_break_nodes):
        self.rivers = rivers
        self.river_break_nodes = river_break_nodes

        self._river_names = {}
        for point_id in self.rivers:
            river_data = self.rivers[point_id]
            self._river_names[river_data['name']] = point_id

    def _make_river_tree_segments_structure(self):
        root = self.root

        break_keys = [k for k in self.river_break_nodes.keys() if k != '_by_name']
        if break_keys:
            # make real structure
            for key_name in break_keys:
                break_node = self.river_break_nodes[key_name]

                # [CANAL NOT IMPLEMENTED] Canal must be ingnored because WEAP has not implemented this type to be linked.
                # delete Canal break nodes
                arc_id = break_node['main_river_id']
                arc_type = self.rivers[arc_id]['type']
                if arc_type == 15:  # it is a Canal
                    self.river_break_nodes.pop(key_name)
                    continue

                break_node_id = break_node['node_id']
                break_node_name = break_node['node_name']
                break_node_type = break_node['node_type']
                break_node_distance = break_node['distance']
                break_node_x, break_node_y = break_node['x'], break_node['y']

                # make an initial node
                river_node = RiverNode(node_id=break_node_id, node_name=break_node_name, node_type=break_node_type,
                                       node_distance=break_node_distance, root_node=root, parent=root)
                river_node.set_coords(break_node_x, break_node_y)

                # set main river
                main_river_id = self.river_break_nodes[key_name]['main_river_id']
                main_distance = self.river_break_nodes[key_name]['distance']  # between node to river
                main_river_data = self.rivers[main_river_id]
                river_node.set_main_river(main_river_data['id'], main_river_data['name'], main_river_data['cat'],
                                          main_distance)

                # if it is a inflow node, it marks secondary node
                if break_node_type == 13:  # Tributary node
                    # get secondary river data
                    secondary_river_id = self.river_break_nodes[key_name]['secondary_river_id']
                    secondary_distance = self.river_break_nodes[key_name]['secondary_distance']

                    if secondary_river_id in self.rivers:
                        secondary_river_data = self.rivers[secondary_river_id]
                        river_node.set_secondary_river(secondary_river_data['id'], secondary_river_data['name'],
                                                       secondary_river_data['cat'], secondary_distance)

            # for pre, fill, node in RenderTree(root):
            #     print("%s %s | x=%s | y=%s | dist=%s | id=%s | cat=%s" %
            #           (pre, node.node_name, node.x, node.y, node.node_distance, node.node_id, node.node_cat))

            segments = root.get_segments_list()
            # for seg in segments:
            #     print(seg)
        else:
            root = None

        return root

    def _set_break_names_in_segments_map(self, segments_map_name='arc_segments'):
        _err, _errors = False, []  # TODO: catch errors

        columns = [(u'cat', 'INTEGER PRIMARY KEY'),
                   (u'segment_break_name', 'TEXT'),
                   (u'river_name', 'TEXT')]

        root_node = self.root

        # create attribute table and link with vector map
        columns_str = ','.join(['{} {}'.format(col[0], col[1]) for col in columns])  # columns format
        GrassCoreAPI.create_table_attributes(segments_map_name, columns_str, layer=1)

        # set break names in map
        segment_map = VectorTopo(segments_map_name)
        segment_map.open('rw')

        for feature in segment_map.viter('lines'):
            segment_break_name, river_name = root_node.get_segment_break_name(feature.cat)

            # table columns: ([cat], [segment_break_name] [river_name])
            f_attrs = (segment_break_name, river_name)
            try:
                segment_map.rewrite(feature, cat=feature.cat, attrs=f_attrs)
            except GrassError as e:
                # print('ERROR writing in segment map  - cat={}'.format(feature.cat))
                continue
        segment_map.table.conn.commit()

        segment_map.close()

        return _err, _errors

    # @main_task
    def make_segment_map(self, is_main_file: bool = False):
        err = False
        errors = []

        # get the arc map
        arc_map_name, arc_map_path, arc_map_inter = self.geo.get_arc_map_names()[0]  # get the arc map
        segments_map_name = 'segments_out_river'

        # make hierarchy of rivers with tree segment nodes
        self.root = self._make_river_tree_segments_structure()

        if self.root and self.root.get_segments_list():
            # TODO: check if copy and extract maps were created
            # filter only rivers from WEAPArc and apply hierarchy to divide rivers in segment lines
            _err, _errors = GrassCoreAPI.make_segments(root=self.root, arc_map_name=arc_map_name, output_map=segments_map_name)
            self.append_error(msgs=_errors, typ=self.get_feature_type()) if _err else None

            # put segment names in [river_segments_map]
            _err, _errors = self._set_break_names_in_segments_map(segments_map_name=segments_map_name)
            self.append_error(msgs=_errors, typ=self.get_feature_type()) if _err else None

            # set segment map like the main river map
            self.set_map_name(map_name=segments_map_name, map_path='', is_main_file=is_main_file)

            # it was imported because it is based in Arc map
            self.map_names[segments_map_name]['imported'] = True

            # the intersection map is with 'lines' geos not the default 'areas'
            self.set_inter_map_geo_type(map_key=segments_map_name, geo_map_type='lines')

            self.summary.set_process_line(msg_name='make_segment_map', check_error=self.check_errors(types=[self.get_feature_type()]))
        else:
            msg_info = 'Not rivers found in in map: [{}]'.format(arc_map_name)
            self.append_error(msg=msg_info, typ=self.get_feature_type(), is_warn=True)

        return self.check_errors(types=[self.get_feature_type()]), self.get_errors()

    # @main_task
    def make_cell_data_by_main_map(self, map_name, inter_map_name, inter_map_geo_type):
        inter_map = VectorTopo(inter_map_name)
        inter_map.open('r')

        for feature_data in inter_map.viter(vtype=inter_map_geo_type):
            if feature_data.cat is None:  # when topology has some errors
                # print("[ERROR] ", a.cat, a.id)
                continue

            Cell = namedtuple('Cell_river', ['row', 'col'])

            fields = self.get_needed_field_names(alias=self.get_feature_type())
            main_field, main_needed = fields['main']['name'], fields['main']['needed']
            second_field, second_needed = fields['secondary']['name'], fields['secondary']['needed']

            field_feature_name = 'a_' + main_field
            field_subfeature_name = 'a_' + second_field
            col_field = 'b_' + self.config.fields_db['linkage']['col_in']
            row_field = 'b_' + self.config.fields_db['linkage']['row_in']

            subfeature_name = feature_data.attrs[field_subfeature_name]
            feature_name = feature_data.attrs[field_feature_name]
            cell_area_id = feature_data.attrs['b_cat']  # id from cell in linkage map
            area_row, area_col = feature_data.attrs[row_field], feature_data.attrs[col_field]
            line_length = feature_data.length()

            data = {
                'length': line_length,
                'cell_id': cell_area_id,
                'segment_name': subfeature_name,
                'river_name': feature_name,
                'name': '{},{}'.format(feature_name, subfeature_name),
                'map_name': map_name
            }

            cell = Cell(area_row, area_col)

            self._set_cell(cell, feature_name, data, by_field=self.get_order_criteria_name())

            self.cells_by_map[map_name].append(cell)  # order cells by map name (be used in DS)

        inter_map.close()

        self.summary.set_process_line(msg_name='make_cell_data_by_main_map', check_error=self.check_errors(types=[self.get_feature_type()]),
                                      map_name=map_name, inter_map_name=inter_map_name,
                                      inter_map_geo_type=inter_map_geo_type)

        return self.check_errors(types=[self.get_feature_type()]), self.get_errors()

    # @main_task
    def make_cell_data_by_secondary_maps(self, map_name, inter_map_name, inter_map_geo_type):
        # in this case is the same done with main map to secondary maps
        return self.make_cell_data_by_main_map(map_name=map_name, inter_map_name=inter_map_name,
                                               inter_map_geo_type=inter_map_geo_type)

    def set_map_names(self):
        super().set_map_names()

        # because river map is based on arc map, the intersection map is with 'lines'
        map_names = [m for m in self.get_map_names(only_names=True, with_main_file=True, imported=False)]
        for map_name in map_names:
            self.set_inter_map_geo_type(map_key=map_name, geo_map_type='lines')

