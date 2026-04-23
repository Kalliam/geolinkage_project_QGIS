{
    ## este campo va para la interfaz de usuario
    "DEFAULT MAP NAMES": {
        "LINKAGE FINAL MAP": "linkage_final_new",
        "RIVER SEGMENTS MAP": "arc_segments",
        "LINKAGE INTER RIVER SEGMENTS MAP": "output_inter_linkage_rivers",
        "LINKAGE INTER DEMAND SITE MAP": "output_inter_linkage_demand_sites"
    },

    ## ver que hacer con este
    "GEO": {
          "NODE_COL": {
              "name": "Name",
              "type_id": "TypeID",
              "obj_id": "ObjID",
              "cat": "cat"
          },

          "ARC_COL": {
            "name": "Name",
            "type_id": "TypeID",
            "type_name": "TypeName",
            "obj_id": "ObjID",
            "cat": "cat",
            "src_obj_id": "SrcObjID",
            "dest_obj_id": "DestObjID"
          },

          "NODE_TYPE_ID": {
              "demand_site": 1,
              "groundwater": 3,
              "reservoir": 4,
              "river_withdrawal": 10,
              "diversion_outflow": 11,
              "tributary_inflow": 13,
              "return_flow_node": 17,
              "catchment": 21,
              "catchment_inflow_node": 23
        },

          "ARC_TYPE_ID": {
              "river": 6,
              "transmission_link": 7,
              "return_flow": 8,
              "canal": 15,
              "runoff_infiltration": 22
        }
    },

    ## este campo va para la interfaz de usuario
    "FIELDS IN INPUT MAP": {
        "catchment_map": {
            "name":  "Catchment",
            "modflow": "MODFLOW"
        },
        "gw_map": {
            "name": "GW"
        },
        "ds_map": {
            "name": "DS"
        },
        "river_map": {
            "priority": "principal",
            "segment_break_name": "segment_break_name",
            "river_name": "river_name"
        },
        "geo_map": {
            "arc_name": "Name",
            "node_name": "Name",
            "arc_type": "TypeID",
            "node_type": "TypeID"
        },
        "linkage_in_map": {
          "row": "row",
          "col": "column"
        }
    },

    ## ver que hacer con este
    "FIELDS IN OUTPUT FILE": {
        "catchment": "CATCHMENT",
        "groundwater": "GROUNDWAT",
        "demand_site": "DEMAND",
        "river": "RIVERREAC",
        "row": "row",
        "col": "column",
        "rc": "MF_RC",
        "landuse": "LANDUSE"
    },

    ## este campo reemplaza por length o area dependiendo del tipo de feature, creo que se puede eliminar
    "CELL OVERLAP CRITERIA": {
        "catchment": "area",
        "groundwater": "area",
        "demand_site": "area",
        "river": "length"
    },

    # mover como diccionario dentro del postprocessor que lo use?
    "COLUMNS FOR FEATURE": {
        "catchment": 1,
        "groundwater": 1,
        "demand_site": 4,
        "river": 1
    },

    # mensajes de la consola, puedo implementarlos en la ejecucion de QGIS?
    "PROCESSING LINES": {
            "import_maps": "Importando archivo [{map_path}] con nombre [{output_name}]",
            "set_origin_in_map": "Definiendo origen del mapa [{map_name}] a: x_ll=[{x_ll}], y_ll=[{y_ll}], z_rot=[{z_rot}]",
            "setup_arcs": "Leyendo geometrías de Esquema WEAP",
            "_inter_map_with_linkage": "Intersectando mapa [{map_name}] con linkage",
            "get_catchments_from_map": "Validando cuencas encontradas en esquema WEAP con archivo de cuencas",
            "get_gws_from_map": "Validando acuíferos encontrados en esquema WEAP con archivo de acuíferos",
            "make_cell_data_by_main_map": "Procesando [{inter_map_geo_type}] de interseccion del mapa primario [{map_name}] con linkage",
            "make_cell_data_by_secondary_maps": "Procesando [{inter_map_geo_type}] de interseccion del mapa secundario [{map_name}] con linkage",
            "make_segment_map": "Calculando y almacenando divisiones en ríos",
            "init_linkage_file": "Formateando estructura de archivo linkage",
            "mark_linkage_active": "Guardando datos en archivo linkage",
            "export_to_shapefile": "Exportando linkage a [{output_path}]",
            "check_basic_columns": "Validando columnas necesarias para [{map_name}]: {columns}",
            "check_names_with_geo": "Validando mapas con geometrías de nodos y arcos",
            "check_names_between_maps": "Validando nombres de geometrias entre mapas",
            "get_ds_map_from_node_map": "Generando mapa principal a partir de mapa de nodos",
            "_read_well_files": "Leyendo el archivo [{well_path}] para identificar los pozos del mapa de Nodos.",
            "init_check_arc": "Recorriendo arcos para crear estructura de datos",
            "init_check_node": "Recorriendo nodos para crear estructura de datos",
            "init_check_cell": " Recorriendo celdas para crear estructura de datos",
            "perform_check_arc": "Llevando a cabo chequeos sobre arcos",
            "perform_check_node": "Llevando a cabo chequeos sobre nodos",
            "perform_check_cell": "Llevando a cabo chequeos sobre celdas" 
    },

    ## dejar en settings o pasar a cada postprocessor que lo use?
    "FEATURE NAMES": {
        "groundwater": "groundwater",
        "catchment": "catchment",
        "demand sites": "demand_site",
        "river": "river",
        "geometry": "geo",
        "main program": "main",
        "geometry checker": "geo_check"
    }
}



# Archivo que reemplazaria al config.json

NODE_COL = {
    "name": "Name",
    "type_id": "TypeID",
    "obj_id": "ObjID",
    "cat": "cat"
}

ARC_COL = {
    "name": "Name",
    "type_id": "TypeID",
    "type_name": "TypeName",
    "obj_id": "ObjID",
    "cat": "cat",
    "src_obj_id": "SrcObjID",
    "dest_obj_id": "DestObjID"
}


# Diccionario de identificadores de WEAP
NODE_TYPE_ID = {
    "demand_site": 1,
    "groundwater": 3,
    "reservoir": 4,
    "river_withdrawal": 10,
    "diversion_outflow": 11,
    "tributary_inflow": 13,
    "return_flow_node": 17,
    "catchment": 21,
    "catchment_inflow_node": 23
}

ARC_TYPE_ID = {
    "river": 6,
    "transmission_link": 7,
    "return_flow": 8,
    "canal": 15,
    "runoff_infiltration": 22
}


# Nombres obligatorios (máx 10 caracteres) para el DBF de salida
OUTPUT_FIELDS = {
    "catchment": "CATCHMENT",
    "groundwater": "GROUNDWAT",
    "demand_site": "DEMAND",
    "river": "RIVERREAC",
    "row": "row",
    "col": "column",
    "rc": "MF_RC",
    "landuse": "LANDUSE"
}

# Límite de columnas generadas por tipo de feature
FEATURE_COLUMN_LIMIT = {
    "catchment": 1,
    "groundwater": 1,
    "demand_site": 4,
    "river": 1
}