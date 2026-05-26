from anytree import Node, RenderTree, NodeMixin, AsciiStyle
from anytree.search import find_by_attr, findall_by_attr


class RiverNode(NodeMixin):
    """
        It is responsible for providing the structure that stores river segments. These segments are created
        because there are nodes on the surface node map that modify the river flow (injecting or extracting
        water into the river). For the integration between groundwater model and surface model
        it is necessary to identify the river segment of the where it occurs.

        Initial:
            |------------------------- RIVER 1 ----------------------------|
            =============[NODE 1]====================[NODE 2]=============>

        Final:
            |--Below NODE 1-|       |----Below NODE 2---|       |Below RIVER 1 Headflow-|
            ================[NODE 1]====================[NODE 2]=======================>


        Attributes:
        ----------
        segments_list : Dict[int<id>, Dict[str, str | int | float]]
            Class variable that stores the complete segments list.
            (Contains the same segments as 'river_segments' for the root node).

        river_segments : List[Dict[str, str | int | float]]
            List of accumulated segments for children of this RiverNode (self) node. It is used to create
            a new vector map with river arc correct divisions.
            The GRASS tool used is 'v.segment' to perform these subdivisions.
            The segment data stored are:
                - 'feature_id': new ID <int> for each segment in new map. (created with 'v.segment')
                - 'type': segment type, it is always 'L' for line. (It is required by WEAP for linking)
                - 'cat': GRASS internal ID for the river (surface arc map).
                - 'start_offset': starting percentage where to start dividing arc.
                - 'end_offset': final percentage where to finish dividing arc.
                - 'break_name': river segment name. (Below [Node] or Below [RIVER] Headflow)
                - 'river_name': river name.

        root_node : RiverNode
            RiverNode root. it is the access point to the entire segments structure.

        node_id : int
            Node ID.

        node_name : str
            Node name.

        node_type : int
            Node type. (for example: 'Tributary node').

        node_distance : float
            Distance between node and the beginning of river arc.

        x : float
            x-axis node coordinate.

        y : float
            y-axis node coordinate.

        node_cat : int
            Internal GRASS ID that identifies its geometries.

        parent : RiverNode
            RiverNode parent.
            It is inherited from the parent class NodeMixin.

        children : RiverNode
            RiverNode children.
            It is inherited from NodeMixin parent class.

        main_river_id : int
            ID that identifies the river (surface arc map) the tributary reaches.
            This occurs for 'Tributary Nodes'.

        main_river_cat : int
            Internal GRASS ID that identifies the river (surface arc map) the tributary reaches.

        main_river_name : str
            River name that the tributary reaches (on surface arc map).

        main_river_distance : float
            (Not used) Distance between node and arc beginning of the main river.

        secondary_river_id : int
            Tributary river ID on arc vector map.

        secondary_river_cat : int
            (Not used)

        secondary_river_name : str
            Tributary river name on arc vector map.

        secondary_river_distance : float
            (Not used)


        Methods:
        -------
        get_segment_break_name(cls, segment_line_cat)
            Returns a particular segment name and the river name to which it belongs.
            The 'segment_line_cat' parameter identifies the required segment.

        set_main_river(self, river_id, river_name, river_cat, river_distance)
            Bind a new RiverNode within tree structure. The parameters 'river_id', 'river_name',
            'river_cat' and 'river_distance' are data to store for this new node.

        get_order_children_by_distance(self)
            Returns an ordered list of the children of the <RiverNode> self node.
            It is ordered by node distance respect to river arc.

        get_segments_list(self)
            Returns a list with all segments child of the self <RiverNode> node.
            Updating 'river_segments' parameter of self <RiverNode> with this list.

        get_break_input_by_river(self, river_node_id=None)
            Build segments list with their structured data for the self <RiverNode> node.
            (The parameter 'river_node_id' is not used).

        get_segments_format(self, river_node_id=None)
            Returns a formated string with the segments data of the self <RiverNode> node. This string follows
            required format by the GRASS tool 'v.segment' to build the new vector map with segments river.
            (The parameter 'river_node_id' is not used).


        Example:
        --------
        >>> from processors.GeoKernel import GeoKernel
        >>> from utils.RiverNode import RiverNode
        >>> from utils.Config import ConfigApp
        >>> from utils.Errors import ErrorManager

        >>> epsg_code, gisdb, location, mapset = 30719, '/tmp', 'test', 'PERMANENT'
        >>> arc_map_file, node_map_file = '/tmp/arc_map.shp', '/tmp/node_map.shp'

        >>> config = ConfigApp(epsg_code=epsg_code, gisdb=gisdb, location=location, mapset=mapset)
        >>> error = ErrorManager(config=config)
        >>> geo_processor = GeoKernel(config=config, err=error)

        >>> rivers = geo_processor.get_rivers()
        >>> break_node_list = geo_processor.get_river_break_nodes()

        >>> root = RiverNode(node_id=-1, node_name='root', node_type=0, node_distance=0)

        >>> for key_name in break_node_list.keys():
        >>>     bk_node = break_node_list[key_name]

        >>>     bk_node_id, bk_node_name, bk_node_type = bk_node['node_id'], bk_node['node_name'], bk_node['node_type']
        >>>     bk_node_distance, bk_node_x, bk_node_y = bk_node['distance'], bk_node['x'], bk_node['y']

        >>>     river_node = RiverNode(node_id=bk_node_id, node_name=bk_node_name, node_type=bk_node_type,
        >>>                                node_distance=bk_node_distance, root_node=root, parent=root)
        >>>     river_node.set_coords(bk_node_x, bk_node_y)

        >>>     main_river_data = rivers[main_river_id]
        >>>     main_river_id = break_node_list[key_name]['main_river_id']
        >>>     main_distance = break_node_list[key_name]['distance']  # between node to river
        >>>     river_node.set_main_river(main_river_data['id'], main_river_data['name'], main_river_data['cat'],
        >>>                                   main_distance)

                # Tributary node
        >>>     if bk_node['node_type'] == 13 and break_node_list[key_name]['secondary_river_id'] in rivers:
        >>>         secondary_river_id = break_node_list[key_name]['secondary_river_id']
        >>>         river_node.set_secondary_river(rivers[secondary_river_id]['id'], rivers[secondary_river_id]['name'],
        >>>                                                rivers[secondary_river_id]['cat'],
        >>>                                                break_node_list[key_name]['secondary_distance'])

        >>> segments = root.get_segments_list()
        >>>     for seg in segments:
        >>>         print(seg)

        >>> segments_to_grass = root.get_segments_format()
        >>> print(segments_to_grass)

        """

    segments_list = {}

    def __init__(self, node_id, node_name, node_type, node_distance, root_node=None, parent=None, children=None):
        super(RiverNode, self).__init__()

        if root_node:
            self.root_node = root_node

        self.node_id = node_id
        self.node_name = node_name
        self.node_type = node_type
        self.node_distance = node_distance  # if it is a inflow node, use the main_river_distance
        self.x = None
        self.y = None
        self.node_cat = -1  # TODO: Should be the main_river_cat from childs

        self.parent = parent
        if children:
            self.children = children

        self.river_segments = []

        # main river or parent river
        self.main_river_cat = None
        self.main_river_name = None
        self.main_river_id = None
        self.main_river_distance = self.node_distance

        # secondary river or subflow river
        self.secondary_river_cat = None
        self.secondary_river_name = None
        self.secondary_river_id = None
        self.secondary_river_distance = None

    @classmethod
    def get_segment_break_name(cls, segment_line_cat):
        segment_break_name = RiverNode.segments_list[segment_line_cat]['break_name']
        river_name = RiverNode.segments_list[segment_line_cat]['river_name']

        return segment_break_name, river_name

    def set_main_river(self, river_id, river_name, river_cat, river_distance):
        # make a node representing main river (parent river)
        # if not self.parent == self.root_node:
        # Búsqueda tolerante a duplicados topológicos
        coincidencias = findall_by_attr(self.root_node, name="node_id", value=river_id)
        
        if not coincidencias:
            main_river = None
        else:
            # Selecciona defensivamente el primer nodo encontrado, ignorando los duplicados
            main_river = coincidencias[0]
            
            # Opcional: Imprimir una advertencia en consola si hay duplicados
            if len(coincidencias) > 1:
                print(f"ADVERTENCIA: Se encontraron {len(coincidencias)} nodos duplicados con el ID {river_id}. Usando el primero.")

        if not main_river:
            _river_type = 13
            main_river = RiverNode(river_id, river_name, _river_type, river_distance, self.root_node, parent=self.root_node)
            main_river.node_cat = river_cat  # TODO: refactor to include it into constructor

        self.parent = main_river

        self.main_river_id = river_id
        self.main_river_name = river_name
        self.main_river_cat = river_cat
        self.main_river_distance = river_distance

    def set_secondary_river(self, river_id, river_name, river_cat, river_distance):
        self.secondary_river_id = river_id
        self.secondary_river_name = river_name
        self.secondary_river_cat = river_cat
        self.secondary_river_distance = river_distance

    def set_coords(self, node_x, node_y):
        self.x = node_x
        self.y = node_y

    def get_order_children_by_distance(self):
        if self.is_root:
            return self.children
        else:
            children = sorted(self.children, key=lambda x: x.node_distance, reverse=False)
            return children

    def get_segments_list(self):
        segments = []
        for child_node in self.children:
            segment = child_node.get_break_input_by_river()

            if segment is not None:
                segments.append(segment)

        self.river_segments = segments

        return segments
    def get_break_input_by_river(self):
        # Si el nodo no está sobre un río, no genera corte
        if self.is_root or not self.main_river_distance:
            return None
            
        segment_data = {
            'break_name': f"{self.main_river_name}_{self.node_name}",
            'river_id': self.main_river_id,
            'river_name': self.main_river_name,
            'river_cat': self.main_river_cat,
            'distance': self.main_river_distance,
            'type': self.node_type
        }
        
        return segment_data

    def get_segments_format(self, river_node_id=None):
        if river_node_id:
            river_node = find_by_attr(self, name="node_id", value=river_node_id)
        else:
            river_node = self

        segments_str = ''
        for ind, segment in enumerate(self.river_segments):
            # set class variable [segments_list] to link with segments
            segment['feature_id'] = ind + 1
            RiverNode.segments_list[ind + 1] = segment

            # make string to use like input in [v.segment]
            segments_str += '{} {} {} {} {} \n'.format(
                segment['type'], segment['feature_id'], segment['cat'], segment['start_offset'], segment['end_offset'])
        # print(segments_str)

        return segments_str

    def get_river_segments_recursive(self, last_child, segments):
        node_before_name = last_child.node_name
        node_before_distance = last_child.node_distance

        # get properties from main river arc associated
        river_node_name = last_child.main_river_name
        river_node_cat = last_child.main_river_cat

        # generate segment string
        for i, child_node in enumerate(last_child.children):

            child_name = child_node.node_name
            child_distance = child_node.node_distance  # distance from main river

            if i == 0:
                break_name = f"Below {node_before_name} Headflow"
            else:
                break_name = f"Below {node_before_name}"

            segment = {
                'start_distance': node_before_distance,
                'end_distance': child_distance,
                'segment_break_name': break_name,
                'river_name': river_node_name
            }
            segments.append(segment)

            # final conditions
            node_before_name = child_name
            node_before_distance = child_distance
            last_child = child_node
        else:
            child_name = last_child.node_name
            child_distance = last_child.node_distance  # distance from main river

            break_name = f"Below {child_name}"

            segment = {
                'start_distance': child_distance,
                'end_distance': None,  # Usamos None en lugar de '100%'
                'segment_break_name': break_name,
                'river_name': river_node_name
            }
            segments.append(segment)

        return segments