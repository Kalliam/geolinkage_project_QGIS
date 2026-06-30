from .Check import Check
from ..utils.Visualizer import Visualizer
from ..settings import NODE_TYPE_ID
import numpy as np

class SuperpositionCheck(Check):
    """
    SuperpositionCheck class is a subclass of Check class.

    This class is used to check if a superposition between two features is corresponded
    by a connection in the WEAP model.

    Attributes:
    ----------
    base_feature : str
        Name of the base feature to check.
    secondary_feature : str
        Name of the secondary feature to check.
    base_feature_type_id : int
        Type ID of the base feature.
    secondary_feature_type_id : int
        Type ID of the secondary feature.
    base_names : dict
        Dictionary to store the names of the base features and the amount of cells
        it has in the linkage file.
    secondary_names : dict
        Dictionary to store the names of the secondary features and the amount of cells
        it has in the linkage file.
    nodes : dict
        Dictionary to store the nodes data.
    connections : dict
        Dictionary to store all the base features and the secondary features
        they are connected to.
    connection_error : dict
        Dictionary to store the errors found in the connections between the base
        and secondary features.

    Methods:
    --------
    add_error(base_element, super_element)
        Add an error to the connection_error dictionary, checks if the base element
        is already in the dictionary and if the super element is already in the base element
        dictionary.
    set_connection(base_info, secondary_info)
        Set the connection between the base and secondary features.
    check_connection(base_name, secondary_name)
        Check if the base element is connected to the secondary element. 
        It returns True if the connection exists or if the base element is not part
        of the WEAP model, False otherwise.
    make_connection_matrix()
        Create a matrix with the connections between the base and secondary features,
        used for visualization.
    make_error_matrix()
        Create a matrix with the amount of errors in the connections between the base
        and secondary features, used for visualization.
    get_name()
        Return the name of the check.
    get_description()
        Return the description of the check.
    plot(visualizator)
        Plot the results of the check, uses the Visualizator instance to write the
        images to files.
        Uses as subroutines the make_connection_matrix and make_error_matrix methods to
        create the necesary data for the visualization.
    arc_init_operation(arc_id, arc)
        Does nothing.
    node_init_operation(node_id, node)
        Saves the information for all the relevant nodes.
    cell_init_operation(cell_id, cell)
        Does nothing.
    arc_check_operation(arc_id, arc)
        Builds the connections between the base and secondary features.
    node_check_operation(node_id, node)
        Does nothing.
    cell_check_operation(cell_id, cell)
        Checks the connections between the base and secondary features present in
        each cell.
    """

    def __init__(self, base_feature, secondary_feature):
        super().__init__()
        self.name = f"Chequeo superposición {base_feature}-{secondary_feature}"
        self.description = f"Chequea si la superposición de elementos [{base_feature}-{secondary_feature}] en el archivo de enlace es correspondida por una conexión en el modelo WEAP, con el fin de prevenir perdida de flujo."

        self.base_feature = base_feature
        self.secondary_feature = secondary_feature

        self.base_feature_type_id = NODE_TYPE_ID[self.base_feature]
        self.secondary_feature_type_id = NODE_TYPE_ID[self.secondary_feature]

        self.base_names = {}
        self.secondary_names = {}
        self.nodes = {}

        self.connections = {}
        self.connection_error = {}

    # Space for auxiliary functions specific to this class.

    def add_error(self, base_element, super_element, area=1):
        if not self.connection_error.get(base_element):
            self.connection_error[base_element] = {}
        if not self.connection_error[base_element].get(super_element):
            self.connection_error[base_element][super_element] = 0
        self.connection_error[base_element][super_element] += area

    def set_connection(self, base_info, secondary_info):
        if not self.connections.get(base_info["name"]):
            # should never happen because we already set every node with an empty dict
            self.connections[base_info["name"]] = dict()
        self.connections[base_info["name"]][secondary_info["name"]] = 0

    def check_connection(self, base_name, secondary_name):
        if base_name in self.connections:
            return secondary_name in self.connections[base_name]

        # Only arrives here if the base element does not exist in WEAP.
        return True

    def make_error_dict_for_df(self):
        error_list = []
        for base_element, secondary_elements in self.connection_error.items():
            base_element_area = self.base_names[base_element]
            for secondary_element, error_area in secondary_elements.items():
                secondary_element_area = self.secondary_names[secondary_element]
                error_list.append(
                    {
                        self.base_feature: base_element,
                        f"{self.base_feature}_area": base_element_area,
                        self.secondary_feature: secondary_element,
                        f"{self.secondary_feature}_area": secondary_element_area,
                        "area_error": error_area,
                        f"percentage_error_of_{self.base_feature}": error_area
                        / base_element_area,
                        f"percentage_error_of_{self.secondary_feature}": error_area
                        / secondary_element_area,
                    }
                )
        return error_list

    def make_error_file_list(self):
        error_list = []
        if not self.connection_error or len(self.connection_error) == 0:
            return error_list

        errors = {}
        for base in self.connection_error.keys():
            for secondary in self.connection_error[base].keys():
                errors[f"{base}-{secondary}"] = {
                    "amount_error": self.connection_error[base][secondary],
                    "percentaje_error_over_primary": self.connection_error[base][
                        secondary
                    ]
                    / self.base_names[base],
                    "percentaje_error_over_secondary": self.connection_error[base][
                        secondary
                    ]
                    / self.secondary_names[secondary],
                }

        # sort the errors by the amount of errors
        errors = dict(
            sorted(
                errors.items(), key=lambda item: item[1]["amount_error"], reverse=True
            )
        )
        longest_base_name = (
            max([len(error.split("-")[0]) for error in errors.keys()]) - 1
        )
        longest_secondary_name = (
            max([len(error.split("-")[1]) for error in errors.keys()]) - 1
        )

        for error in errors.keys():
            [base, secondary] = error.split("-")
            error_txt = f"{self.base_feature}: {base}{" "*(longest_base_name-len(base) + 1)}|-| {self.secondary_feature}: {secondary}{" "*(longest_secondary_name-len(secondary) + 1)}-> {errors[error]['amount_error']} area de error,  {errors[error]['percentaje_error_over_primary']*100:.2f}% del {self.base_feature}, {errors[error]['percentaje_error_over_secondary']*100:.2f}% del {self.secondary_feature}."
            error_list.append(error_txt)

        return error_list

    def make_connection_matrix(self):
        if self.base_names == {} or self.secondary_names == {}:
            return None, None, None

        base_names = list(self.base_names.keys())
        secondary_names = list(self.secondary_names.keys())

        matrix = np.ones((len(base_names), len(secondary_names)), dtype=float)

        for i, base in enumerate(base_names):
            for j, secondary in enumerate(secondary_names):
                if secondary in self.connections.get(base, {}):
                    matrix[i][j] = 0

        # Add the errors in red
        for base, secondaries in self.connection_error.items():
            i = base_names.index(base)
            for secondary in secondaries:
                j = secondary_names.index(secondary)
                matrix[i][j] = 0.5

        # this made a simple connection matrix
        return matrix, base_names, secondary_names

    def make_error_matrix(self):
        if self.connection_error == {}:
            return None, None, None

        base_names = list(self.connection_error.keys())
        secondary_names = list(set().union(*list(self.connection_error.values())))

        matrix = np.zeros((len(base_names), len(secondary_names)), dtype=float)

        # Fill the matrix with the amount of cells in error for each connection
        for base, secondaries in self.connection_error.items():
            i = base_names.index(base)
            for secondary in secondaries:
                j = secondary_names.index(secondary)
                magnitud = (
                    self.connection_error[base][secondary]
                    / self.secondary_names[secondary]
                )
                matrix[i][j] = magnitud

        return matrix, base_names, secondary_names

    def plot(self, visualizer: Visualizer):
        matrix, base_labels, secondary_labels = self.make_connection_matrix()
        visualizer.write_matrix_img(
            matrix,
            f"{self.base_feature}_{self.secondary_feature}_connection_matrix",
            color_labels=["Connection", "Error", "No Connection"],
            colors_list=["#000000", "#ff0000", "#ffffff"],
            row_labels=base_labels,
            column_labels=secondary_labels,
            linewidth=0.5,
            cbar=True,
            min_val=0,
            max_val=1,
            title=f"Connection matrix for {self.base_feature} and {self.secondary_feature} elements",
            x_label=self.secondary_feature,
            y_label=self.base_feature,
        )

        matrix, base_labels, secondary_labels = self.make_error_matrix()
        visualizer.write_matrix_img(
            matrix,
            f"{self.base_feature}_{self.secondary_feature}_error_magnitude_matrix",
            row_labels=base_labels,
            column_labels=secondary_labels,
            linewidth=0.5,
            cbar=True,
            cmap="rocket_r",
            min_val=0,
            max_val=1,
            title=f"Error magnitude matrix for {self.base_feature} and {self.secondary_feature} elements, normalized over the area of {self.secondary_feature}",
            x_label=self.secondary_feature,
            y_label=self.base_feature,
        )

        error_list = self.make_error_file_list()
        visualizer.write_text_file(
            f"{self.base_feature}_{self.secondary_feature}_error_report",
            texts=error_list,
            preface=f"Error report in the superposition of {self.base_feature}-{self.secondary_feature} elements in the linkage file. An error implies that the superposition is not corresponded by a connection in WEAP. The most frequent causes are, a missing link that must be added to the WEAP model, or incorrect coordinates provided for the lower left corner (provide these coordinates with the most decimal places possible).",
        )

        error_dict_for_df = self.make_error_dict_for_df()
        visualizer.write_csv_file(
            f"{self.base_feature}_{self.secondary_feature}_error_report",
            error_dict_for_df,
        )

    def arc_init_operation(self, arc_id, arc):
        pass

    def node_init_operation(self, node_id, node):
        type_id = node["type_id"]
        if (
            type_id == self.base_feature_type_id
            or type_id == self.secondary_feature_type_id
        ):
            self.nodes[node_id] = node
            if type_id == self.base_feature_type_id:
                self.base_names[node["name"]] = 0
                self.connections[node["name"]] = dict()
            else:
                self.secondary_names[node["name"]] = 0

    def cell_init_operation(self, cell_id, cell):
        pass

    def arc_check_operation(self, arc_id, arc):
        src_id = arc["src_id"]
        dst_id = arc["dst_id"]

        if (src_id and dst_id) and (src_id in self.nodes and dst_id in self.nodes):
            if (
                self.nodes[src_id]["type_id"] == self.base_feature_type_id
                and self.nodes[dst_id]["type_id"] == self.secondary_feature_type_id
            ):
                self.set_connection(self.nodes[src_id], self.nodes[dst_id])
            elif (
                self.nodes[src_id]["type_id"] == self.secondary_feature_type_id
                and self.nodes[dst_id]["type_id"] == self.base_feature_type_id
            ):
                self.set_connection(self.nodes[dst_id], self.nodes[src_id])

    def node_check_operation(self, node_id, node):
        pass

    def cell_check_operation(self, cell_id, cell):
        base_element_data = self.get_cell_feature_data(
            cell, self.base_feature
        )  # [] if non existent
        secondary_element_data = self.get_cell_feature_data(
            cell, self.secondary_feature
        )

        cell_area = cell["cell_area"]

        for base in base_element_data:
            # if for the case of non existence and not break
            if base not in self.base_names:
                self.base_names[base] = 0
            self.base_names[base] += cell_area
        for secondary in secondary_element_data:
            # same case of non existence
            if secondary not in self.secondary_names:
                self.secondary_names[secondary] = 0
            self.secondary_names[secondary] += cell_area

        if base_element_data is None or secondary_element_data is None:
            return
        for base in base_element_data:
            base_name = base
            for secondary in secondary_element_data:
                secondary_name = secondary
                if not self.check_connection(base_name, secondary_name):
                    self.add_error(base_name, secondary_name, area=cell_area)
                else:
                    if base_name in self.connections:
                        if secondary_name not in self.connections[base_name]:
                            self.connections[base_name][secondary_name] = 0
                        self.connections[base_name][secondary_name] += cell_area