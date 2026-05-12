import json
import os
import pathlib
from settings import FEATURE_NAMES, OUTPUT_FIELDS, NODE_COL, ARC_COL, NODE_TYPE_ID, ARC_TYPE_ID

class ConfigApp:
    """
        Clase utilitaria que contiene las propiedades y metodos para manejar tres tipos basicos de configuraciones de la aplicacion:
            - configuracion interna de la aplicacion.
            - configuracion del archivo './config/config.json'.
            - configuracion del usuario

        Archivo de Configuracion './config/config.json'.


        Attributes:
        ----------
        grass_internals : Dict[str, str | int]
            Almacena las variables relativas a la sesion de grass creada con la libreria 'gras_session'.

        debug : bool
            (No implementado) Modo de ejecucion de la aplicacion.

        linkage_out : str
            Ruta por defecto donde exportar el archivo final con la malla y la metadata completa. Se obtiene desde el archivo
            de configuracion.

        segments_map_name : str
            Nombre por defecto del mapa con los segmentos de rios (util en caso de realizar debugging.).
            Se obtiene desde el archivo de configuracion. [v.segment]

        inter_river_linkage_name : str
            Nombre por defecto del mapa de la interseccion entre el mapa con la malla y el mapa con los segmentos (util en caso
            de realizar debugging). Se obtiene desde el archivo de configuracion. [v.overlay]

        inter_ds_linkage_name : str
            Nombre por defecto del mapa de la interseccion entre el mapa con la malla y el mapa con los pozos (util en caso
            de realizar debugging). Se obtiene desde el archivo de configuracion. [v.overlay]

        type_names : Dict[str, str]
            Alias a utilizar para el programa principal y las distintas caracteristicas a procesar en los resumenes con
            los resultados finales (parametros de entrada, estadisticas, errores, advertencias) y propositos internos de la
            aplicacion. Por defecto se obtiene del archivo de configuracion (variable: config_data["FEATURE NAMES"]["groundwater"]).

        fields_db : Dict[str, Dict[str, str]] or Dict[MAP][COLUMN][VALUE]
            Nombres de las columnas de los distintos mapas de entrada, de uso interno de la aplicacion.
            Se obtienen del archivo de configuracion y las columnas asociadas a 'nombres' pueden ser definidos por el usuario.
            En caso que el usuario no ingrese alguna de estas columnas, se utiliza la columna asociada en el archivo de configuracion.

        cols_linkage : Dict[str, Dict[str, str | bool]]
            Almacena la configuracion de las columnas en la metadata del archivo final con formato SHP.

        process_msgs : Dict[str, str] or Dict[TASK][MESSAGE]
            Almacena los mensajes de las principales tareas durante la ejecucion de la aplicacion y su resultado positivo o negativo.
            Se utiliza en el resumen final de la aplicacion.

        fields_needed : Dict[str, Dict[str, List[str | bool | list]]]
            Almacena la configuracion usada por las clases (procesadores) para saber cuales on las principales columnas
            de la metadata que deben existir en los mapas de entrada.

        _feature_opts : Dict[str, Any]
            Parametros de configuracion del procesador, se configuran en cada instancia y para cada caracteristica.
            Actualmente se utilizan dos, 'order_criteria' y 'columns_to_save'.
            'order_criteria' identifica si las geometrias del mapa vectorial son medidas por su 'area' o 'length'. 'columns_to_save'
            identifica el numero de columnas a generar en la metadata final, que solo en el caso de los sitios de demanda
            son por defecto 4 columnas y en los demas solo 1 columna.


        Metodos:
        --------
        get_columns_to_save(self, feature_type: str)
            Retorna el numero de columnas que deben crearse en la metadata final para el tipo de caracteristica o
            archivo final dado por el parametro 'feature_type'.

        """




    def __init__(self, epsg_code: int = None, gisdb: str = None, location: str = None, mapset: str = None,
                 debug: bool = False, order_criteria: str = None, columns_to_save: int = None):

        

        self.type_names = {
            'GroundwaterProcess': FEATURE_NAMES.groundwater,
            'CatchmentProcess': FEATURE_NAMES.catchment,
            'RiverProcess': FEATURE_NAMES.river,
            'DemandSiteProcess': FEATURE_NAMES.demand_sites,
            'GeoKernel': FEATURE_NAMES.geometry,
            'AppKernel': FEATURE_NAMES.main_program,
            'GeoCheck': FEATURE_NAMES.geometry_checker,
        }



        self.debug = debug

        # Default names in vector maps
        ### mover a la interfaz
        # self.linkage_out = config_data["DEFAULT MAP NAMES"]["LINKAGE FINAL MAP"]
        # self.segments_map_name = config_data["DEFAULT MAP NAMES"]["RIVER SEGMENTS MAP"]
        # self.inter_river_linkage_name = config_data["DEFAULT MAP NAMES"]["LINKAGE INTER RIVER SEGMENTS MAP"]
        # self.inter_ds_linkage_name = config_data["DEFAULT MAP NAMES"]["LINKAGE INTER DEMAND SITE MAP"]

        # Default opts
        # # order_criteria: to select between two or more geometries which intersect one cell
        # # columns_to_save: columns to save in final linkage file by feature

        ### 
        # self.default_opts = {
        #     "CELL OVERLAP CRITERIA": {
        #         "catchment": "area",
        #         "groundwater": "area",
        #         "demand_site": "area",
        #         "river": "length"
        #     },

 
        ## eliminar, QGIS se encarga de esto
        # self.default_opts = {
        #     self.type_names['CatchmentProcess']: {
        #         'order_criteria': config_data["CELL OVERLAP CRITERIA"]["catchment"],
        #         'columns_to_save': config_data["COLUMNS FOR FEATURE"]["catchment"]
        #     },
        #     self.type_names['GroundwaterProcess']: {
        #         'order_criteria': config_data["CELL OVERLAP CRITERIA"]["groundwater"],
        #         'columns_to_save': config_data["COLUMNS FOR FEATURE"]["groundwater"]
        #     },
        #     self.type_names['RiverProcess']: {
        #         'order_criteria': config_data["CELL OVERLAP CRITERIA"]["river"],
        #         'columns_to_save': config_data["COLUMNS FOR FEATURE"]["river"]
        #     },
        #     self.type_names['DemandSiteProcess']: {
        #         'order_criteria': config_data["CELL OVERLAP CRITERIA"]["demand_site"],
        #         'columns_to_save': config_data["COLUMNS FOR FEATURE"]["demand_site"]
        #     },
        # }


        # Metadata fields in vector maps

        ## input se va para la interfaz de usuario
        self.fields_db = {
            # self.type_names['GeoKernel']: {
            #     'arc_name': config_data["FIELDS IN INPUT MAP"]["geo_map"]["arc_name"],
            #     'node_name': config_data["FIELDS IN INPUT MAP"]["geo_map"]["node_name"],
            #     'arc_type': config_data["FIELDS IN INPUT MAP"]["geo_map"]["arc_type"],
            #     'node_type': config_data["FIELDS IN INPUT MAP"]["geo_map"]["node_type"]
            # },
            # self.type_names['CatchmentProcess']: {
            #     'name': config_data["FIELDS IN INPUT MAP"]["catchment_map"]["name"],
            #     'modflow': config_data["FIELDS IN INPUT MAP"]["catchment_map"]["modflow"]
            # },
            # self.type_names['GroundwaterProcess']: {
            #     'name': config_data["FIELDS IN INPUT MAP"]["gw_map"]["name"]  # GW or GROUNDWAT usually
            # },
            # self.type_names['RiverProcess']: {
            #     'priority': config_data["FIELDS IN INPUT MAP"]["river_map"]["priority"],  # not used yet
            #     'segment_break_name': config_data["FIELDS IN INPUT MAP"]["river_map"]["segment_break_name"],
            #     'river_name': config_data["FIELDS IN INPUT MAP"]["river_map"]["river_name"]
            # },
            # self.type_names['DemandSiteProcess']: {
            #     'name': config_data["FIELDS IN INPUT MAP"]["ds_map"]["name"]
            # },
            # 'linkage-in': {  # init linkage
            #     'row': config_data["FIELDS IN INPUT MAP"]["linkage_in_map"]["row"],
            #     'col': config_data["FIELDS IN INPUT MAP"]["linkage_in_map"]["col"]
            # }
            'linkage': {  # final linkage file
                self.type_names['CatchmentProcess']: OUTPUT_FIELDS.catchment ,
                self.type_names['GroundwaterProcess']: OUTPUT_FIELDS.groundwater ,
                self.type_names['RiverProcess']: OUTPUT_FIELDS.river,
                self.type_names['DemandSiteProcess']: OUTPUT_FIELDS.demand_site,
                'row': OUTPUT_FIELDS.row,
                'col': OUTPUT_FIELDS.col,
                'rc': OUTPUT_FIELDS.rc,
                'row_in': 'row',
                'col_in': 'column'
            },
        }

        self.cols_linkage = {  # linkage-out is based from this
            'row': {
                'action': 'rename',
                #'name_old': config_data["FIELDS IN INPUT MAP"]["linkage_in_map"]["row"],
                'name': OUTPUT_FIELDS.row,
                'type': 'INT',
                '_type_name': 'integer',
                '_necessary': True
            },

            'col': {
                'action': 'rename',
                #'name_old': config_data["FIELDS IN INPUT MAP"]["linkage_in_map"]["col"],
                'name': OUTPUT_FIELDS.col,
                'type': 'INT',
                '_type_name': 'integer',
                '_necessary': True
            },

            'rc': {
                'action': 'add',
                'name': OUTPUT_FIELDS.rc,
                'type': 'VARCHAR',
                '_type_name': 'varchar',
                '_necessary': True
            },

            self.type_names['CatchmentProcess']: {
                'action': 'add',
                'name': OUTPUT_FIELDS.catchment,
                'type': 'VARCHAR',
                '_type_name': 'varchar',
                '_necessary': True
            },

            'landuse': {
                'action': 'add',
                'name': OUTPUT_FIELDS.landuse,
                'type': 'VARCHAR',
                '_type_name': 'varchar',
                '_necessary': True
            },

            self.type_names['GroundwaterProcess']: {
                'action': 'add',
                'name': OUTPUT_FIELDS.groundwater,
                'type': 'VARCHAR',
                '_type_name': 'varchar',
                '_necessary': True
            },

            self.type_names['RiverProcess']: {
                'action': 'add',
                'name': OUTPUT_FIELDS.river,
                'type': 'VARCHAR', '_type_name': 'varchar',
                '_necessary': True
            },

            self.type_names['DemandSiteProcess']: {
                'action': 'add',
                'name': OUTPUT_FIELDS.demand_site,
                'type': 'VARCHAR',
                '_type_name': 'varchar',
                '_necessary': True
            },
        }

        ## mensajes de consola que vienen desde settings.json, los quito de aca y se los pongo a cada postprocessor
        # self.process_msgs = config_data['PROCESSING LINES']

        self.fields_needed = {
            'main': {  # alias: [name, needed]
                self.type_names['CatchmentProcess']: [self.fields_db[self.type_names['CatchmentProcess']]['name'], True],
                self.type_names['GroundwaterProcess']: [self.fields_db[self.type_names['GroundwaterProcess']]['name'], True],
                self.type_names['RiverProcess']: [self.fields_db[self.type_names['RiverProcess']]['river_name'], True],
                self.type_names['DemandSiteProcess']: [self.fields_db[self.type_names['DemandSiteProcess']]['name'], True],
                self.type_names['GeoKernel']: [[self.fields_db[self.type_names['GeoKernel']]['arc_name'], True],   # arc fields
                                               [self.fields_db[self.type_names['GeoKernel']]['node_name'], True]],  # node fields
                self.type_names['AppKernel']: [self.fields_db['linkage-in']['row'], True]
            },
            'secondary': {
                self.type_names['CatchmentProcess']: None,
                self.type_names['GroundwaterProcess']: None,
                self.type_names['RiverProcess']: [self.fields_db[self.type_names['RiverProcess']]['segment_break_name'], True],
                self.type_names['DemandSiteProcess']: None,
                self.type_names['GeoKernel']: [[self.fields_db[self.type_names['GeoKernel']]['arc_type'], True],    # arc fields
                                               [self.fields_db[self.type_names['GeoKernel']]['node_type'], True]],  # node fields
                self.type_names['AppKernel']: [self.fields_db['linkage-in']['col'], True]
            },
            'limit': {
                self.type_names['CatchmentProcess']: [self.fields_db[self.type_names['CatchmentProcess']]['modflow'], False],
                self.type_names['GroundwaterProcess']: None,
                self.type_names['RiverProcess']: None,
                self.type_names['DemandSiteProcess']: None,
                self.type_names['GeoKernel']: None,
                self.type_names['AppKernel']: [self.fields_db['linkage-in']['col'], True]
            }
        }

        # prepare arc and node maps configuration
        self.node_columns = NODE_COL  # columns to read node map
        self.arc_columns = ARC_COL  # columns to read arc map
        self.nodes_type_id = NODE_TYPE_ID  # node ids in node map
        self.arc_type_id = ARC_TYPE_ID  # arc ids in node map

    def get_order_criteria(self, feature_type: str):
        ret = self.default_opts[feature_type]['order_criteria']
        return ret

    def set_order_criteria(self, feature_type: str, order_criteria: str):
        self.default_opts[feature_type]['order_criteria'] = order_criteria

    def get_columns_to_save(self, feature_type: str):
        return self.default_opts[feature_type]['columns_to_save']

    def set_columns_to_save(self, feature_type: str, columns_to_save: int):
        self.default_opts[feature_type]['columns_to_save'] = columns_to_save

    def get_needed_fields(self, alias: str, is_node: bool = False, is_arc: bool = False):
        fields = {}

        if not (is_node or is_arc):
            for concept in ('main', 'secondary', 'limit'):
                if alias in self.fields_needed[concept] and self.fields_needed[concept][alias] is not None:
                    fields[concept] = {
                        'name': self.fields_needed[concept][alias][0],
                        'needed': self.fields_needed[concept][alias][1]
                    }
        else:
            index = 0 if is_arc else 1
            for concept in ('main', 'secondary', 'limit'):
                if alias in self.fields_needed[concept] and self.fields_needed[concept][alias] is not None:
                    fields[concept] = {
                        'name': self.fields_needed[concept][alias][index][0],
                        'needed': self.fields_needed[concept][alias][index][1]
                    }

        return fields

    def get_feature_names(self):
        return self.type_names.values()

    def set_config_field(self, feature_type: str, field_type: str, field_new_name: str):
        _err = False

        if field_type in self.fields_needed and feature_type in self.fields_needed[field_type]:
            self.fields_needed[field_type][feature_type][0] = field_new_name
        else:
            _err = True

        return _err

    def get_config_field_name(self, feature_type: str, field_type: str = 'main'):
        field_value = None

        if field_type in self.fields_needed and feature_type in self.fields_needed[field_type]:
            if self.fields_needed[field_type][feature_type] is not None:
                field_value = self.fields_needed[field_type][feature_type][0]  # name

        return field_value

    def get_linkage_out_file_name(self):
        return self.linkage_out

    #mensajes de consola
    # def get_process_msg(self, msg_name: str):
    #     if msg_name in self.process_msgs:
    #         msg_info = self.process_msgs[msg_name]
    #     else:
    #         msg_info = 'Message for [{}] not found!'.format(msg_name)

    #     return msg_info





