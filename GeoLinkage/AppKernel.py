import time
import os
from collections import namedtuple
from qgis.core import QgsField, QgsVectorFileWriter
from qgis.PyQt.QtCore import QVariant

from .postprocessors.GeoChecker import GeoChecker
from .processors.CatchmentProcessor import CatchmentProcess
from .processors.DemandSiteProcessor import DemandSiteProcess
from .processors.GroundwaterProcessor import GroundwaterProcess
from .postprocessors.SuperpositionCheck import SuperpositionCheck
from .processors.RiverProcessor import RiverProcess
from  .utils.Visualizer import *
from .utils.UtilMisc import *
from .settings import *
from .settings import COLUMNS_FOR_SHP_EXPORT
from .utils.UtilMisc import UtilMisc




class AppKernel():
    """
    AppKernel class is the main processor manager for the GeoLinkage plugin.
    It orchestrates the spatial intersections between the MODFLOW grid and the WEAP elements
    (catchments, groundwater, demand sites, and rivers) using individual processors.

    Attributes:
    ----------
    debug : bool
        Flag to enable debug mode (default is False).
    catchment_processor : CatchmentProcess
        Processor instance for catchment features.
    groundwater_processor : GroundwaterProcess
        Processor instance for groundwater features.
    river_processor : RiverProcess
        Processor instance for river features.
    demand_site_processor : DemandSiteProcess
        Processor instance for demand site features.
    stats : dict
        Dictionary used to store general processing statistics.
    visualizer : Visualizer
        Instance responsible for outputting visualization data and paths.

    Methods:
    --------
    run_geo_checker(output_path, layers_dict):
        Initializes and runs the GeoChecker module for the generated linkage data.
        
    consolidate_grid_attributes(grid_layer, layers_dict):
        Consolidates the processed data from all WEAP element processors and writes the
        corresponding attributes directly into the grid layer.
        
    run(grid_layer, layers_dict, output_path, run_geochecker=False):
        Main execution routine. Runs each spatial processor as requested, consolidates the
        results into the final shapefile, exports it, and optionally runs GeoChecker.
    """

    def __init__(self, debug: bool = False):
        self.debug = debug

        self.catchment_processor = CatchmentProcess(debug=self.debug)
        self.groundwater_processor = GroundwaterProcess(debug=self.debug)
        self.river_processor = RiverProcess(debug=self.debug)
        self.demand_site_processor = DemandSiteProcess(debug=self.debug)
        self.stats = {}
        self.visualizer = Visualizer()

        
    def run_geo_checker(self, output_path: str, layers_dict: dict):
        geochecker_out = os.path.join(output_path, "geochecker_results")
        os.makedirs(geochecker_out, exist_ok=True)
        linkage_path = os.path.join(output_path, "linkage_final.shp")
        
        # .source() returns the path of the .shp file on the disk
        arc_path = layers_dict['river']['river_layer'].source()
        node_path = layers_dict['river']['node_layer'].source()

        cells, arcs, nodes = UtilMisc.structure_creation(
            linkage_map=linkage_path,
            arc_map=arc_path,
            node_map=node_path,
            catch_name='CATCH',
            gw_name='GW',
            ds_prefix='DS'
        )

        geo_checker = GeoChecker(checks=[
            SuperpositionCheck(base_feature='groundwater', secondary_feature='catchment'),
            SuperpositionCheck(base_feature='groundwater', secondary_feature='demand_site')
        ], folder_path=geochecker_out)

        geo_checker.setup(cells, arcs, nodes)
        geo_checker.run()

    def consolidate_grid_attributes(self, grid_layer, layers_dict):
        # Extract layer names (defensive)
        gw_layer_obj = layers_dict.get('gw', {}).get('gw_layer')
        gw_map_name = gw_layer_obj.name() if gw_layer_obj else None

        cat_layer_obj = layers_dict.get('catchment', {}).get('catchment_layer')
        catchment_map_name = cat_layer_obj.name() if cat_layer_obj else None

        river_layer_obj = layers_dict.get('river', {}).get('river_layer')
        river_map_name = river_layer_obj.name() if river_layer_obj else None

        # For demand sites: collect the actual names of the layers that were processed
        ds_map_names = []
        if 'ds' in layers_dict:
            node_layer = layers_dict.get('river', {}).get('node_layer')
            if node_layer:
                ds_map_names.append(node_layer.name())
            for area_layer in layers_dict.get('ds', {}).get('demand_site_layers', []):
                ds_map_names.append(area_layer.name())

        # column structure required by WEAP/MODFLOW, ensure that the columns exist in the grid layer
        export_columns = COLUMNS_FOR_SHP_EXPORT
        provider = grid_layer.dataProvider()
        current_fields = [field.name() for field in grid_layer.fields()]
        new_fields = []

        for column_group in export_columns.values():
            for column_name in column_group:
                if column_name not in current_fields:
                    new_fields.append(QgsField(column_name, QVariant.String, len=50))
        
        if new_fields:
            provider.addAttributes(new_fields)
            grid_layer.updateFields()

        # Prepare update batch
        update_batch = {}
        
        # Get column indices/names
        column_indices = {field.name(): grid_layer.fields().indexOf(field.name()) for field in grid_layer.fields()}
        col_row = layers_dict['grid']['col_row']
        col_col = layers_dict['grid']['col_col']

        # Define the Cell outside the loop
        Cell = namedtuple('Cell', ['row', 'col'])

        # Iterate over grid and collect winning data (the ones that cover the most area over the cell)
        for feature in grid_layer.getFeatures():
            fid = feature.id()
            current_cell = Cell(feature[col_row], feature[col_col])
            cell_attributes = {}

            # -------------------------------------------------------------------------
            # FAIL-SAFE EXTRACTION
            # -------------------------------------------------------------------------
            
            # Groundwater
            if self.groundwater_processor:
                gw_cell = self.groundwater_processor.cell_ids.get(current_cell)
                if gw_cell and gw_cell.get('data'):
                    cell_attributes[export_columns['gw'][0]] = str(gw_cell['data'][0].get('name', ''))

            # Catchment
            if self.catchment_processor:
                cat_cell = self.catchment_processor.cell_ids.get(current_cell)
                if cat_cell and cat_cell.get('data'):
                    cell_attributes[export_columns['catchment'][0]] = str(cat_cell['data'][0].get('name', ''))

            # Rivers
            if self.river_processor:
                riv_cell = self.river_processor.cell_ids.get(current_cell)
                if riv_cell and riv_cell.get('data'):
                    cell_attributes[export_columns['river'][0]] = str(riv_cell['data'][0].get('name', ''))

            # Demand Sites (Supports multiple wells per cell)
            if self.demand_site_processor:
                ds_cell = self.demand_site_processor.cell_ids.get(current_cell)
                if ds_cell and ds_cell.get('data'):
                    for i, record in enumerate(ds_cell['data']):
                        if i < len(export_columns['ds']):
                            target_col = export_columns['ds'][i]
                            cell_attributes[target_col] = str(record.get('name', ''))

            # Map column names to numerical indices for PyQGIS
            changes_for_this_cell = {}
            for col_name, value in cell_attributes.items():
                if col_name in column_indices:
                    idx = column_indices[col_name]
                    changes_for_this_cell[idx] = value
            
            # Save changes for this cell in the master update batch
            if changes_for_this_cell:
                update_batch[fid] = changes_for_this_cell

        # startEditing() and commitChanges() handle safe transactions in QGIS
        grid_layer.startEditing()
        provider.changeAttributeValues(update_batch)
        grid_layer.commitChanges()        



    def run(self, grid_layer, layers_dict, output_path, run_geochecker: bool = False):
        ts = time.time()
        t_start = time.perf_counter()
        # 1. Start background monitor
        monitor = MonitorRAMOS()
        monitor_thread = threading.Thread(target=monitor.track)
        monitor_thread.start()

        t_start = time.perf_counter()
        # -------------------------------------------------------------------------------
        # Catchments Logic
        # -------------------------------------------------------------------------------
        if 'catchment' in layers_dict:
            self.catchment_processor.run(grid_layer, **layers_dict['catchment'], **layers_dict['grid'])

        # -------------------------------------------------------------------------------
        # GWS Logic
        # -------------------------------------------------------------------------------
        if 'gw' in layers_dict:
            self.groundwater_processor.run(grid_layer, **layers_dict['gw'], **layers_dict['grid'])

        # -------------------------------------------------------------------------------
        # Demand Sites Logic
        # -------------------------------------------------------------------------------
        if 'ds' in layers_dict:
            node_layer = layers_dict.get('river', {}).get('node_layer')
            col_node_name = layers_dict.get('river', {}).get('col_node_name')

            self.demand_site_processor.run(
                grid_layer=grid_layer,
                well_layer=node_layer,
                area_layers_list=layers_dict['ds']['demand_site_layers'],
                wells_txt_path=layers_dict['ds']['wells_file_path'],
                col_name=layers_dict['ds']['col_name'],
                col_well_name=col_node_name, 
                **layers_dict['grid']
            )

        # -------------------------------------------------------------------------------
        # Rivers Logic
        # -------------------------------------------------------------------------------
        if 'river' in layers_dict:
            self.river_processor.run(grid_layer, **layers_dict['river'], **layers_dict['grid'])

        # -------------------------------------------------------------------------------
        # General and Results Logic
        # -------------------------------------------------------------------------------
        # make a linkage map copy and format with the base linkage cols

        self.consolidate_grid_attributes(grid_layer, layers_dict)

        # DISK EXPORT         
        output_file = os.path.join(output_path, "linkage_final.shp").replace("\\", "/") #avoid parsing errors
        
        # vector writing engine
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "ESRI Shapefile"
        options.fileEncoding = "UTF-8"
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
        
        # Execute clone to disk 
        write_result = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer=grid_layer,
            fileName=output_file,
            transformContext=grid_layer.transformContext(),
            options=options
        )
        
        error_code = write_result[0]
        message = write_result[1]
        
        if error_code != QgsVectorFileWriter.NoError:
            raise IOError(f"Critical I/O error. Could not save the final file to the output path: {message}")

        # GEOCHECKER        
        if run_geochecker:
            monitor2 = MonitorRAMOS()
            monitor_thread2 = threading.Thread(target=monitor2.track)
            monitor_thread2.start()

            t_start_geochecker = time.perf_counter()
            self.output_path = output_path
            self.run_geo_checker(output_path, layers_dict)
            t_end_geochecker = time.perf_counter()
            elapsed_time_geochecker = t_end_geochecker - t_start_geochecker
            peak_mb_geochecker = monitor2.peak_bytes / (1024 * 1024)
            monitor2.active = False
            monitor_thread2.join()

            print(f"[Profiling] GeoChecker executed in: {elapsed_time_geochecker:.4f} seconds | Peak RAM: {peak_mb_geochecker:.2f} MB")
            
        t_end = time.perf_counter()
            
        monitor.active = False
        monitor_thread.join()

        total_time = t_end - t_start
        peak_mb = monitor.peak_bytes / (1024 * 1024)

        print(f"[Profiling OS] Time: {total_time:.4f} sec | Peak RAM: {peak_mb:.2f} MB")
        te = time.time()
        self.stats['TOTAL_TIME'] = f"{te - ts:.2f} sec"
        print(f"DEBUG OUTPUT: {self.stats['TOTAL_TIME']}")

        t_end = time.perf_counter()
        elapsed_time = t_end - t_start
        print(f"[Profiling] Processor executed in: {elapsed_time:.4f} seconds")

        self.visualizer.set_result_path(output_path)
