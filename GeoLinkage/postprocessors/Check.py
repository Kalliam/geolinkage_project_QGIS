from abc import ABC, abstractmethod

class Check(ABC):
    """
    Check class is the abstract class for the checks to be performed in the postprocessor.
    It contains the abstract methods that must be implemented by the subclasses.

    Attributes:
    ----------
    errors : list
        List of errors found during the check.
    
    Methods:
    --------
    get_name()
        Abstract method to get the name of the check.
    
    get_description()
        Abstract method to get the description of the check.
    
    arc_init_operation(arc_id, arc)
        Abstract method called by GeoChecker to use the data of the arcs. 
        Usually used to setup data structures.
    
    node_init_operation(node_id, node)
        Abstract method called by GeoChecker to use the data of the nodes. 
        Usually used to setup data structures.
    
    cell_init_operation(cell_id, cell)
        Abstract method called by GeoChecker to use the data of the cells.
        Usually used to setup data structures.
    
    arc_check_operation(arc_id, arc)
        Abstract method called by GeoChecker.
        Usually used to perform the check over an arc using the previously
        setup data structures.

    node_check_operation(node_id, node)
        Abstract method called by GeoChecker.
        Usually used to perform the check over a node using the previously
        setup data structures.
    
    cell_check_operation(cell_id, cell)
        Abstract method called by GeoChecker.
        Usually used to perform the check over a cell using the previously
        setup data structures.
    
    plot(visualizator)
        Abstract method to plot the results of the check. Interacts with a Visualizator instance,
        which contains all the methods to write to files and visualize the information in different ways.

    get_errors()
        Method to get the errors found during the check.
        Meant to be called after the checks are finished.
    
    get_cell_feature_data(cell, feature_type)
        Method to get the data of a feature from a cell structure.
    
    get_cell_feature_names(cell, feature_type)
        Method to get the names of a feature from a cell structure.

    """
    def __init__(self):
        self.errors = []
        self.name = None
        self.description = None

    # Space for auxiliary functions

    def get_cell_feature_data(self, cell, feature_type):
        # 
        feature = cell[feature_type]
        if feature:
            return feature["data"]
        else: 
            return []
    
    # This one incurs in a mistake when dealing with demand_sites, it only gives you the first demand site name.
    def get_cell_feature_names(self, cell, feature_type):
        names = []
        feature = cell[feature_type]
        if feature:
            for f in feature["data"]:
                names.append(f["name"])
        return names

    # Abstract methods

    @abstractmethod
    def get_name(self):
        pass

    @abstractmethod
    def get_description(self):
        pass

    @abstractmethod
    def arc_init_operation(self, arc_id, arc):
        pass

    @abstractmethod
    def node_init_operation(self, node_id, node):
        pass

    @abstractmethod
    def cell_init_operation(self, cell_id, cell):
        pass

    @abstractmethod
    def arc_check_operation(self, arc_id, arc):
        pass

    @abstractmethod
    def node_check_operation(self, node_id, node):
        pass

    @abstractmethod
    def cell_check_operation(self, cell_id, cell):
        pass

    @abstractmethod
    def plot(self, visualizator):
        pass

    def get_errors(self):
        return self.errors
    
    def get_name(self):
        return self.name

    def get_description(self):
        return self.description
    
