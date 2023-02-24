"""
function that converts TEO and CF inputs to the "input_dict" we were expecting
"""
# import json
# from datetime import datetime

from multiprocessing.sharedctypes import Value
import numpy as np
import pandas as pd
# import xlrd
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse
from datetime import timedelta


def convert_user_and_module_inputs(input_data):
    # input_data includes information from "user", "teo-module", "cf-module", and "gis-module"

    # Date related
    start_yr = min([int(input_data["teo-module"]["AccumulatedNewCapacity"][i]["YEAR"]) for i in range(len(input_data["teo-module"]["AccumulatedNewCapacity"]))])
    start_date = parse("01-01-" + str(start_yr))
    start_date_str = start_date.strftime('%d-%m-%Y')

    if input_data['user']['horizon_basis'] == 'weeks':
        end_date = start_date + relativedelta(weeks=input_data['user']["recurrence"])
    if input_data['user']['horizon_basis'] == 'months':
        end_date = start_date + relativedelta(months=input_data['user']["recurrence"])
    if input_data['user']['horizon_basis'] == 'years':
        #always sending just one year of hourly data
        end_date = start_date + relativedelta(years=input_data['user']["recurrence"])

    if input_data['user']['data_profile'] == 'hourly':
        diff = end_date - start_date  # difference
        diff = int(diff.total_seconds()/3600) #difference in hours

    if input_data['user']['data_profile'] == 'daily':
        diff = end_date - start_date  # difference
        # always sending just one year of hourly data
        diff = int(diff.total_seconds()/3600) #difference in hours

    nr_of_hours = diff
    print("nr of hours is " + str(nr_of_hours))

    # throw error if end_date or start_date is not in TEO YEAR.
    teo_years =list(set([int(input_data["teo-module"]["AccumulatedNewCapacity"][i]["YEAR"]) for i in range(len(input_data["teo-module"]["AccumulatedNewCapacity"]))]))
    nr_of_yrs_teo = len(teo_years)
    last_teo_yr = max(teo_years)

    if (end_date - relativedelta(hours=1)).year > last_teo_yr: 
        raise ValueError("There is not enough data from TEO for the selected horizon basis and recurrence in the Market Module simulation. \n" +
                         "You have " + str(nr_of_yrs_teo) + " years of data available from TEO. \n" + 
                         "Please select a lower recurrence or a smaller horizon basis in the Market Module so that your simulation is covered by input data from TEO.")

    # get CF data
    all_sinks_info = input_data["cf-module"]["all_sinks_info"]["sinks"]


    # convert CF inputs -----------------------------------------------------------------------------
    # get some sink info
    nr_of_sinks = len(all_sinks_info)

    sink_ids = []
    map_sink_streams = []

    for i in range(nr_of_sinks):
        sink_ids += [all_sinks_info[i]["sink_id"]]
        map_sink_streams += [[streams["demand_fuel"] for streams in all_sinks_info[i]["streams"]]]

    # get some stream x
    all_stream_ids = [y for x in map_sink_streams for y in x]

    # prep inputs
    lmax_sinks = np.zeros((diff, len(all_stream_ids)))
    for t in range(0, diff):
        count=0
        for sink in range(0, len(all_sinks_info)):
            for stream in range(0,len(all_sinks_info[sink]['streams'])):
                lmax_sinks[t,count] = all_sinks_info[sink]['streams'][stream]['hourly_stream_capacity'][t]
                count+=1

    utility_list = input_data['user']['util']
    util_sinks_t0 = np.zeros(len(all_stream_ids))
    for stream in range(0, len(all_stream_ids)):
        # get the nr of the sink that this stream is a part of
        stream_id_start = int(all_stream_ids[stream].split("str")[0].split("sink")[1])
        # assign that sink's utility to this stream
        util_sinks_t0[stream] = utility_list[sink_ids.index(stream_id_start)]
    
    util_sinks = np.tile(util_sinks_t0,(diff,1))

    if len(util_sinks_t0) != len(all_stream_ids):
        raise Exception('Utility does not match the sinks size')
    
    if np.min(util_sinks) < 0:
        raise Exception('Utility cannot be negative!')

    # get TEO data
    teo_output = input_data["teo-module"]

    #Convert TEO inputs
    production_by_technology_annual = teo_output.get("ProductionByTechnologyMM", teo_output["ProductionByTechnology"])
    ProductionByTechnologyAnnual = pd.DataFrame(production_by_technology_annual)
    VariableOMCost = pd.DataFrame(teo_output["VariableOMCost"])

    #Converting timeslice from str to int
    ProductionByTechnologyAnnual['TIMESLICE'] = ProductionByTechnologyAnnual['TIMESLICE'].astype('int')
    
    #Getting names and removing agents with 0 cost
    agent_names_all = ProductionByTechnologyAnnual.TECHNOLOGY.unique()
    
    list_agent_names = []
    for agent in agent_names_all:
        if VariableOMCost.loc[(VariableOMCost['TECHNOLOGY'] == agent)]["VALUE"].values[0] != 0.0:
            list_agent_names.append(agent)
    agent_names=np.array(list_agent_names)
    
    #Getting source names by removing sink names
    source_names = []
    for word in agent_names:
        if 'sink' not in word:
            source_names.append(word)
    #Removing dhn from source_names
    if 'dhn' in source_names:
        source_names.remove('dhn')

    nr_of_sources = len(source_names)

    dummy = {'TIMESLICE': range(1, nr_of_hours+1)}
    #Building gmax_sources
    gmax_sources = pd.DataFrame(dummy)
    gmax_sources.set_index('TIMESLICE', inplace=True)
    
    for source in source_names:
        gmax_sources[source] = ProductionByTechnologyAnnual[ProductionByTechnologyAnnual['TECHNOLOGY'] == source].sort_values(
                                                    by=['TIMESLICE']).filter(items=["VALUE"]).values[:nr_of_hours]

    gmax_sources.fillna(0, inplace=True)

    # Building cost_sources
    cost_sources = pd.DataFrame(dummy)
    cost_sources.set_index('TIMESLICE', inplace=True)
    for source in source_names:
        cost_sources[source] = VariableOMCost.loc[(VariableOMCost['TECHNOLOGY'] == source)]["VALUE"].values[0]
    
    cost_sources = cost_sources.to_numpy()

    if np.min(cost_sources) < 0:
        raise Exception('It is not possible to provide negative marginal cost coefficients to the market module. ')
    
    # Getting Annual CO2 Emissions
    co2_names = [] #Agents with co2 data
    for leng_nr in teo_output['AnnualTechnologyEmission']:
        co2_names.append(leng_nr['TECHNOLOGY'])
    # get total annual production of each source
    tot_production_year = pd.DataFrame(teo_output["ProductionByTechnologyMM"]).groupby("TECHNOLOGY").sum()
    tot_production_year = tot_production_year.reset_index(level=0)

    emissions_sources = []
    for source in source_names:
        # get total annual production for this specific source
        annual_prod = tot_production_year.loc[tot_production_year['TECHNOLOGY'] == source].VALUE.to_list()[0]
        if source in co2_names:
            for tech in teo_output['AnnualTechnologyEmission']:
                if tech['TECHNOLOGY'] == source:
                    # divide annual CO2 emissions by total annual production to get emission intensity per unit generated
                    emissions_sources.append(tech['VALUE'] / annual_prod)
        else:
            emissions_sources.append(0)

    # Get GIS data
    gis_output = input_data['gis-module']
    gis_data = {'from_to': [],
                'losses_total': [],
                'length': [],
                'total_costs': []}

    for link in gis_output['gis_data']['res_sources_sinks']:
        for source in source_names:
            if 'sou' in source:
                for sink in all_stream_ids:
                    if link['from_to'][1:-1].split(',')[0] == source.split('sou')[1].split('str')[0] and link['from_to'][1:-1].split(',')[1][1:] == sink.split('sink')[1].split('str')[0]:
                        gis_data['from_to'].append('(\'{}\',\'{}\')'.format(source,sink))
                        gis_data['losses_total'].append(link['losses_total'])
                        gis_data['length'].append(link['length'])
                        gis_data['total_costs'].append(link['total_costs'])

    # prep inputs
    lmax_sources = np.zeros((nr_of_hours, nr_of_sources))
    util_sources = np.zeros((nr_of_hours, nr_of_sources))
    gmax_sinks = np.zeros((nr_of_hours, len(all_stream_ids)))
    cost_sinks = np.zeros((nr_of_hours, len(all_stream_ids)))
    emissions_sinks = np.zeros(len(all_stream_ids))

    ## combine in input_dict as we used to have it
    # make input dict ------------------------
    # combine source and sink inputs
    agent_ids = source_names + all_stream_ids
    agent_ids_to_report = source_names + all_stream_ids
    gmax = np.concatenate((gmax_sources, gmax_sinks), axis=1).tolist()
    lmax = np.concatenate((lmax_sources, lmax_sinks), axis=1).tolist()
    cost = np.concatenate((cost_sources, cost_sinks), axis=1).tolist()
    util = np.concatenate((util_sources, util_sinks), axis=1).tolist()
    co2_emissions = np.concatenate((np.array(emissions_sources), emissions_sinks))


    # Checking if we have solver info. If not, set "GUROBI" as default.
    if not 'solver' in input_data['user']:
        Solver = "GUROBI"
    else:
        Solver = input_data['user']['solver']
        
    ## add storage inputs ---------------------------------------
    storage_data_TEO = teo_output["AccumulatedNewStorageCapacity"]

    # create a list stating for each timestep of the period what year it is.
    dates = []
    d = start_date
    while d < end_date:
        dates.append(d)
        d += timedelta(hours=1)
    year_ = [x.year for x in dates] # list of the year that each timestep is in


    # extract the needed storage data
    nr_of_storage = len(storage_data_TEO)
    print(nr_of_storage)
    print("nr_of_storage = " + str(nr_of_storage))
    storage_df = pd.DataFrame(storage_data_TEO)
    if nr_of_storage > 0:
        storage_df.YEAR = storage_df["YEAR"].astype(int)

        # check that all needed data is given by TEO, given by start date
        for year in set(year_):
            if not year in set(storage_df.YEAR):
                raise ValueError("The TEO data for storage capacity does not cover the selected simulation time for the Market Module. \n" +
                                "Check whether your selected start_datetime, horizon basis, and recurrence are such that all dates to be " +
                                "simulated by the Market Module are included in TEO output. ")

        # nr and names
        storage_names = list(set(storage_df.STORAGE))

        # capacity per year 
        storage_capacity_per_timestep = {}
        for storage_name in storage_names:
            print(storage_df.VALUE[(storage_df.STORAGE == storage_name) & (storage_df.YEAR == year_[0])].to_numpy())
            capacity_per_time = [storage_df.VALUE[(storage_df.STORAGE == storage_name) & (storage_df.YEAR == year_nr)].to_numpy().item() for year_nr in year_]
            storage_capacity_per_timestep[storage_name] = capacity_per_time
    
        stor_capacity_arr = np.array([storage_capacity_per_timestep[stor] for stor in storage_names]).T 
        if stor_capacity_arr.ndim == 1:
            stor_capacity_list = [stor_capacity_arr.tolist()]
        elif stor_capacity_arr.ndim == 2:
            stor_capacity_list = stor_capacity_arr.tolist()
        else:
            raise ValueError("stor_capacity_arr has wrong dimension, ndim = " + str(stor_capacity_arr.ndim) + " but should be 1 or 2")

    else:
        stor_capacity_list = []
        storage_names = []

    if not 'fbp_time' in input_data['user']:
        fbp_time = None
    else:
        fbp_time = input_data['user']["fbp_time"]
        if fbp_time == "None":
            fbp_time = None

    if not 'fbp_agent' in input_data['user']:
        fbp_agent = None
    else:
        fbp_agent = input_data['user']["fbp_agent"]
        if fbp_agent == "None":
            fbp_agent = None
    
            
    dict_acronyms = {
        "gridspecificngboiler" : " Grid Specific Natural Gas Boiler",
        "gridspecificoilboiler" : " Grid Specific Oil Boiler",
        "gridspecificbioboiler" : " Grid Specific Biomass Boiler",
        "gridspecifichp" : " Grid Specific Heat Pump",
        "gridspecificsthp" : " Grid Specific solar thermal with Heat Pump",
        "dhn" : " District Heating Network",
        "she" : " Single Heat Exchanger",
        "mhe" : " Multiple Heat Exchanger",
        "elwhrb" : " Electric Heat Recovery Boiler",
        "ngwhrb" : " Natural Gas Heat Recovery Boiler",
        "oilwhrb" : " Oil Heat Recovery Boiler",
        "biowhrb" : " Biomass Heat Recovery Boiler",
        "chpng" : " Natural Gas CHP",
        "chpoil" : " Oil CHP",
        "chpbio" : " Biomass CHP",
        "boosthp" : " Booster Heat Pump",
        "sthp" : " Solar thermal Heat Pump",
        "stngboiler" : " Solar thermal with Natural gas boiler",
        "stoilboiler" : " Solar thermal with oil boiler",
        "stbioboiler" : " Solar thermal with biomass boiler",
        "stelboiler" : " Solar thermal with el boiler",
        "ac" : " Absorption Chiller",
        "acec" : " Absorption Chiller with Electric Chiller",
        "acngboiler":  " Absorption Chiller with Natural gas boiler",
        "acoilboiler" : " Absorption Chiller with oil boiler",
        "acbioboiler" : " Absorption Chiller with biomass boiler",
        "acelectricboiler" : " Absorption Chiller with electric boiler"  ,
        "acecngboiler" : " Absorption Chiller and Electric Chiller with Natural gas boiler",
        "acecoilboiler" : " Absorption Chiller and Electric Chiller with oil boiler",
        "acecbioboiler" : " Absorption Chiller and Electric Chiller with biomass boiler",
        "acecelectricboiler" : " Absorption Chiller and Electric Chiller with electric boiler",
        "acechp" : " Absorption Chiller and Electric Chiller with heat pump",
        "achp" : " Absorption Chiller with heat pump",
        "orc" : " Organic Rankine Cycle",
        "exgrid" : " Existing Grid Technologies",
        "hp" : " Heat Pump"}

    #Changing agent_ids to common IDs
    for id in agent_ids_to_report:
        if 'sou' in id:
            for cf_id in range(0,len(input_data["cf-module"]["all_sources_info"])):
                if int(id.split('sou')[1].split('str')[0]) == input_data["cf-module"]["all_sources_info"][cf_id]['source_id']:
                    for abb in dict_acronyms.keys():
                        if abb in id:
                            agent_ids_to_report[agent_ids_to_report.index(id)] = input_data["cf-module"]["all_sources_info"][cf_id]['name'] + dict_acronyms[abb]

    #Does not update agent_ids, so a new cycle is required
    for id in agent_ids_to_report:
        if 'sou' in id:
            for cf_id in range(0, len(input_data["cf-module"]["all_sources_info"])):
                if int(id.split('sou')[1].split('str')[0]) == input_data["cf-module"]["all_sources_info"][cf_id][
                    'source_id']:
                    agent_ids_to_report[agent_ids_to_report.index(id)] = input_data["cf-module"]["all_sources_info"][cf_id]['name']

    #Sinks
    for sink in range(0, len(all_sinks_info)):
        for stream in range(0, len(all_sinks_info[sink]['streams'])):
            for conv_tec in range(0, len(all_sinks_info[sink]['streams'][stream]['conversion_technologies'])):
                for agent in agent_ids_to_report:
                    if all_sinks_info[sink]['streams'][stream]['conversion_technologies'][conv_tec]['output_fuel'] == agent:
                        agent_ids_to_report[agent_ids_to_report.index(agent)] = all_sinks_info[sink]['streams'][stream]['conversion_technologies'][conv_tec]['teo_equipment_name']


    for id in agent_ids_to_report:
        if 'sink' in id:
            for cf_id in range(0, len(all_sinks_info)):
                if int(id.split('sink')[1].split('str')[0]) == input_data["cf-module"]["all_sinks_info"]["sinks"][cf_id]['sink_id']:
                    for abb in dict_acronyms.keys():
                        if abb in id:
                            agent_ids_to_report[agent_ids_to_report.index(id)] = input_data["cf-module"]["all_sinks_info"]['sinks'][cf_id]['name'] + dict_acronyms[abb]

    #CHanging grids and dhn names
    for agent in agent_ids_to_report:
        if agent in dict_acronyms.keys():
            agent_ids_to_report[agent_ids_to_report.index(agent)] = dict_acronyms[agent]
                            
    # construct input_dict
    input_dict = {
        'md': input_data['user']['md'],
        'horizon_basis': input_data['user']["horizon_basis"],
        'data_profile': input_data['user']["data_profile"],
        'recurrence': input_data['user']["recurrence"],
        'yearly_demand_rate': input_data['user']["yearly_demand_rate"],
        'prod_diff_option': input_data['user']["prod_diff_option"],
        'agent_ids': agent_ids,
        'gmax': gmax,
        'lmax': lmax,
        'cost': cost,
        'util': util,
        'start_datetime': start_date_str,
        'co2_emissions': list(co2_emissions),  # allowed values are 'none' or list of size (nr_of_agents)
        'gis_data': gis_data,
        'nodes': None,
        'edges': None,
        'solver': Solver,
        'storage_name': storage_names, 
        'storage_capacity': stor_capacity_list,
        'fbp_time': fbp_time,
        'fbp_agent': fbp_agent,
        'agent_ids_to_report': agent_ids_to_report
    }
    return input_dict
