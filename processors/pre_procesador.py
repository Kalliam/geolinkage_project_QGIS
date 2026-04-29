
# @main_task
def check_names_with_geo(self):
    self.set_data_from_geo()  # get the feature names in geo maps (node and arc)

    if len(self._features_by_map) == 0:
        self.set_feature_names_in_maps(imported=True)

    for feature_name in self._features_by_map.keys():
        feature_id = self.get_feature_id_by_name(feature_name)  # find [feature_name] in geo features
        map_names = ', '.join(self._features_by_map[feature_name])

        if not feature_id:  # not exists in geometries (arcs and nodes)
            msg_error = 'El nombre [{}] en los mapas [{}] no existe en las geometrias bases de arcos y nodos.'.format(
                feature_name, map_names
            )
            self.append_error(msg=msg_error, typ=self.get_feature_type(), code='10')  # check error codes = 1[x]

    self.summary.set_process_line(msg_name='check_names_with_geo', check_error=self.check_errors(code='10'))

    return self.check_errors(code='10'), self.get_errors(code='10')

# @main_task
def check_names_between_maps(self):
    self.set_data_from_geo()  # get the feature names in geo maps (node and arc)

    if len(self._features_by_map) == 0:
        self.set_feature_names_in_maps(imported=True)

    check_maps = [f_name for f_name in self._features_by_map if len(self._features_by_map[f_name]) > 1]
    for feature_name in check_maps:
        map_names = ', '.join(self._features_by_map[feature_name])
        msg_error = 'El nombre [{}] se encuentra en mas de un mapa ([{}]) al mismo tiempo.'.format(
            feature_name, map_names
        )
        self.append_error(msg=msg_error, code='11', typ=self.get_feature_type())  # check error codes = 1[x]

    self.summary.set_process_line(msg_name='check_names_between_maps', check_error=self.check_errors(code='11'))

    return self.check_errors(code='11'), self.get_errors(code='11')





def validar_integridad_nombres(qgs_layer_poligonos, qgs_layer_nodos, columna_nombre_poligono, columna_nombre_nodo):
    """
    Realiza las validaciones semánticas previas al procesamiento espacial.
    """
    # 1. Extraer todos los nombres rápidamente a listas
    nombres_poligonos = [feat[columna_nombre_poligono] for feat in qgs_layer_poligonos.getFeatures() if feat[columna_nombre_poligono]]
    nombres_nodos = [feat[columna_nombre_nodo] for feat in qgs_layer_nodos.getFeatures() if feat[columna_nombre_nodo]]

    # 2. Validación de Duplicidad (Código 11)
    # Si la longitud del set (elementos únicos) es menor a la lista original, hay duplicados.
    if len(nombres_poligonos) != len(set(nombres_poligonos)):
        # Puedes usar colecciones de Python para encontrar cuáles están duplicados exactamente
        import collections
        duplicados = [item for item, count in collections.Counter(nombres_poligonos).items() if count > 1]
        raise ValueError(f"Error de Duplicidad: Los elementos {duplicados} están repetidos en el mapa de polígonos.")

    # 3. Validación de Orfandad (Código 10)
    # Convertimos a conjuntos para operaciones de resta rápidas
    set_poligonos = set(nombres_poligonos)
    set_nodos = set(nombres_nodos)
    
    # ¿Hay polígonos que no tienen un nodo asociado?
    huerfanos = set_poligonos - set_nodos
    
    if huerfanos:
        raise ValueError(f"Error de Orfandad: Los polígonos {huerfanos} no tienen un nodo correspondiente en el esquema WEAP.")

    return True # Todo está correcto, podemos proceder a procesar la geometría.