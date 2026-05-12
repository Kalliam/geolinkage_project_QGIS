import difflib
import os
import random
import re
from subprocess import PIPE
import sqlite3
import ui
from functools import wraps
import time

from grass.pygrass.modules import Module
from grass.pygrass.vector import Vector, VectorTopo
from grass.pygrass.vector.table import Columns
from grass.pygrass.utils import copy, rename, remove

from utils.Config import ConfigApp
from utils.RiverNode import RiverNode


class Utils:
    """
    Utility class that is responsible for establishing a connection with GRASS Platform.
    Use the 'Module' API class (grass.pygrass.modules.Module) to connect with the GRASS tools.

    * Config File: ./config/config.json


    Methods:
    --------
    set_verbosity(cls)
        Set class varibles 'cls.quiet' and 'cls.verbose' using GRASS method grass.script.verbosity().

    inter_map_with_linkage(cls, linkage_name, snap, verbose, quiet)
        Using a GRASS tool (v.overlay) intersect the vector map with groundwater grid vector map.
        The 'linkage_name' parameter identifies final groundwater grid and the 'snap' parameter allows to make
        the intersection more detailed (but slower).

    export_to_shapefile(cls, map_name, output_path, file_name: str = 'linkage.shp', verbose, quiet)
        Export an vector map as shapefile to a defined path. The 'map_name' parameter is the map name, and the path is
        defined by 'output_path' folder and 'file_name' parameters. The GRASS tool (v.out.ogr) is used to export the map.

    import_vector_map(cls, map_path, output_name, verbose, quiet)
        Using a GRASS tool (v.in.ogr) import an vector map in 'map_path' with the name defined by 'outer_name'.
        The input format is ESRI Shapefile (.shp).

    check_basic_columns(cls, map_name, columns, needed)
        Check if 'columns' list are into metadata map 'map_name'. The list parameter 'needed' is used to set error
        or warning message.

    create_table_attributes(cls, vector_map_name, columns_str, layer, verbose, quiet)
        Build metadata table for vector map 'vector_map_name' using 'columns_str' columns configuration. By default
        the parameter 'layer' is set to 1. The table will be created by (v.db.addtable) GRASS tool.

    extract_map_with_condition(cls, map_name, output_name, col_query, val_query,  op_query, geo_check, verbose, quiet)
        Extract a subset of the geometries from the map 'map_name' to store as 'output_name' vector map name.
        The 'col_query' parameter specifies the column to query. 'op_query' parameter specifies the operator to
        use (=, <, >). The 'val_query' parameter specifies value to filter. Finally, 'geo_check' parameter sets
        the type of geometry to filter ('point', 'line', 'area', ...). The (v.extract) GRASS tool is used.

    make_buffer_in_point(cls, map_pts_name, out_name, map_type, distance, verbose, quiet)
        Using a GRASS tool (v.buffer) builds an area at each 'map_type' geometry on the 'map_pts_name' map.
        'distance' parameter is used to set the width in meters. Final vector map is be stored as 'out_name'.

    make_segments(cls, root: RiverNode, arc_map_name, output_map, verbose, quiet)
        Build line segments from the river types in 'arc_map_name' map using RiverNode tree parser object 'root'.
        Segments are formatted for (v.segment) GRASS Tool. Final vector map is be stored as 'output_map' name.


    TODO:
    ----
        - Catch errors in all Module functions.
        - Group Module methods an one Module method and configuration methods (input/output/flags).
        - Currently, map metadata connection only with SQLite.

    """

    quiet = None
    verbose = None

    _debug_lines = []

    @classmethod
    def __set_verbosity(cls):
        from grass.script import core as gc

        verbosity = gc.verbosity()
        if verbosity == 0:
            cls.quiet = True
            cls.verbose = False
        elif verbosity <= 2:
            cls.quiet = False
            cls.verbose = False
        else:  # gc.verbosity() == 3:
            cls.quiet = False
            cls.verbose = True

        return verbosity

    @classmethod
    def get_debug_lines(cls):
        return cls._debug_lines

    @classmethod
    def inter_map_with_linkage(cls, map_name, linkage_name, output_name, snap='1e-12', verbose: bool = False,
                               quiet: bool = True):
        _err, _errors = False, []  # TODO: catch errors

        cls.__set_verbosity()
        verbose = cls.verbose if cls.verbose is not None else verbose
        quiet = cls.quiet if cls.quiet is not None else quiet

        # get a copy from map
        map_copy_name = map_name + '_copy'
        copy(map_name, map_copy_name, 'vect', overwrite=True)

        vector_map = Vector(map_copy_name)
        if vector_map.exist():
            # intersect vector maps
            overlay = Module('v.overlay', run_=False, stdout_=PIPE, stderr_=PIPE, overwrite=True)
            overlay.flags.c = True

            overlay.inputs.ainput = map_copy_name
            # overlay.inputs.atype = 'area'
            overlay.inputs.binput = linkage_name
            # overlay.inputs.btype = 'area'

            overlay.inputs.operator = 'and'
            overlay.inputs.snap = snap
            overlay.outputs.output = output_name

            debug_line = overlay.get_bash()
            GrassCoreAPI._debug_lines.append(debug_line)

            overlay.run()
            # print(overlay.outputs["stdout"].value)
            # print(overlay.outputs["stderr"].value)

            vector_map = Vector(output_name)
            if not vector_map.exist():
                msg_error = 'El mapa [{}] presenta errores o no pudo ser creado por funcion [{}].'.format(overlay,
                                                                                                          'v.overlay')
                _errors.append(msg_error)
                _err = True
        else:
            msg_error = 'El mapa [{}] no pudo ser creado por funcion [{}].'.format(map_copy_name, 'v.copy')
            _errors.append(msg_error)
            _err = True

        return _err, _errors

    @classmethod
    def export_to_shapefile(cls, map_name, output_path, file_name: str = 'linkage.shp', verbose: bool = False,
                            quiet: bool = True):
        err, errors = False, []

        cls.__set_verbosity()
        verbose = cls.verbose if cls.verbose is not None else verbose
        quiet = cls.quiet if cls.quiet is not None else quiet

        # import vector map in [map_path]
        out_ogr = Module('v.out.ogr', run_=False, stdout_=PIPE, stderr_=PIPE, overwrite=True)

        out_ogr.inputs.input = map_name
        out_ogr.inputs.type = ['auto']
        out_ogr.inputs.format = 'ESRI_Shapefile'

        out_ogr.outputs.output = '{}/{}'.format(output_path, file_name)
        out_ogr.flags.e = True

        debug_line = out_ogr.get_bash()
        GrassCoreAPI._debug_lines.append(debug_line)

        out_ogr.run()
        # print(out_ogr.outputs["stdout"].value)

        return err, errors

    @classmethod
    def import_vector_map(cls, map_path: str, output_name: str, verbose: bool = False, quiet: bool = True):
        cls.__set_verbosity()
        err = False
        errors = []

        verbose = cls.verbose if cls.verbose is not None else verbose
        quiet = cls.quiet if cls.quiet is not None else quiet

        # import vector map in [map_path]
        in_ogr = Module('v.in.ogr', run_=False, stdout_=PIPE, stderr_=PIPE, overwrite=True)

        in_ogr.inputs.input = map_path
        in_ogr.outputs.output = output_name + '_tmp'
        in_ogr.flags.o = True

        debug_line = in_ogr.get_bash()
        GrassCoreAPI._debug_lines.append(debug_line)

        in_ogr.run()
        # print(in_ogr.outputs["stdout"].value)

        # check if import works
        vector_map = Vector(output_name + '_tmp')
        if vector_map.exist():
            cls.do_clean(map_name=output_name + '_tmp', map_new_name=output_name, tool=['rmarea', 'rmline', 'rmdac'],
                     threshold=['1', '0', '0'])
        else:
            err = True
            msg_error = 'El mapa [{}] en path=[{}] no pudo ser importado'.format(output_name, map_path)
            errors.append(msg_error)

        return err, errors

    @classmethod
    def do_clean(cls, map_name=None, map_new_name=None, tool=('rmarea', 'rmline', 'rmdac'), threshold=('1', '0', '0'),
                 verbose: bool = False, quiet: bool = True):
        cls.__set_verbosity()
        verbose = cls.verbose if cls.verbose is not None else verbose
        quiet = cls.quiet if cls.quiet is not None else quiet

        vclean = Module('v.clean', run_=False, stdout_=PIPE, stderr_=PIPE, overwrite=True)

        vclean.inputs.input = map_name
        vclean.outputs.output = map_new_name

        vclean.inputs.tool = tool
        vclean.inputs.threshold = threshold

        debug_line = vclean.get_bash()
        GrassCoreAPI._debug_lines.append(debug_line)

        vclean.run()
        # print(vclean.outputs["stdout"].value)

        return map_new_name

    @classmethod
    def get_values_from_map_db(cls, vector_map, data_values: dict):
        db_path = vector_map.dblinks[0].database

        cols_sqlite = Columns(vector_map.name, sqlite3.connect(db_path))
        cols_in = cols_sqlite.items()
        col_key = cols_sqlite.key

        col_values = []
        col_keys = []
        for col in [c for c in cols_in if c[0] != col_key]:
            key_column, key_type = col

            col_values.append(data_values[key_column] if key_column in data_values else '')
            col_keys.append(key_column)

        # if __debug:
        #     print('VALUES to DB: ================================================================')
        #     print ('\n'.join(['   [{}] = {}'.format(c, v) for c, v in zip(col_keys, col_values)]))
        #     print('VALUES to DB: ----------------------------------------------------------------')

        return col_keys, col_values

    @classmethod
    ## lo mejor seria usar las clases de qgis.core para no depender de pygrass
    ## toda esta funcion es un check de un vector map, no se usaria en QGIS
    def check_basic_columns(cls, vector_layer, columns: list, needed: list):
        _err, _errors = False, []
        nombres_columnas = [field.name() for field in vector_layer.fields()]
        for ind, c_check in enumerate(columns):
            if c_check not in nombres_columnas and needed[ind]:
                _err = True
                msg_error = 'El mapa [{}] no tiene la columna necesaria: [{}].'.format(vector_layer, c_check)
                _errors.append(msg_error)
            elif c_check not in nombres_columnas and not needed[ind]:
                _err = True
                msg_warn = 'El mapa [{}] no tiene la columna [{}] (se ingorará su valor durante el proceso)'.format(vector_layer, c_check)
                _errors.append(msg_warn)
        return _err, _errors

    @classmethod
    def create_table_attributes(cls, vector_map_name, columns_str, layer=1, verbose: bool = False, quiet: bool = True):
        cls.__set_verbosity()
        verbose = cls.verbose if cls.verbose is not None else verbose
        quiet = cls.quiet if cls.quiet is not None else quiet

        # add columns to vector map
        addtable = Module('v.db.addtable', run_=False, stdout_=PIPE, stderr_=PIPE)
        addtable.inputs.map = vector_map_name
        addtable.inputs.table = vector_map_name
        addtable.inputs.layer = layer
        # addtable.inputs.key = key
        addtable.inputs.columns = columns_str

        debug_line = addtable.get_bash()
        GrassCoreAPI._debug_lines.append(debug_line)

        addtable.run()
        # print(addtable.outputs["stdout"].value)
        # print(addtable.outputs["stderr"].value)

        # for security, rebuild topology
        vbuild = Module('v.build', run_=False, stdout_=PIPE, stderr_=PIPE, overwrite=True)
        vbuild.inputs.map = vector_map_name
        vbuild.inputs.option = 'build'

        debug_line = vbuild.get_bash()
        GrassCoreAPI._debug_lines.append(debug_line)

        vbuild.run()
        # print(vbuild.outputs["stdout"].value)
        # print(vbuild.outputs["stderr"].value)

    @classmethod
    def extract_map_with_condition(cls, map_name, output_name, col_query: str, val_query: str, op_query: str = '=',
                                   geo_check: str = 'point', verbose: bool = False, quiet: bool = True):
        _err, _errors = False, []

        cls.__set_verbosity()
        verbose = cls.verbose if cls.verbose is not None else verbose
        quiet = cls.quiet if cls.quiet is not None else quiet

        verbose = cls.verbose if cls.verbose is not None else verbose
        quiet = cls.quiet if cls.quiet is not None else quiet

        extract = Module('v.extract', run_=False, stdout_=PIPE, stderr_=PIPE, overwrite=True)
        extract.inputs.input = map_name
        extract.outputs.output = output_name

        extract.inputs.where = "{}{}\'{}\'".format(col_query, op_query, val_query)
        extract.inputs.type = ['point', 'line', 'boundary', 'centroid', 'area']

        debug_line = extract.get_bash()
        GrassCoreAPI._debug_lines.append(debug_line)

        extract.run()

        # check if it was created
        vector_map = VectorTopo(output_name)
        vector_map.open('rw')
        if not vector_map.exist() or vector_map.num_primitive_of(geo_check) == 0:  # extract works
            _err = True
            msg_warn = 'No se ha podido extraer del mapa [{}] con la condicion: [{} {} {}]'.format(map_name, col_query,
                                                                                                   op_query, val_query)
            _errors.append(msg_warn)
        vector_map.close()

        return _err, _errors

    @classmethod
    def make_buffer_in_point(cls, map_pts_name, out_name, map_type='point', distance=1000, verbose: bool = False,
                             quiet: bool = True):
        _err, _errors = False, []

        cls.__set_verbosity()
        verbose = cls.verbose if cls.verbose is not None else verbose
        quiet = cls.quiet if cls.quiet is not None else quiet

        buffer = Module('v.buffer', run_=False, stdout_=PIPE, stderr_=PIPE, overwrite=True)

        buffer.inputs.input = map_pts_name
        buffer.inputs.type = map_type
        buffer.inputs.distance = distance

        buffer.outputs.output = out_name

        buffer.flags.t = True
        buffer.flags.s = True

        debug_line = buffer.get_bash()
        GrassCoreAPI._debug_lines.append(debug_line)

        buffer.run()
        print(buffer.outputs["stdout"].value)

        return _err, _errors

    @classmethod
    def make_segments(cls, root: RiverNode, arc_map_name='arcs', output_map='arc_segments', verbose: bool = False, quiet: bool = True):
        _err, _errors = False, []  # TODO: catch errors

        cls.__set_verbosity()
        verbose = cls.verbose if cls.verbose is not None else verbose
        quiet = cls.quiet if cls.quiet is not None else quiet

        root_node = root
        arc_map_copy_name = arc_map_name + '_copy'
        rivers_map_name = 'arc_rivers'

        # (1) get only rivers
        # copy to new map to work
        copy(arc_map_name, arc_map_copy_name, 'vect', overwrite=True)  # get a copy from map
        GrassCoreAPI._debug_lines.append('copy {} {}'.format(arc_map_name, arc_map_copy_name))

        # extract only [TypeID]=6 in WEAPArc map
        #extract = Module('v.extract', run_=False, stdout_=PIPE, stderr_=PIPE, overwrite=True, quiet=quiet, verbose=verbose)
        extract = Module('v.extract', run_=False, stdout_=PIPE, stderr_=PIPE, overwrite=True)
        extract.inputs.input = arc_map_copy_name
        extract.outputs.output = rivers_map_name

        conf_tmp = ConfigApp()
        arc_type_id = conf_tmp.arc_columns['type_id']
        arc_river_code = conf_tmp.arc_type_id['river']
        extract.inputs.where = "{}={}".format(arc_type_id, arc_river_code)  # "TypeID=6"
        extract.inputs.type = 'line'

        debug_line = extract.get_bash()
        GrassCoreAPI._debug_lines.append(debug_line)

        extract.run()
        # print(extract.outputs["stdout"].value)
        # print(extract.outputs["stderr"].value)

        # (2) apply river tree to divide them in segments
        segments_str = root_node.get_segments_format()

        #vsegment = Module('v.segment', run_=False, stdout_=PIPE, stderr_=PIPE, overwrite=True, verbose=verbose, quiet=quiet)
        vsegment = Module('v.segment', run_=False, stdout_=PIPE, stderr_=PIPE, overwrite=True)
        vsegment.inputs.input = rivers_map_name
        vsegment.outputs.output = output_map

        if segments_str:
            vsegment.inputs.stdin = segments_str

        debug_line = vsegment.get_bash()
        GrassCoreAPI._debug_lines.append(debug_line)

        vsegment.run()

        return _err, _errors

    @classmethod
    def set_origin_in_map(cls, map_name: str, map_name_out: str, x_offset_ll: float, y_offset_ll: float,
                          z_rotation: float, verbose: bool = False, quiet: bool = True):
        """Set lower left edge in vector map. """

        _err, _errors = False, []  # TODO: catch errors

        cls.__set_verbosity()
        verbose = cls.verbose if cls.verbose is not None else verbose
        quiet = cls.quiet if cls.quiet is not None else quiet

        vtransform = Module('v.transform', run_=False, stdout_=PIPE, stderr_=PIPE, overwrite=True)

        vtransform.inputs.input = map_name
        vtransform.outputs.output = map_name_out
        vtransform.inputs.xshift = x_offset_ll
        vtransform.inputs.yshift = y_offset_ll
        vtransform.inputs.zrotation = z_rotation

        debug_line = vtransform.get_bash()
        GrassCoreAPI._debug_lines.append(debug_line)

        vtransform.run()

        return _err, _errors


class TimerSummary:
    """
    Utility class to be used in measuring times.
    """
    config_summary = {
        'CatchmentProcess.run': {
            'scope': 'catchment',
        },
        'GroundwaterProcess.run': {
            'scope': 'gw',
        },
        'DemandSiteProcess.run': {
            'scope': 'ds',
        },
        'RiverProcess.run': {
            'scope': 'river',
        },
    }
    time_functions = {}

    @staticmethod
    def get_scopes():
        scopes = set(['general'])
        for time_key in TimerSummary.config_summary:
            scopes.add(TimerSummary.config_summary[time_key]['scope'])

        return scopes

    @staticmethod
    def timeit(method):

        @wraps(method)
        def timed(*args, **kw):
            ts = time.time()
            result = method(*args, **kw)
            te = time.time()

            f_name = method.__qualname__

            if f_name in TimerSummary.config_summary:
                f_scope = TimerSummary.config_summary[f_name]['scope']
            else:
                f_scope = 'general'

            TimerSummary.time_functions[f_name] = {
                'scope': f_scope,
                'ms': (te - ts) * 1000
            }

            return result

        return timed

    @staticmethod
    def get_summary_time(f_scope: str = 'all'):
        ms_total_time = 0

        if f_scope == 'all':
            scopes = TimerSummary.get_scopes()
            for scope in scopes:
                ms_total_time += TimerSummary.get_summary_time(f_scope=scope)
        else:
            for method in TimerSummary.time_functions:
                scope = TimerSummary.time_functions[method]['scope']
                if f_scope == scope:
                    ms_total_time += TimerSummary.time_functions[method]['ms']

        return ms_total_time

    @staticmethod
    def get_summary_by_scope(f_scope: str = 'all'):
        summary = []
        # headers = ["function", "ms"]

        if f_scope == 'all':
            total_time_ms = 0
            scopes = TimerSummary.get_scopes()
            for scope in scopes:
                # TODO: watch if the total times were in order to calculate the total over totals
                _summary = TimerSummary.get_summary_by_scope(f_scope=scope)
                summary.append(_summary)
        else:
            for method in TimerSummary.time_functions:
                scope = TimerSummary.time_functions[method]['scope']
                ms = TimerSummary.time_functions[method]['ms']
                if f_scope == scope:
                    summary.append([(ui.bold, method), (ui.green, ms)])

            total_ms = TimerSummary.get_summary_time(f_scope = f_scope)
            summary.append([(ui.bold, 'Total: ' + f_scope), (ui.red, total_ms)])

        return summary

    @staticmethod
    def get_summary_by_function():
        summary = []
        total_time_ms = 0
        for method in TimerSummary.time_functions:
            scope = TimerSummary.time_functions[method]['scope']
            ms = TimerSummary.time_functions[method]['ms']

            total_time_ms += ms
            summary.append([(ui.bold, method), (ui.green, ms)])
        summary.append([(ui.bold, 'Total'), (ui.red, total_time_ms)])

        return summary


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

