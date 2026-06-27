#WEAP IDs (used on postprocessors)
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

# Output Shapefile final columns
COLUMNS_FOR_SHP_EXPORT = {
    'gw': ['GW'],
    'catchment': ['CATCH'],
    'river': ['RIVER'],
    'ds': ['DS1', 'DS2', 'DS3', 'DS4']
}