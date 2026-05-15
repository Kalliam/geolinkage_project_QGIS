# trasladadas para el main.py del plugin de QGIS
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

### desde featureProcessor
self.config.set_columns_to_save(feature_type=self.get_feature_type(),
                                columns_to_save=self.config.default_opts[self.get_feature_type()]['columns_to_save'])
self.config.set_order_criteria(feature_type=self.get_feature_type(),
                                order_criteria=self.config.default_opts[self.get_feature_type()]['order_criteria'])


## puede que se necesite despues
## Abría los mapas en GRASS: Usaba la clase VectorTopo(map_name) de la librería pygrass para abrir la conexión a la base de datos de cada mapa.
## Leía la tabla de atributos: Iteraba sobre cada geometría (for a in vector_map.viter('areas'):) y extraía el valor de la columna principal (por ejemplo, el nombre de la cuenca: "Cuenca_Maipo").
## Llenaba un diccionario global: Guardaba esa información en la variable self._features_by_map.
def set_feature_names_in_maps(self, imported: bool = True):
    map_names = self.map_names
    if imported:
        map_names = dict([(m, map_names[m]) for m in map_names if map_names[m]['imported']])

    for map_key in map_names:
        map_name = map_names[map_key]['name']

        vector_map = VectorTopo(map_name)
        vector_map.open('r')

        fields = self.get_needed_field_names(alias=self.get_feature_type())
        main_field, main_needed = fields['main']['name'], fields['main']['needed']

        for a in vector_map.viter('areas'):
            if a.cat is None or not a.attrs[main_field]:
                # print("[ERROR - {}] ".format(gws_name), a.cat, a.id)
                continue

            feature_name = a.attrs[main_field]

            if feature_name in self._features_by_map:
                self._features_by_map[feature_name].add(map_name)
            else:
                self._features_by_map[feature_name] = {map_name}

        vector_map.close()


## validador

    # @main_task
    def processing_nodes_arcs(self, arcmap, nodemap):
        _err = False

        # prepare node and arc column names
        node_column = NODE_COL
        arc_column = ARC_COL

        # prepare node and arc type ids
        node_type = NODE_TYPE_ID
        arc_type = ARC_TYPE_ID

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






## cosas que debiese hacer sola la interfaz al subir un archivos al plugin
class UtilMisc:
    """
    Miscellaneous utility class.
    """

    @staticmethod
    def get_origin_from_map(map_name: str):
        """Get the real world model coords for lower left edge in a vector map.
        :return (x,y) coords for lower left edge
        """
        v = VectorTopo(map_name)
        v.open('r')

        box = v.bbox()
        x_ll = box.west
        y_ll = box.south
        v.close()

        return x_ll, y_ll


    @staticmethod
    def get_similarity_rate(a_words, b_words, min_rate=0.9):
        seq = difflib.SequenceMatcher(None, a_words, b_words)
        d = seq.quick_ratio()  # seq.ratio()

        return d >= min_rate

    @staticmethod
    def check_paths_exist(files: list = None, folders: list = None):
        import os.path

        files = files if files else []
        folders = folders if folders else []

        # TODO: is it better to use os.path.exists?
        _result_files = []
        for file in files:
            if not os.path.isfile(file):
                msg_error = 'El archivo [{}] no existe.'.format(file)
                _result_files.append((False, msg_error))
            else:
                _result_files.append((True, None))

        _result_dirs = []
        for folder in folders:
            if not os.path.isdir(folder):
                msg_error = 'El directorio [{}] no existe.'.format(folder)
                _result_dirs.append((False, msg_error))
            else:
                _result_dirs.append((True, None))

        return _result_files, _result_dirs

    @staticmethod
    def print_catchment_map(cells, element_set):
        tokens = ['+', '-', '*', '#', '0', '°']

        max_row = max([cell.row for cell in cells])  # 88
        max_col = max([cell.col for cell in cells])  # 67

        catch_tokens = {}
        i = 0
        for c in element_set:
            if not str(c).isnumeric():
                catch_tokens[c] = tokens[i]
                i += 1

        basic_str = "".join([" " for i in range(max_col)])
        rows = {}
        for cell in cells:
            row = cell.row
            col = cell.col
            catchment = cell.catchment

            if row in rows:
                s = rows[row][:col] + catch_tokens[catchment] + rows[row][col + 1:]
            else:
                rows[row] = basic_str
                s = rows[row][:col] + catch_tokens[catchment] + rows[row][col + 1:]
            rows[row] = s

        for row in rows:
            print(rows[row])

    @staticmethod
    def generate_word(length: int = 5, prefix: str = 'mapset_'):
        _signs = "abcdefghijklmnopqrstuvwxyz1234567890"

        word = ""
        for i in range(length):
            word += random.choice(_signs)

        return prefix + word

    @staticmethod
    def show_title(msg_title, ch: str = '-', ch_len: int = 100, title_color=ui.green):
        count_str = ch_len - len(msg_title) if ch_len > len(msg_title) else 0
        print()
        print(ch * (ch_len + 2))
        ch = ' '
        ui.info_section(ui.bold, title_color, msg_title, ui.faint, ui.lightgray, ch * count_str)

    @staticmethod
    def get_map_name_standard(f_path: str):
        f_path = os.path.basename(f_path)
        f_path = f_path.replace('.', '_')
        f_path = f_path.replace(',', '_')
        f_path = f_path.replace('-', '_')
        name = os.path.splitext(f_path)[0][0:30].lower()

        first_letter_patter = '[a-zA-Z]'
        if re.match(first_letter_patter, name[0]):
            return name
        else:
            return 'm' + name

    @staticmethod
    def check_file_extension(file_path: str, ftype: str = 'shp'):
        file_name = os.path.splitext(file_path)[1].lower()
        if file_name.endswith('.{}'.format(ftype)):
            return True
        else:
            return False

    @staticmethod
    def get_file_names(folder_path, ftype: str = 'shp') -> list:
        from os import listdir
        from os.path import isfile, join

        files = [join(folder_path, f) for f in listdir(folder_path) if isfile(join(folder_path, f))]
        files = [f for f in files if f.endswith('.{}'.format(ftype))] if ftype else files

        return files

    @staticmethod
    def insert_ui(text: str, pattern: str = r"\[([A-Za-z0-9_/ .']+)\]", highlight_color=ui.red):
        effect_ini = [ui.bold, highlight_color]
        effect_fin = [ui.faint, ui.white]

        m = re.search(pattern, text)

        if m:
            subtext_ini = text[:m.start()].strip()
            subtext_inter = m.group(1).strip()
            subtext_fin = text[m.end():].strip()

            text_end = UtilMisc.insert_ui(subtext_fin, pattern)

            ret = [subtext_ini, *effect_ini, subtext_inter, *effect_fin, *text_end]
            return ret
        else:
            return [text]



    def get_break_input_by_river(self, river_node_id=None):
        if river_node_id:
            river_node = find_by_attr(self, name="node_id", value=river_node_id)
        else:
            river_node = self

        # river data
        river_node_id = river_node.node_id
        river_node_name = river_node.node_name
        river_node_cat = river_node.node_cat
        river_node_distance = river_node.node_distance

        children = river_node.get_order_children_by_distance()

        # inital condition
        segments = []
        node_before_name = river_node_name
        node_before_distance = 0
        last_child = river_node
        for i, child_node in enumerate(children):
            # (1) make segments from this child
            if not child_node.is_leaf:
                child_node.get_break_input_by_river()
            else:  # to keep the river segment if it has a secondary river
                if child_node.node_type == 13 and child_node.secondary_river_id:  # is a Tributary Inflow Node
                    break_name = "Below {} Headflow".format(child_node.secondary_river_name)
                    segment = {
                        'type': 'L',
                        'cat': child_node.secondary_river_cat,
                        'start_offset': '0',
                        'end_offset': '100%',
                        'break_name': break_name,
                        'river_name': child_node.secondary_river_name
                    }
                    segments.append(segment)

            # (2) make input from child to parent river
            child_name = child_node.node_name
            child_distance = child_node.node_distance  # distance from main river
            child_id = child_node.node_id  # id from WEAPNode map

            if i == 0:
                break_name = "Below {} Headflow".format(node_before_name)
            else:
                break_name = "Below {}".format(node_before_name)

            segment = {
                'type': 'L',
                'cat': river_node_cat,
                'start_offset': node_before_distance,
                'end_offset': child_distance,
                'break_name': break_name,
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
            child_id = last_child.node_id * 100  # unique ID using double 0's for final segment

            break_name = "Below {}".format(child_name)

            segment = {
                'type': 'L',
                'cat': river_node_cat,
                'start_offset': child_distance,
                'end_offset': '100%',
                'break_name': break_name,
                'river_name': river_node_name
            }
            segments.append(segment)

        river_node.river_segments = segments

        return segments

