from qgis.core import QgsPointXY
from utils.Utils import Utils, TimerSummary, UtilMisc
from settings import *
from utils.Errors import ErrorManager
from utils.Protocols import MapFileManagerProtocol
from utils.SummaryInfo import SummaryInfo


class GeoKernel(MapFileManagerProtocol):
    """
        Processes nodes and arcs vector maps associated with ESRI Shapefile files (.SHP) for surface scheme.
        Identify the catchments, groundwaters, demand sites, rivers and nodes that modify the river flow.

        Uses semantics to validate feature data with the arcs types: Runoff / Infiltration, Transmission Link
        and Return flow.

        * Config file: ./config/config.json


        Attributes:
        ----------
        nodes : Dict[int<id>, Dict[str, str | int]]
            Stores all nodes found in node vector map (surface scheme).
            The following data is stored:
                - 'type_id': geometry type ID.
                - 'name': node name.
                - 'x': x-axis position of the node.
                - 'y': y-axis position of the node.
                - 'cat': node internal ID (used by 'pygrass library').

        arcs : Dict[str, Dict[str, int<id>]]
            Stores all arcs found in arc vector map (surface scheme).
            The following data is stored:
                - 'type_id': geometry type ID.
                - 'src_id': source node ID (or None)
                - 'dst_id': destination node ID (or None).

        links : Dict[str, Dict[int<id>, int<id>]]
            Stores the relationships between nodes and arcs. The ('type_id') metada value is used to identify
            the relationship type. Arc relationship: Runoff / Infiltration, Return Flow and Transmission Link.
            To check, the following syntax is considered:
                - 'Runoff/Infiltration':
                    - catchment -> [groundwater or catchment inflow node]
                - 'Transmission Link':
                    - [groundwater] -> [demand site] or [catchment],
                    - [demand site] -> [catchment] or [tributary inflow],
                    - [river withdrawal] -> [demand site] or [catchment],
                    - [reservoir] -> [demand site] or [catchment]
                - 'Return flow':
                    - [demand site] -> [groundwater] or [return flow node]

        gws : Dict[int<id>, Dict[str, str]]
            Currently, it only stores groundwater names. Allows access to 'nodes' variable and see its details.
            The following data is stored:
                - 'name': groundwater name

        catchments : Dict[int<id>, Dict[str, str]]
            Currently, it only stores catchment names. Allows access to 'nodes' variable and see its details.
            The following data is stored:
                - 'name': catchment name

        demand_sites : Dict[int<id>, Dict[str, str | int | bool]]
           Stores demand site data.
           The following data is stored:
            - 'name': DS name
            - 'x': x-axis position of the node.
            - 'y': y-axis position of the node.
            - 'cat': node internal ID.
            - 'processed': indicates if it has been processed or not.
            - 'is_well': indicates if it is a well.

        other_nodes : Dict[int<id>, Dict[str, str | int]]
            Not currently used. Stores nodes that are not classified as catchment, gw, ds, or river/canal.
            The following data is stored:
                - 'name': node name.
                - 'type': node type name. (example: 'return flow node' or 'other')
                - 'x': x-axis position of the node.
                - 'y': y-axis position of the node.

        river_break_nodes : Dict[int, Dict[str, str | int | bool]]
            Stores nodes that modify the flow river. Indexed by node ID.
            The following data is stored:
            - 'node_id': node ID.
            - 'node_name': node name.
            - 'node_type': node type ID.
            - 'node_type_name': node type name.
            - 'x': x-axis position of the node.
            - 'y': y-axis position of the node.
            - 'distance': distance from the head of the main river to the node. Not used. (TODO: redundant, remove)
            - 'main_river_id': in case of being a tributary node, it is arc ID (main river). Or None.
            - 'main_distance': distance from the head of the main river to the node.

        rivers : Dict[int, Dict[str, str | int]]
            Stores rivers and canals found on surface arc map (to access by 'pygrass library').
            The following data is stored:
                - 'name': river or canal name.
                - 'id': arc ID on arc map.
                - 'cat': arc internal ID.
                - 'type': river or canal type.

        config : ConfigApp
            Used to access parameters configuration (constants, texts, columns names, node/arc types, etc.)

        arc_map_names : Dict[str, Dict[str, str]]
            Stores link between arc vector map name(s) and its shapefile path. It is indexed by map name.

        node_map_names : Dict[str, Dict[str, str]]
            Stores link between node vector map name(s) and its shapefile path. It is indexed by map name.

        _feature_type : str
            Text used to identify feature type to process.
            (source: self.config.type_names[self.__class__.__name__]).

        summary : SummaryInfo
            Used to access the execution results (errors, warnings, input parameters, statistics.) generated
            by processing a feature and deliver them in a standard way.


        Methods:
        -------
        processing_nodes_arcs(self, arcmap, nodemap)
            Process surface arc and node maps storing all data to process features. Go through all nodes on the map,
            identifies which type it corresponds to and stores it. It does the same with the arc vector map,
            identifying the different types of possible arcs: Runoff / Infiltration, Transmission Link and Return flow.
            Using arcs/nodes semantics, identify possible errors in the analysis of the surface scheme.

        get_catchments(self)
            Gets catchment nodes that were found on surface node map.

        get_groundwaters(self)
            Gets GW nodes that were found on surface node map.

        get_demand_sites(self)
            Gets demand site nodes that were found on the surface node map.

        get_rivers(self)
            Gets rivers that were found on the surface arc map.

        get_river_break_nodes(self)
            Gets nodes that modify the river flow and that were found on surface node map.

        _get_break_node_distance_from_arc(self, river_arc)
            Calculates distance between a river arc and nodes that modify the river flow. The 'river_arc' parameter
            represents the river arc over which the distance is calculated.

        _check_point_on_line(line, pt)
            Check if a point is on a line. If yes, returns the distance from the point to the line start.

        summary : SummaryInfo
            Used to access the execution results (errors, warnings, input parameters, statistics.) generated by
            feature type and format them in a standard way.


        Example:
        --------
        >>> from grass.pygrass.vector import VectorTopo
        >>> from processors.GeoKernel import GeoKernel
        >>> from processors.RiverProcessor import RiverProcess
        >>> from utils.Config import ConfigApp
        >>> from utils.Errors import ErrorManager

        >>> epsg_code, gisdb, location, mapset = 30719, '/tmp', 'test', 'PERMANENT'
        >>> arc_map_file, node_map_file = '/tmp/arc_map.shp', '/tmp/node_map.shp'

        >>> config = ConfigApp(epsg_code=epsg_code, gisdb=gisdb, location=location, mapset=mapset)
        >>> error = ErrorManager(config=config)
        >>> geo_processor = GeoKernel(config=config, err=error)

        >>> arc_map, node_map = VectorTopo(arc_map_file).open(), VectorTopo(node_map_file).open()
        >>> _err, _ = geo_processor.processing_nodes_arcs(arcmap=arc_map, nodemap=node_map)
        >>> if _err:
        >>>     raise RuntimeError('[EXIT] ERROR READING GEOMETRIES')
        >>> else:
        >>>     catchments = geo_processor.get_catchments()
        >>>     groundwaters = geo_processor.get_groundwaters()
        >>>     rivers = geo_processor.get_rivers()
        >>>     river_break_nodes = geo_processor.get_river_break_nodes()
        >>>     demand_sites = geo_processor.get_demand_sites()

        >>>     for catch_id in catchments:
        >>>         print(catchments[catch_id])  # print data

        >>>     summary = geo_processor.get_summary()

        >>>     inputs = summary.print_input_params()  # inputs and stats
        >>>     status_lines = summary.get_process_lines(with_ui=True)
        >>>     errors = summary.print_errors()
        >>>     warnings = summary.print_warnings()

        >>>     print(errors)

        """

    def __init__(self, config: ConfigApp = None, debug=None, err: ErrorManager = None):
        super(GeoKernel, self).__init__(config=config, error=err)

        self.config = config
        if debug is None:
            self.__debug = self.config.debug if self.config is not None else False

        self._err = err

        self.nodes = {}
        self.arcs = {}
        self.links = {
            'tl': {},  # transmission link
            'ri': {},  # runoff infiltration
            'rf': {}  # return flow
        }

        self.gws = {}
        self.catchments = {}
        self.demand_sites = {}
        self.other_nodes = {}
        self.river_break_nodes = {}
        self.rivers = {}

        self.arc_map_names = {}
        self.node_map_names = {}

        self._feature_type = self.config.type_names[self.__class__.__name__]

        self.summary = SummaryInfo(prefix=self.get_feature_type(), errors=self._err, config=self.config)

        self.z_rotation = None
        self.x_ll = None  # real world model coords (lower left)
        self.y_ll = None  # real world model coords (lower left)

    def set_origin(self, x_ll: float, y_ll: float, z_rotation: float):
        self.x_ll = x_ll
        self.y_ll = y_ll
        self.z_rotation = z_rotation

    def get_summary(self):
        return self.summary

    def get_feature_type(self):
        return self._feature_type

    def get_catchments(self):
        return self.catchments

    def get_groundwaters(self):
        return self.gws

    def get_demand_sites(self):
        return self.demand_sites

    def get_rivers(self):
        return self.rivers

    def get_river_break_nodes(self):
        return self.river_break_nodes

    @staticmethod
    def _check_point_on_line(line, pt):
        closest_pont_on_line, dst_bt_two_pts, dst_from_segment_beginning, dst_from_line_beg = line.distance(pt)

        return closest_pont_on_line == pt, dst_from_line_beg

    def _get_break_node_distance_from_arc(self, river_arc, min_rate=0.9):
        for break_node_id in self.river_break_nodes:

            if break_node_id != '_by_name':  # TODO: FIX IT - remove '_by_name'
                break_node = self.river_break_nodes[break_node_id]

                if break_node['node_name']:
                    point_node = QgsPointXY(break_node['x'], break_node['y']) 
                    arc_name = river_arc.attrs['Name']
                    arc_id = river_arc.attrs['ObjID']

                    pt_on_line, dist = GeoKernel._check_point_on_line(river_arc, point_node)

                    if pt_on_line:
                        if break_node['node_type'] == 13:  # Tributary Node
                            if break_node['node_name'] == arc_name + ' Inflow':  # it is the seconday river
                                break_node['secondary_river_id'] = arc_id
                                break_node['secondary_distance'] = dist
                            elif UtilMisc.get_similarity_rate(break_node['node_name'], arc_name + ' Inflow', min_rate=min_rate):  # it is the seconday river
                                msg_error = "[ADVERTENCIA] El nodo del tipo [Tributary Inflow] tiene un nombre={} levemente" \
                                            " diferente al rio que esta conectado, de nombre={}.".format(break_node['node_name'], arc_name)

                                self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)

                                break_node['secondary_river_id'] = arc_id
                                break_node['secondary_distance'] = dist
                            else:  # it is the main river
                                break_node['main_river_id'] = arc_id
                                break_node['main_distance'] = dist  # use main distance like node distance
                                break_node['distance'] = dist
                        else:
                            break_node['main_river_id'] = arc_id
                            break_node['main_distance'] = dist  # use main distance like node distance
                            break_node['distance'] = dist

    @TimerSummary.timeit
    # @main_task
    def processing_nodes_arcs(self, arcmap, nodemap):
        _err = False

        # prepare node and arc column names
        node_column = self.config.node_columns
        arc_column = self.config.arc_columns

        # prepare node and arc type ids
        node_type = self.config.nodes_type_id
        arc_type = self.config.arc_type_id

        for p in nodemap.viter('points'):
            point_name = p.attrs[node_column['name']]
            point_type_id = p.attrs[node_column['type_id']]  # 3: GW; 21: Catchment; 13: Inflow
            point_id = p.attrs[node_column['obj_id']]

            point_x, point_y = p.x, p.y
            point_cat = p.attrs[node_column['cat']]

            self.nodes[point_id] = {
                'type_id': point_type_id,
                'name': point_name,
                'x': point_x,
                'y': point_y,
                'cat': point_cat
            }

            if point_type_id == node_type["groundwater"]:  # gw
                _point_name = 'groundwater'

                self.gws[point_id] = {
                    'name': point_name
                }

            elif point_type_id == node_type["catchment"]:  # catchment
                _point_name = 'catchment'

                self.catchments[point_id] = {
                    'name': point_name
                }
                # self.catchments[point_name] = point_id

            elif point_type_id == node_type["demand_site"]:  # demand site
                _point_name = 'demand site'

                self.demand_sites[point_id] = {
                    'name': point_name,
                    'x': point_x,
                    'y': point_y,
                    'cat': point_cat,
                    'processed': False,
                    'is_well': False  # it is preliminarily assumed to be a well
                }

            elif point_type_id == node_type["return_flow_node"]:  # return flow node
                _point_name = 'return flow node'

                self.other_nodes[point_id] = {
                    'name': point_name or _point_name,
                    'type': point_name,
                    'x': point_x,
                    'y': point_y
                }

            elif point_type_id == node_type["tributary_inflow"]:  # inflow
                _point_name = 'tributary inflow'
                _point_type = node_type["tributary_inflow"]

                if point_name:
                    self.river_break_nodes[point_id] = {
                        'node_id': point_id,
                        'node_name': point_name,
                        'node_type': _point_type,
                        'node_type_name': _point_name,
                        'x': point_x,
                        'y': point_y,
                        'distance': None,
                        'main_river_id': None,  # it will set by arc, when it will calculate the distance
                        'main_distance': None,
                        'secondary_river_id': None,  # it will set by arc
                        'secondary_distance': None,
                    }
                else:
                    msg_error = "[{}] inflow node node (ObjID=[{}]) without name. It will be ignorated." \
                        .format(_point_name.title(), point_id)
                    # self._errors['ris'].append(msg_error)
                    # self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)

            elif point_type_id == node_type["catchment_inflow_node"]:  # catchment inflow node
                _point_name = 'catchment inflow node'
                _point_type = node_type["catchment_inflow_node"]

                if point_name:
                    self.river_break_nodes[point_id] = {
                        'node_id': point_id,
                        'node_name': point_name,
                        'node_type': _point_type,
                        'node_type_name': _point_name,
                        'x': point_x,
                        'y': point_y,
                        'distance': None,
                        'main_river_id': None,  # it will set by arc, when it will calculate the distance
                        'main_distance': None
                    }
                else:
                    msg_error = "[{}] inflow node node (ObjID=[{}]) without name. It will be ignorated." \
                        .format(_point_name.title(), point_id)
                    # self._errors['ris'].append(msg_error)
                    # self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)

            elif point_type_id == node_type["river_withdrawal"]:  # river withdrawal
                _point_name = 'river withdrawal'
                _point_type = node_type["river_withdrawal"]

                if point_name:
                    self.river_break_nodes[point_id] = {
                        'node_id': point_id,
                        'node_name': point_name,
                        'node_type': _point_type,
                        'node_type_name': _point_name,
                        'x': point_x,
                        'y': point_y,
                        'distance': None,
                        'main_river_id': None,  # it will set by arc, when it will calculate the distance
                        'main_distance': None
                    }
                else:
                    msg_error = "[{}] inflow node node (ObjID=[{}]) without name. It will be ignorated."\
                        .format(_point_name.title(), point_id)
                    # self._errors['ris'].append(msg_error)
                    # self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)

            elif point_type_id == node_type["diversion_outflow"]:  # diversion outflow
                _point_name = 'diversion outflow'
                _point_type = node_type["diversion_outflow"]

                if point_name:
                    self.river_break_nodes[point_id] = {
                        'node_id': point_id,
                        'node_name': point_name,
                        'node_type': _point_type,
                        'node_type_name': _point_name,
                        'x': point_x,
                        'y': point_y,
                        'distance': None,
                        'main_river_id': None,  # it will set by arc, when it will calculate the distance
                        'main_distance': None
                    }
                else:
                    msg_error = "[{}] inflow node node (ObjID=[{}]) without name. It will be ignorated."\
                        .format(_point_name.title(), point_id)
                    # self._errors['ris'].append(msg_error)
                    # self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)

            else:
                _point_name = 'other'

                self.other_nodes[point_id] = {
                    'name': point_name or _point_name,
                    'type': point_type_id,
                    'x': point_x,
                    'y': point_y
                }

            # check if 'name' is null
            if not point_name:
                point_name = _point_name
                self.nodes[point_id]['name'] = point_name

        for l in arcmap.viter('lines'):
            line_name = l.attrs[arc_column["name"]]
            line_type_id = l.attrs[arc_column["type_id"]]  # 22: Runoff/Infiltration; 6: River; 7: transmission link; 6,15: River or Canal; 8: return flow
            line_type_name = l.attrs[arc_column["type_name"]]
            line_id = l.attrs[arc_column["obj_id"]]

            line_cat = l.attrs[arc_column["cat"]]
            node_src_id, node_dst_id = l.attrs[arc_column["src_obj_id"]], l.attrs[arc_column["dest_obj_id"]]

            if line_type_id == arc_type["runoff_infiltration"]:  # Runoff/Infiltration
                # cases: catchment->[groundwater | catchment inflow node]
                node_src = self.nodes[node_src_id]
                node_dst = self.nodes[node_dst_id]

                if node_src['type_id'] == node_type["catchment"]:  # catchment
                    self.arcs[line_id] = {
                        'type_id': line_type_id,
                        'src_id': node_src_id,
                        'dst_id': node_dst_id
                    }

                    # groundwater | catchment inflow node
                    if node_dst['type_id'] == node_type["groundwater"] or node_dst['type_id'] == node_type["catchment_inflow_node"]:
                        self.links['ri'][node_src_id] = node_dst_id
                    else:
                        msg_error = "Tipos permitidos para Runoff/Infiltration: catchment->[groundwater | catchment inflow node]. " \
                                    "Pero se encontro en el nodo [fin]: nombre={}, tipo={}.".format(node_dst['name'],
                                                                                                    node_dst['type_id'])
                        # self._errors['ris'].append(msg_error)
                        self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)
                else:
                    msg_error = "Tipos permitidos para Runoff/Infiltration: catchment->[groundwater | catchment inflow node]. " \
                                "Pero se encontro en el nodo [inicio]: nombre={}, tipo={}.".format(node_src['name'],
                                                                                                   node_src['type_id'])
                    # self._errors['ris'].append(msg_error)
                    self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)

            elif line_type_id == arc_type["transmission_link"]:  # transmission link
                # cases: groundwater->[demand site | catchment] or demand site->[catchment | tributary inflow] or river withdrawal->demand site
                node_src = self.nodes[node_src_id]
                node_dst = self.nodes[node_dst_id]

                if node_src['type_id'] == node_type["groundwater"]:  # groundwater
                    self.arcs[line_id] = {
                        'type_id': line_type_id,
                        'src_id': node_src_id,
                        'dst_id': node_dst_id
                    }

                    # demand site | catchment
                    if node_dst['type_id'] == node_type["demand_site"] or node_dst['type_id'] == node_type["catchment"]:
                        self.links['tl'][node_src_id] = node_dst_id
                    else:
                        msg_error = "Tipos permitidos para [Transmission Link]: (*)[groundwater]->[demand site] | [catchment] | " \
                                    "[demand site]->[catchment] | [tributary inflow] | [river withdrawal]->[demand site] | [catchment] | " \
                                    "[reservoir]->[demand site] | [catchment]" \
                                    "Pero se encontro en el nodo [fin]: [nombre={}], [tipo={}].".format(
                            node_dst['name'],
                            node_dst['type_id'])
                        # self._errors['tls'].append(msg_error)
                        self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)
                elif node_src['type_id'] == node_type["demand_site"]:  # demand site
                    self.arcs[line_id] = {
                        'type_id': line_type_id,
                        'src_id': node_src_id,
                        'dst_id': node_dst_id
                    }

                    # catchment | river_withdrawal | tributary inflow
                    if node_dst['type_id'] == node_type["catchment"] or \
                            node_dst['type_id'] == node_type["river_withdrawal"] or \
                            node_dst['type_id'] == node_type["tributary_inflow"]:
                        self.links['tl'][node_src_id] = node_dst_id
                    else:
                        msg_error = "Tipos permitidos para [Transmission Link]: [groundwater]->[demand site] | [catchment] | " \
                                    "(*)[demand site]->[catchment] | [tributary inflow] | [river withdrawal]->[demand site] | [catchment] | " \
                                    "[reservoir]->[demand site] | [catchment]" \
                                    "Pero se encontro en el nodo [fin]: [nombre={}], [tipo={}].".format(
                            node_dst['name'],
                            node_dst['type_id'])
                        # self._errors['tls'].append(msg_error)
                        self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)
                elif node_src['type_id'] == node_type["river_withdrawal"]:  # river withdrawal
                    self.arcs[line_id] = {
                        'type_id': line_type_id,
                        'src_id': node_src_id,
                        'dst_id': node_dst_id
                    }

                    # demand site or catchment
                    if node_dst['type_id'] == node_type["demand_site"] or node_dst['type_id'] == node_type["catchment"]:
                        self.links['tl'][node_src_id] = node_dst_id
                    else:
                        msg_error = msg_error = "Tipos permitidos para [Transmission Link]: [groundwater]->[demand site] | [catchment] | " \
                                    "[demand site]->[catchment] | [tributary inflow] | (*)[river withdrawal]->[demand site] | [catchment] | " \
                                    "[reservoir]->[demand site] | [catchment]" \
                                    "Pero se encontro en el nodo [fin]: [nombre={}], [tipo={}].".format(node_dst['name'],
                                                                                                    node_dst['type_id'])
                        # self._errors['tls'].append(msg_error)
                        self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)
                elif node_src['type_id'] == node_type["reservoir"]:  # reservoir
                    self.arcs[line_id] = {
                        'type_id': line_type_id,
                        'src_id': node_src_id,
                        'dst_id': node_dst_id
                    }

                    # demand site or catchment
                    if node_dst['type_id'] == node_type["demand_site"] or node_dst['type_id'] == node_type["catchment"]:
                        self.links['tl'][node_src_id] = node_dst_id
                    else:
                        msg_error = "Tipos permitidos para [Transmission Link]: [groundwater]->[demand site] | [catchment] | " \
                                    "[demand site]->[catchment] | [tributary inflow] | [river withdrawal]->[demand site] | [catchment] | " \
                                    "[reservoir]->[demand site] | [catchment]" \
                                    "Pero se encontro en el nodo [fin]: [nombre={}], [tipo={}].".format(node_dst['name'],
                                                                                                    node_dst['type_id'])
                        # self._errors['tls'].append(msg_error)
                        self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)
                else:
                    msg_error = "Tipos permitidos para [Transmission Link]: [groundwater]->[demand site] | [catchment] | " \
                                    "[demand site]->[catchment] | [tributary inflow] | [river withdrawal]->[demand site] | [catchment] | " \
                                    "[reservoir]->[demand site] | [catchment]" \
                                "Pero se encontro en el nodo [inicio]: [nombre={}], [tipo={}].".format(node_src['name'],
                                                                                                   node_src['type_id'])
                    # self._errors['tls'].append(msg_error)
                    self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)

            elif line_type_id == arc_type["river"] or line_type_id == arc_type["canal"]:  # River or Canal
                if line_name:
                    self.rivers[line_id] = {
                        'name': line_name,
                        'id': line_id,
                        'cat': line_cat,
                        'type': line_type_id
                    }
                    # self.rivers[line_name] = line_id

                    self.arcs[line_id] = {
                        'type_id': line_type_id,
                        'src_id': None,
                        'dst_id': None
                    }

                    # complete distances in river break nodes (order <= [river arcs number]*[brak nodes number])
                    self._get_break_node_distance_from_arc(l)
                else:  # river without name
                    msg_error = "River or Canal (ObjID=[{}]) without name".format(line_id)
                    self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)

            elif line_type_id == arc_type["return_flow"]:  # return flow
                # cases: demand site->[groundwater | return flow node]
                node_src = self.nodes[node_src_id]
                node_dst = self.nodes[node_dst_id]

                if node_src['type_id'] == node_type["demand_site"]:  # demand site
                    self.arcs[line_id] = {
                        'type_id': line_type_id,
                        'src_id': node_src_id,
                        'dst_id': node_dst_id
                    }

                    # groundwater | return flow node
                    if node_dst['type_id'] == node_type["groundwater"] or node_dst['type_id'] == node_type["return_flow_node"]:
                        self.links['rf'][node_src_id] = node_dst_id
                        # catchment_to_gw[node_src_id] = node_dst_id
                    else:
                        msg_error = "Tipos permitidos para Return Flow: demand site->[groundwater | return flow node]. " \
                                    "Pero se encontro en el nodo [fin]: nombre={}, tipo={}.".format(node_dst['name'],
                                                                                                    node_dst['type_id'])
                        # self._errors['rfs'].append(msg_error)
                        self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)
                else:
                    msg_error = "Tipos permitidos para Return Flow: demand site->[groundwater | return flow node]. " \
                                "Pero se encontro en el nodo [inicio]: nombre={}, tipo={}.".format(node_src['name'],
                                                                                                   node_src['type_id'])
                    # self._errors['rfs'].append(msg_error)
                    self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)
            else:
                msg_error = "Tipos de enlaces permitidos: Runoff/Infiltration | Return Flow | River | Transmission Link. " \
                            "Datos de geometria encontrada: nombre={}, tipo={}, id={}".format(line_name, line_type_id,
                                                                                              line_id)
                # self._errors['others'].append(msg_error)
                self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)

        self.summary.set_process_line(msg_name='processing_nodes_arcs', check_error=self.check_errors(types=[self.get_feature_type()]),
                                      arcmap=arcmap, nodemap=nodemap)

        return self.check_errors(types=[self.get_feature_type()]), self.get_errors()
    
    ## toda esta funcion es un check de un vector map, no se usaria en QGIS porque ya se hace en la clase Utils
    def check_basic_columns(self, map_name: str):
        _err, _errors = False, []
        #################### CAMBIO
        code_error = ERROR_CODES['geo_basic_column']  # code error for geo basic column

        if self.is_arc_map(map_name=map_name):
            fields = self.get_needed_field_names(alias=self.get_feature_type(), is_arc=True)
        else:
            fields = self.get_needed_field_names(alias=self.get_feature_type(), is_node=True)

        for field_key in [field for field in fields if fields[field]]:
            field_name = fields[field_key]['name']
            needed = fields[field_key]['needed']
            #################### CAMBIO
            __err, __errors = Utils.check_basic_columns(vector_layer=map_name, columns=[field_name], needed=[needed])

            self.summary.set_process_line(msg_name='check_basic_columns', check_error=__err,
                                          map_name=map_name, columns=field_name)
            if needed:
                self.append_error(msgs=__errors, is_warn=False, typ=self.get_feature_type(), code=code_error)
            else:
                self.append_error(msgs=__errors, is_warn=True, typ=self.get_feature_type(), code=code_error)

        return self.check_errors(code=code_error), self.get_errors(code=code_error)

    def import_maps(self, verbose: bool = False, quiet: bool = True):
        map_names = [m for m in self.get_map_names(only_names=False, with_main_file=True, imported=False) if m[1]]

        arc_map = self.get_arc_map_names()[0]  # only one file
        node_map = self.get_node_map_names()[0]  # only one file

        for map_name, path_name, inter_name in (arc_map, node_map):
            _err, _errors = self.make_vector_map(map_name=map_name)
            if _err:
                self.append_error(msgs=_errors, typ=self.get_feature_type())
            else:
                self.summary.set_process_line(msg_name='import_maps', check_error=_err,
                                              map_path=path_name, output_name=map_name)

        return self.check_errors(types=[self.get_feature_type()]), self.get_errors()

    def set_map_names(self):
        for map_name, map_path in self.get_geo_file_path(is_arc=True):
            self.set_arc_map_names(map_name=map_name, map_path=map_path)

        for map_name, map_path in self.get_geo_file_path(is_node=True):
            self.set_node_map_names(map_name=map_name, map_path=map_path)
