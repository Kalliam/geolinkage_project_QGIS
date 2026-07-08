from ..utils.Visualizer import Visualizer
from qgis.PyQt.QtCore import QCoreApplication


class GeoChecker:
    """
    GeoChecker class is the main class for the GeoChecker postprocessor. It is in charge of managing the checks,
    looping through the data and visualizing the checks.

    Attributes:
    ----------

    checks : list
        List of checks to be performed, this checks are instances of the Check class.

    arcs : dict
        Dictionary containing the arcs data.
        {Arc ID :
            {
                'type_id': geometry type ID of the arc,
                'src_id': source node ID (or None),
                'dst_id': destination node ID (or None)
            }
        }

    nodes : dict
        Dictionary containing the nodes data with the following structure.
        {Node ID :
            {
                'type_id': geometry type ID,
                'name': node name,
                'x': x-axis position of the node,
                'y': y-axis position of the node,
                'cat': node internal ID (used by 'pygrass library')
            }
        }
    cells : dict
        Dictionary containing the consolidated cells data.
        {Cell ID :
            {
                'catchment': {number_of_data : int, cell_id : int, row : int, col : int, data : [{area : float, cell_id : int, name : str, map_name : str}]},
                'groundwater': {number_of_data : int, cell_id : int, row : int, col : int, data : [{area : float, cell_id : int, name : str, map_name : str}]},
                'river': {number_of_data : int, cell_id : int, row : int, col : int, data : [{area : float, cell_id : int, name : str, map_name : str}]},
                'demand_site': {number_of_data : int, cell_id : int, row : int, col : int, data : [{area : float, cell_id : int, name : str, map_name : str}]}
            }
        }

    visualizer : visualizer
        visualizer object to manage the visualization of the checks.

    Methods:
    --------
    set_arcs_and_nodes(arcs, nodes):
        Set the arcs and nodes data to be used in the checks.

    set_consolidate_cells(cells):
        Set the consolidated cells data to be used in the checks.

    setup(consolidate_cells, arcs, nodes):
        Set the consolidated cells, arcs and nodes data to be used in the checks.

    init_nodes_loop():
        Do a first loop through the nodes data and initialize the checks for the nodes.

    init_arcs_loop():
        Do a first loop through the arcs data and initialize the checks for the arcs.

    init_cells_loop():
        Do a first loop through the cells data and initialize the checks for the cells.

    check_nodes_loop():
        Loop through the nodes data and perform the checks for the nodes.

    check_arcs_loop():
        Loop through the arcs data and perform the checks for the arcs.

    check_cells_loop():
        Loop through the cells data and perform the checks for the cells.

    build_checks():
        Run the initial loop through the data.

    perform_checks():
        Runs the final loop through the data to perform the checks.

    plot_checks():
        Loop through the checks and run the plot method for each one.

    run():
        Run the GeoChecker postprocessor, initializing, performing the checks, returning errors and visualizing

    """

    def __init__(self, checks, folder_path=None):
        self.checks = checks

        self.arcs = None
        self.nodes = None
        self.cells = None

        self.visualizer = Visualizer()
        self.folder_path = None

        if folder_path is not None:
            self.set_result_path(folder_path)

    def set_result_path(self, path):
        self.folder_path = str(path)
        self.visualizer.set_result_path(str(path))

    def set_arcs_and_nodes(self, arcs, nodes):
        self.arcs = arcs
        self.nodes = nodes

    def set_consolidate_cells(self, cells):
        self.cells = cells

    def setup(self, consolidate_cells, arcs, nodes):
        self.set_consolidate_cells(consolidate_cells)
        self.set_arcs_and_nodes(arcs, nodes)

    def init_nodes_loop(self):
        for i, (node_id, node) in enumerate(self.nodes.items()):
            if i % 1000 == 0:
                QCoreApplication.processEvents()
            for check in self.checks:
                check.node_init_operation(node_id, node)

    def init_arcs_loop(self):
        for i, (arc_id, arc) in enumerate(self.arcs.items()):
            if i % 1000 == 0:
                QCoreApplication.processEvents()
            for check in self.checks:
                check.arc_init_operation(arc_id, arc)

    def init_cells_loop(self):
        for i, (cell_id, cell) in enumerate(self.cells.items()):
            if i % 1000 == 0:
                QCoreApplication.processEvents()
            for check in self.checks:
                check.cell_init_operation(cell_id, cell)

    def check_nodes_loop(self):
        for i, (node_id, node) in enumerate(self.nodes.items()):
            if i % 1000 == 0:
                QCoreApplication.processEvents()
            for check in self.checks:
                check.node_check_operation(node_id, node)

    def check_arcs_loop(self):
        for i, (arc_id, arc) in enumerate(self.arcs.items()):
            if i % 1000 == 0:
                QCoreApplication.processEvents()
            for check in self.checks:
                check.arc_check_operation(arc_id, arc)

    def check_cells_loop(self):
        for i, (cell_id, cell) in enumerate(self.cells.items()):
            if i % 1000 == 0:
                QCoreApplication.processEvents()
            for check in self.checks:
                check.cell_check_operation(cell_id, cell)

    def build_checks(self):
        self.init_arcs_loop()
        self.init_nodes_loop()
        self.init_cells_loop()

    def perform_checks(self):
        self.check_arcs_loop()
        self.check_nodes_loop()
        self.check_cells_loop()

    def plot_checks(self):
        for check in self.checks:
            check.plot(self.visualizer)

    def run(self):
        # Initializing secuence
        self.build_checks()
        # Checking secuence
        self.perform_checks()
        self.plot_checks()
