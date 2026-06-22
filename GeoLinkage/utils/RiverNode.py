from anytree import Node, RenderTree, NodeMixin, AsciiStyle
from anytree.search import find_by_attr, findall_by_attr


class RiverNode(NodeMixin):
    """
    It is responsible for providing the structure that stores river segments. These segments are created
    because there are nodes on the surface node map that modify the river flow (injecting or extracting
    water into the river). For the integration between groundwater model and surface model
    it is necessary to identify the river segment where it occurs.

    Initial:
        |------------------------- RIVER 1 ----------------------------|
        =============[NODE 1]====================[NODE 2]=============>

    Final:
        |--Below NODE 1-|       |----Below NODE 2---|       |Below RIVER 1 Headflow-|
        ================[NODE 1]====================[NODE 2]=======================>

    Attributes:
    ----------
    segments_list : Dict[int, Dict[str, str | int | float]]
        Class variable that stores the complete segments list.

    river_segments : List[Dict[str, str | int | float]]
        List of accumulated segments for children of this RiverNode. It is used to rebuild
        the river tree structure by linking nodes to their closest rivers and calculate line distances.
        The segment data stored are:
            - 'feature_id': new ID <int> for each segment in the new map.
            - 'type': segment type, it is always 'L' for line. (It is required by WEAP for linking)
            - 'fid': Internal vector feature ID for the river.
            - 'start_offset': starting percentage or distance where to start dividing the arc.
            - 'end_offset': final percentage or distance where to finish dividing the arc.
            - 'break_name': river segment name (e.g., Below [Node] or Below [RIVER] Headflow).
            - 'river_name': river name.

    root_node : RiverNode
        RiverNode root. It is the access point to the entire segments structure.

    node_id : int
        Node ID.

    node_name : str
        Node name.

    node_type : int
        Node type (e.g., 'Tributary node').

    node_distance : float
        Distance between the node and the beginning of the river arc.

    x : float
        x-axis node coordinate.

    y : float
        y-axis node coordinate.

    node_fid : int
        Internal vector feature ID.

    parent : RiverNode
        RiverNode parent (inherited from NodeMixin).

    children : tuple of RiverNode
        RiverNode children (inherited from NodeMixin).

    main_river_id : int
        ID that identifies the main river the tributary reaches.

    main_river_fid : int
        Internal vector feature ID that identifies the main river.

    main_river_name : str
        River name that the tributary reaches.

    main_river_distance : float
        Distance between node and arc beginning of the main river.

    secondary_river_id : int
        Tributary river ID on the arc vector map.

    secondary_river_name : str
        Tributary river name on the arc vector map.

    Methods:
    -------
    get_segment_break_name(cls, segment_line_fid)
        Returns a particular segment name and the river name to which it belongs.

    set_main_river(self, river_id, river_name, river_fid, river_distance)
        Bind a new RiverNode within the tree structure.

    get_order_children_by_distance(self)
        Returns an ordered list of the children of the node, ordered by distance.

    get_segments_list(self)
        Returns a list with all segments child of this node.

    get_break_input_by_river(self)
        Builds the segments list with their structured data for this node.
    """

    segments_list = {}

    def __init__(self, node_id, node_name, node_type, node_distance, node_fid=-1, root_node=None, parent=None, children=None):
        super(RiverNode, self).__init__()

        if root_node:
            self.root_node = root_node

        self.node_id = node_id
        self.node_name = node_name
        self.node_type = node_type
        self.node_distance = node_distance  # if it is a inflow node, use the main_river_distance
        self.x = None
        self.y = None
        self.node_fid = node_fid  

        self.parent = parent
        if children:
            self.children = children

        self.river_segments = []

        # main river or parent river
        self.main_river_fid = None
        self.main_river_name = None
        self.main_river_id = None
        self.main_river_distance = self.node_distance

        # secondary river or subflow river
        self.secondary_river_fid = None
        self.secondary_river_name = None
        self.secondary_river_id = None
        self.secondary_river_distance = None

    @classmethod
    def get_segment_break_name(cls, segment_line_fid):
        segment_break_name = RiverNode.segments_list[segment_line_fid]['break_name']
        river_name = RiverNode.segments_list[segment_line_fid]['river_name']

        return segment_break_name, river_name

    def set_main_river(self, river_id, river_name, river_fid, river_distance):
        # make a node representing main river (parent river)
        coincidencias = findall_by_attr(self.root_node, name="node_id", value=river_id)
        
        if not coincidencias:
            main_river = None
        else:
            # select the first node found, ignoring duplicates
            main_river = coincidencias[0]
            
        if not main_river:
            _river_type = 13
            main_river = RiverNode(
                node_id=river_id, 
                node_name=river_name, 
                node_type=_river_type, 
                node_distance=river_distance, 
                node_fid=river_fid, 
                root_node=self.root_node, 
                parent=self.root_node
            )
        
        self.parent = main_river

        self.main_river_id = river_id
        self.main_river_name = river_name
        self.main_river_fid = river_fid
        self.main_river_distance = river_distance

    def set_secondary_river(self, river_id, river_name, river_fid, river_distance):
        self.secondary_river_id = river_id
        self.secondary_river_name = river_name
        self.secondary_river_fid = river_fid
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
        # If the node is not on a river, it does not generate a cut
        if self.is_root or not self.main_river_distance:
            return None
            
        segment_data = {
            'break_name': f"{self.main_river_name}_{self.node_name}",
            'river_id': self.main_river_id,
            'river_name': self.main_river_name,
            'river_fid': self.main_river_fid,
            'distance': self.main_river_distance,
            'type': self.node_type
        }
        
        return segment_data

    def get_river_segments_recursive(self, last_child, segments):
        node_before_name = last_child.node_name
        node_before_distance = last_child.node_distance

        # get properties from main river arc associated
        river_node_name = last_child.main_river_name
        river_node_fid = last_child.main_river_fid

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
                'end_distance': None,  #None instead of '100%'
                'segment_break_name': break_name,
                'river_name': river_node_name
            }
            segments.append(segment)

        return segments