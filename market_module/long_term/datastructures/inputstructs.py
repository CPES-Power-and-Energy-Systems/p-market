# inputs format for market module
# if we receive them differently from other modules, we will convert them to these

import pandas as pd
import numpy as np
import heapq
from typing import List, Any, Union
from pydantic import BaseModel, validator, conint, conlist, Field, constr
import datetime
from datetime import datetime
from dateutil.relativedelta import relativedelta


# general settings object ---------------------------------------------------------------------------------------------
class MarketSettings(BaseModel):
    """
    Object to store market settings.
    On creation, it checks whether settings are valid
    """

    class Config:
        arbitrary_types_allowed = True

    product_diff: str = "noPref" # product differentiation. Only has an effect if market design = p2p
    market_design: str  # market design
    horizon_basis: str # horizon basis
    recurrence: conint(strict=True) # Recurrence
    ydr: float = 0.05 #yearly demand rate - 0.05 is the default value
    data_profile: str #data profile
    start_datetime: Any
    # to be filled by init
    day_range: Any
    data_size: Any
    diff: Any
    solver: str



    def __init__(self, **data) -> None:
        """
        create MarketSettings object if all inputs are correct
        """
        # pydantic __init__ syntax
        super().__init__(**data)

        if self.horizon_basis == 'weeks':
            self.day_range = 7
        if self.horizon_basis == 'months':
            self.day_range = 30
        if self.horizon_basis == 'years':
            self.day_range = 365
        # converting data profile to scalar
        if self.data_profile == 'hourly':
            self.data_size = 24
        if self.data_profile == 'daily':
            self.data_size = 1

        #Date related
        date_format = '%d-%m-%Y'
        start_date = datetime.strptime(self.start_datetime, date_format)
        if self.horizon_basis == 'weeks':
            end_date = start_date + relativedelta(weeks=self.recurrence)
        if self.horizon_basis == 'months':
            end_date = start_date + relativedelta(months=self.recurrence)
        if self.horizon_basis == 'years':
            end_date = start_date + relativedelta(years=self.recurrence)

        if self.data_profile == 'hourly':
            self.diff = end_date - start_date  # difference
            self.diff = int(self.diff.total_seconds()/3600) #difference in hours

        if self.data_profile == 'daily':
            self.diff = end_date - start_date  # difference
            self.diff = int(self.diff.total_seconds()/3600/24) #difference in days
            

    
    @validator("product_diff")
    def product_diff_valid(cls, v):
        options_product_diff = ["noPref", "co2Emissions", "networkDistance"]
        if v not in options_product_diff:
            raise ValueError("product_diff should be one of " + str(options_product_diff))
        return v

    @validator("market_design")
    def market_design_valid(cls, v):
        # check if input is correct
        options_market_design = ["centralized", "decentralized"]
        if v not in options_market_design:
            raise ValueError('market_design should be one of ' + str(options_market_design))
        return v

    @validator("horizon_basis")
    def horizon_basis_valid(cls, v):
        # check if input is correct
        options_horizon_basis = ['weeks', 'months', 'years']
        if v not in options_horizon_basis:
            raise ValueError('horizon_basis should be one of ' + str(options_horizon_basis))
        return v

    @validator("recurrence")
    def recurrence_valid(cls, v, values):
        # check if input is correct
        if not ((type(v)) == int):
            raise ValueError('recurrence should be an integer')
        if (values['horizon_basis'] == 'weeks') and v > 52:
            raise ValueError('If horizon_basis is weeks, then recurrence should be less than 53')
        if (values['horizon_basis'] == 'months') and v > 12:
            raise ValueError('If horizon_basis is months, then recurrence should be less than 13')
        if (values['horizon_basis'] == 'years') and v > 21:
            raise ValueError('If horizon_basis is years, then recurrence should be less than 21')
        return v

    @validator("ydr")
    def ydr_valid(cls, v):
        # check if input is correct
        if (v > 1) or (v < -1):
            raise ValueError('ydr should be within the range [-1,1]')
        return v

    @validator("data_profile")
    def data_profile_valid(cls, v):
        # check if input is correct
        options_data_profile=['hourly', 'daily']
        if v not in options_data_profile:
            raise ValueError('data_profile should be one of ' + str(options_data_profile))
        return v
    
    @validator("solver")
    def solver_implemented(cls, v):
        if v not in ["SCIP", "GUROBI", "HIGHS", "COPT"]:
            raise ValueError("solver should be SCIP, GUROBI, HIGHS or COPT")
        return v


class AgentData(BaseModel):
    """
    Object that stores all agent related data
    Contains an entry for each different input.
    If the input is constant in time, it is a dataframe with agent ID as column name, and the input as row
    If the input is varying in time, it is a dataframe with agent ID as column name, and time along the rows
    """
    settings: MarketSettings
    name: List
    storage_name: List
    storage_capacity: list
    gmax: List
    lmax: List
    cost: List
    util: List
    co2: Union[None, List] = None
    #to be filled in init
    nr_of_agents : Any
    nr_of_stor : Any
    co2_emission : Any
    agent_name : Any
    lmin_zeros : Any
    gmin_zeros : Any
    gmin : Any
    lmin : Any
    day_range: Any
    data_size: Any
    fbp_time: Any = None
    fbp_agent: Any = None

    def __init__(self, **data) -> None:
        """
        create AgentData object if all inputs are correct
        """
        # pydantic __init__ syntax
        super().__init__(**data)


        # #Just to avoid changing centralized_market and resultobject
        # self.day_range=self.settings.day_range
        # self.data_size=self.settings.data_size

        # set nr of agents, names, and types
        self.nr_of_agents = len(self.name)
        self.nr_of_stor = len(self.storage_name)

        self.agent_name = self.name
        # add co2 emission info if needed
        if self.settings.product_diff == "co2Emissions":
            self.co2_emission = pd.DataFrame(np.reshape(self.co2, (1, self.nr_of_agents)), columns=self.agent_name) #1xnr_of_agents dimension
        else:
            self.co2_emission = None # pd.DataFrame(np.ones((1, self.nr_of_agents))*np.nan, columns=name)

        #If data is provided for 1 year, but user wants to simulate more than 1 year: gmax, cost and util will be replicated; lmax will replicate based on ydr
        if self.settings.horizon_basis == 'years' and self.settings.recurrence > 1 and 365 <= len(self.gmax) == len(self.lmax) == len(self.cost) == len(self.util) <= 366:
            self.gmax = pd.DataFrame(self.replicate_data(np.array(self.gmax), self.settings), columns=self.agent_name)
            self.lmax = pd.DataFrame(self.yearly_demand_rate(np.array(self.lmax), self.settings), columns=self.agent_name)

            self.cost = pd.DataFrame(self.replicate_data(np.array(self.cost), self.settings), columns=self.agent_name)
            self.util = pd.DataFrame(self.replicate_data(np.array(self.util), self.settings), columns=self.agent_name)

        #If user provides hourly data, but wants a daily simulation
        if self.settings.data_profile == 'daily' and len(self.gmax) == len(self.lmax) == len(self.cost) == len(self.util) == self.settings.diff * 24:
            self.gmax = pd.DataFrame(self.cumulative_sum(np.array(self.gmax), self.settings), columns=self.agent_name)
            self.lmax = pd.DataFrame(self.cumulative_sum(np.array(self.lmax), self.settings), columns=self.agent_name)

            self.cost = pd.DataFrame(self.average_sum(np.array(self.cost), self.settings), columns=self.agent_name)
            self.util = pd.DataFrame(self.average_sum(np.array(self.util), self.settings), columns=self.agent_name)
        else:
            self.gmax = pd.DataFrame(self.gmax, columns=self.agent_name)
            self.lmax = pd.DataFrame(self.lmax, columns=self.agent_name)

            self.cost = pd.DataFrame(self.cost, columns=self.agent_name)
            self.util = pd.DataFrame(self.util, columns=self.agent_name)

            self.storage_capacity = pd.DataFrame(self.storage_capacity, columns=self.storage_name)

        # These are parameters now
        self.lmin_zeros = np.zeros((self.settings.diff, self.nr_of_agents))
        self.gmin_zeros = np.zeros((self.settings.diff, self.nr_of_agents))
        self.gmin = pd.DataFrame(self.gmin_zeros, columns=self.agent_name)
        self.lmin = pd.DataFrame(self.lmin_zeros, columns=self.agent_name)

    def cumulative_sum(self, nested_array, settings):
        x=np.zeros([self.settings.diff,self.nr_of_agents])
        for i in range(0,self.nr_of_agents):
            for k,j in enumerate(range(0,self.settings.diff*24,24)):
                x[k][i]=sum(nested_array[j:j+24,i])
        return x
    
    def average_sum(self, nested_array, settings):
        x=np.zeros([self.settings.diff,self.nr_of_agents])
        for i in range(0,self.nr_of_agents):
            for k,j in enumerate(range(0,self.settings.diff*24,24)):
                x[k][i]=np.average(nested_array[j:j+24,i])
        return x
    

    def check_dimension(input_list):
        aux=[]
        new=[]
        for iter in range(len(input_list)):
            aux.append(len(input_list[iter]))
        for dim in aux:
            if dim not in new:
                new.append(dim)
        return new

    def replicate_data(self, nested_list, settings):
        aux_list=nested_list
        for i in range(0,settings.recurrence+1):
            aux_list=np.r_[aux_list, nested_list]
            if len(aux_list) >= self.settings.diff:
                break
        return aux_list[0:self.settings.diff]

    #Increases demand rate over years
    def yearly_demand_rate(self, nested_list, settings):
        aux_list=nested_list
        for i in range(0,settings.recurrence+1):
            aux_list=np.r_[aux_list, nested_list*(1+(settings.ydr*(i+1)))]
            if len(aux_list) >= self.settings.diff:
                break
        return aux_list[0:self.settings.diff]
    
    @validator("fbp_time")
    def fbp_valid(cls, v, values):
        if v is not None:
            if v >= values['settings'].diff:
                raise ValueError("Find the best price: the selected time must be within the simulation range.")
        return v

    @validator("name") #checking list dimensions
    def name_valid(cls, v):
        if isinstance(v[0], list) == True:
            raise ValueError('Agent IDs should be one dimensional list')
        return v
    @validator("storage_name") #checking list dimensions
    def storage_name_valid(cls, v):
        if not np.array(v).ndim == 1:
            raise ValueError('Storage IDs should be one dimensional list')
        return v
    @validator("storage_name")
    def no_storage_in_decentralized(cls, v, values):
        if (len(v) > 0) & (values["settings"].market_design == "decentralized"):
            raise NotImplementedError("Storage can only be included in the centralized market design, " +
            "it is not implemented in the decentralized market (yet). \n" +
            "Please select the centralized market design instead. ")
        return v
    @validator("storage_name")
    def no_storage_in_dailysimulation(cls, v, values):
        if (len(v) > 0) and (values["settings"].data_profile == 'daily'):
            raise NotImplementedError("The daily simulation is not available in case storage is included. Please select hourly simulation instead.")
        return v
    @validator("storage_capacity")
    def storage_capacity_for_all_storages(cls, v, values):
        if np.array(v).ndim == 2:
            nr_of_stor_dimension = np.array(v).shape[1]
            if not nr_of_stor_dimension == len(values["storage_name"]):
                raise ValueError("The 'storage_capacity' input should be given for all storages in 'storage_name', and no others.")
        return v
    @validator("storage_capacity")
    def storage_capacity_for_all_timesteps(cls, v, values):
        # if there is storage in the simulation, the storage capacity must be given for each time step
        if len(values["storage_name"]) > 0:
            time_dimension = np.array(v).shape[0]
            if not time_dimension == values["settings"].diff:
                raise ValueError("The storage capacity must be given for each timestep in the selected time horizon. Probably start_datetime is selected " + 
                "such that outputs from TEO do not cover the entire time period selected for the market module. ")
        return v
    @validator('gmax')
    def gmax_valid(cls, v, values):
        if values['settings'].data_profile == 'hourly' and not (values['settings'].horizon_basis == 'years' and values['settings'].recurrence > 1):
            if (len(cls.check_dimension(v)) != 1 or cls.check_dimension(v)[0] != len(values['name'])) or (
            not len(v) == values['settings'].diff):
                raise ValueError('gmax dimensions are incorrect. Dimensions should be: [{:d}*{:d}]'.format(values['settings'].diff,
                    len(values['name'])))

        # elif values['settings'].data_profile == 'daily' and not (values['settings'].horizon_basis == 'years' and values['settings'].recurrence > 1):
        #     if (len(cls.check_dimension(v)) != 1 or cls.check_dimension(v)[0] != len(values['name'])) or (
        #     len(v) != values['settings'].diff and len(v) != values['settings'].diff * 24):
        #         raise ValueError('gmax dimensions are incorrect. Dimensions should be: [{:d}*{:d}] or [{:d}*{:d}]'.format(values['settings'].diff,
        #             len(values['name']), values['settings'].diff*24,
        #             len(values['name'])))

        # elif (values['settings'].horizon_basis == 'years' and values['settings'].recurrence > 1):
        #     if (len(cls.check_dimension(v)) != 1 or cls.check_dimension(v)[0] != len(values['name'])) or (
        #             len(v) != values['settings'].diff and len(v) != 365 and len(v) != 366):
        #         raise ValueError(
        #             'gmax dimensions are incorrect. Dimensions should be: [{:d}*{:d}] or [{:d}*{:d}] or [{:d}*{:d}] or [{:d}*{:d}]'.format(
        #                 values['settings'].diff,
        #                 len(values['name']), values['settings'].diff * 24,
        #                 len(values['name']), 365,len(values['name']), 366,len(values['name'])))
        return v

    @validator('lmax')
    def lmax_valid(cls, v, values):
        if values['settings'].data_profile == 'hourly' and not (values['settings'].horizon_basis == 'years' and values['settings'].recurrence > 1):
            if (len(cls.check_dimension(v) ) != 1 or cls.check_dimension(v)[0] != len(values['name'])) or (
            not len(v) == values['settings'].diff):
                raise ValueError('lmax dimensions are incorrect. Dimensions should be: [{:d}*{:d}]'.format(values['settings'].diff,
                    len(values['name'])))

        # elif values['settings'].data_profile == 'daily' and not (values['settings'].horizon_basis == 'years' and values['settings'].recurrence > 1):
        #     if (len(cls.check_dimension(v) ) != 1 or cls.check_dimension(v)[0] != len(values['name'])) or (
        #     len(v) != values['settings'].diff and len(v) != values['settings'].diff * 24):
        #         raise ValueError('lmax dimensions are incorrect. Dimensions should be: [{:d}*{:d}] or [{:d}*{:d}]'.format(values['settings'].diff,
        #             len(values['name']), values['settings'].diff*24,
        #             len(values['name'])))
        #
        # elif (values['settings'].horizon_basis == 'years' and values['settings'].recurrence > 1):
        #     if (len(cls.check_dimension(v)) != 1 or cls.check_dimension(v)[0] != len(values['name'])) or (
        #             len(v) != values['settings'].diff and len(v) != 365 and len(v) != 366):
        #         raise ValueError(
        #             'lmax dimensions are incorrect. Dimensions should be: [{:d}*{:d}] or [{:d}*{:d}] or [{:d}*{:d}] or [{:d}*{:d}]'.format(
        #                 values['settings'].diff,
        #                 len(values['name']), values['settings'].diff * 24,
        #                 len(values['name']), 365,len(values['name']), 366,len(values['name'])))

        return v

    @validator('cost')
    def cost_valid(cls, v, values):
        if values['settings'].data_profile == 'hourly' and not (values['settings'].horizon_basis == 'years' and values['settings'].recurrence > 1):
            if (len(cls.check_dimension(v)) != 1 or cls.check_dimension(v)[0] != len(values['name'])) or (
            not len(v) == values['settings'].diff):
                raise ValueError('cost dimensions are incorrect. Dimensions should be: [{:d}*{:d}]'.format(values['settings'].diff,
                    len(values['name'])))

        # elif values['settings'].data_profile == 'daily' and not (values['settings'].horizon_basis == 'years' and values['settings'].recurrence > 1):
        #     if (len(cls.check_dimension(v)) != 1 or cls.check_dimension(v)[0] != len(values['name'])) or (
        #     len(v) != values['settings'].diff and len(v) != values['settings'].diff * 24):
        #         raise ValueError('cost dimensions are incorrect. Dimensions should be: [{:d}*{:d}] or [{:d}*{:d}]'.format(values['settings'].diff,
        #             len(values['name']), values['settings'].diff*24,
        #             len(values['name'])))
        #
        # elif (values['settings'].horizon_basis == 'years' and values['settings'].recurrence > 1):
        #     if (len(cls.check_dimension(v)) != 1 or cls.check_dimension(v)[0] != len(values['name'])) or (
        #             len(v) != values['settings'].diff and len(v) != 365 and len(v) != 366):
        #         raise ValueError(
        #             'cost dimensions are incorrect. Dimensions should be: [{:d}*{:d}] or [{:d}*{:d}] or [{:d}*{:d}] or [{:d}*{:d}]'.format(
        #                 values['settings'].diff,
        #                 len(values['name']), values['settings'].diff * 24,
        #                 len(values['name']), 365,len(values['name']), 366,len(values['name'])))
        return v

    @validator('util')
    def util_valid(cls, v, values):
        if values['settings'].data_profile == 'hourly' and not (values['settings'].horizon_basis == 'years' and values['settings'].recurrence > 1):
            if (len(cls.check_dimension(v)) != 1 or cls.check_dimension(v)[0] != len(values['name'])) or (
            not len(v) == values['settings'].diff):
                raise ValueError('util dimensions are incorrect. Dimensions should be: [{:d}*{:d}]'.format(values['settings'].diff,
                    len(values['name'])))

        # elif values['settings'].data_profile == 'daily' and not (values['settings'].horizon_basis == 'years' and values['settings'].recurrence > 1):
        #     if (len(cls.check_dimension(v)) != 1 or cls.check_dimension(v)[0] != len(values['name'])) or (
        #     len(v) != values['settings'].diff and len(v) != values['settings'].diff * 24):
        #         raise ValueError('util dimensions are incorrect. Dimensions should be: [{:d}*{:d}] or [{:d}*{:d}]'.format(values['settings'].diff,
        #             len(values['name']), values['settings'].diff*24,
        #             len(values['name'])))
        #
        # elif (values['settings'].horizon_basis == 'years' and values['settings'].recurrence > 1):
        #     if (len(cls.check_dimension(v)) != 1 or cls.check_dimension(v)[0] != len(values['name'])) or (
        #             len(v) != values['settings'].diff and len(v) != 365 and len(v) != 366):
        #         raise ValueError(
        #             'util dimensions are incorrect. Dimensions should be: [{:d}*{:d}] or [{:d}*{:d}] or [{:d}*{:d}] or [{:d}*{:d}]'.format(
        #                 values['settings'].diff,
        #                 len(values['name']), values['settings'].diff * 24,
        #                 len(values['name']), 365,len(values['name']), 366,len(values['name'])))
        return v


    @validator("co2")
    def co2_valid(cls, v, values):
        if values["settings"].product_diff == "co2Emissions":
            if v is None:
                raise ValueError("co2 intensity for agents is a mandatory input since you selected" + \
                                 "product_diff = co2Emissions")
            else:
                if not len(v) == len(values["name"]):
                    raise ValueError("'co2' has to be a list of size nr_of_agents=" + str(len(values["name"])))
        return v

#if MarketSettings.market_design_valid == 'decentralized':
    # network data ---------------------------------------------------------------------------------------------------------
class Network(BaseModel):

    agent_data : AgentData
    gis_data : Any
    distance: Any
    all_distance: Any
    all_distance_percentage: Any

    """
    :param agent_data: AgentData object.
    :param gis_data: dataframe provided by GIS to us. has columns from_to (tuple), Losses total (W), length (m), total costs
    :output: a Network object with 2 properties: distance and losses (both n by n np.array). distance[1,3] is the
    distance from agent 1 to agent 3. has np.inf if cannot reach the agent.
    """
    def __init__(self, **data) -> None:
        """
        create Network object if all inputs are correct
        """
        # pydantic __init__ syntax
        super().__init__(**data)

        # define distance and losses between any two agents in a matrix ----------------------------
        self.distance = np.inf * np.ones((self.agent_data.nr_of_agents, self.agent_data.nr_of_agents))
        for i in range(self.agent_data.nr_of_agents):
            self.distance[i, i] = 0.0  # distance to self is zero.
        for row_nr in range(len(self.gis_data["from_to"].values)):
            (From, To) = self.gis_data["from_to"].values[row_nr]
            self.distance[self.agent_data.agent_name.index(From), self.agent_data.agent_name.index(To)] = self.gis_data['length'].iloc[row_nr]

            # Dijkstra's shortest path
            def calculate_distances(graph, starting_vertex):
                distances = {vertex: float('infinity') for vertex in graph}
                distances[starting_vertex] = 0

                pq = [(0, starting_vertex)]
                while len(pq) > 0:
                    current_distance, current_vertex = heapq.heappop(pq)

                    # Nodes can get added to the priority queue multiple times. We only
                    # process a vertex the first time we remove it from the priority queue.
                    if current_distance > distances[current_vertex]:
                        continue

                    for neighbor, weight in graph[current_vertex].items():
                        distance = current_distance + weight

                        # Only consider this new path if it's better than any path we've
                        # already found.
                        if distance < distances[neighbor]:
                            distances[neighbor] = distance
                            heapq.heappush(pq, (distance, neighbor))
                return distances

            # graph for the Dijkstra's
            graph = {i: {j: np.inf for j in range(0, (self.agent_data.nr_of_agents))} for i in
                     range(0, (self.agent_data.nr_of_agents))}
            total_dist = []  # total network distance

            for j in range(0, (self.agent_data.nr_of_agents)):
                for i in range(0, (self.agent_data.nr_of_agents)):
                    if self.distance[i][j] != 0 and self.distance[i][j] != np.inf:
                        # symmetric matrix
                        graph[i][j] = self.distance[i][j]
                        graph[j][i] = self.distance[i][j]
                        total_dist.append(self.distance[i][j])

            # Matrix with the distance between all the agents
            self.all_distance = np.ones((self.agent_data.nr_of_agents, self.agent_data.nr_of_agents))  # might need this later
            for i in range(0, (self.agent_data.nr_of_agents)):
                aux = []
                aux = calculate_distances(graph, i)
                for j in range(0, (self.agent_data.nr_of_agents)):
                    self.all_distance[i][j] = aux[j]
            # network usage in percentage for each trade Pnm
            self.all_distance_percentage = self.all_distance / sum(total_dist)
        self.all_distance_percentage[self.all_distance_percentage == np.inf] = 0 #Replacing inf for 0. Solver was throwing an infinity error.
        #It is irrelevant because these trades never take place.


    @validator('gis_data')
    def gis_data_mandatory_if_p2p_and_loss_or_distance(cls, v, values):
        if values["agent_data"].settings.market_design == "decentralized" and (
                values["agent_data"].settings.product_diff in ["networkDistance"]) and v is None:
            raise ValueError(
                "gis_data has to be given for p2p market with 'networkDistance' based preference"
             )

        if 'length' not in v.keys() and values["agent_data"].settings.market_design == "decentralized" and (
                values["agent_data"].settings.product_diff in ["networkDistance"]):
            raise ValueError('gis_data is not including length between peers.')

        if 'from_to' not in v.keys() and values["agent_data"].settings.market_design == "decentralized" and (
                values["agent_data"].settings.product_diff in ["networkDistance"]):
            raise ValueError('gis_data is not including from_to data.')

        for keys in v.keys():
           if type(v[keys]) != pd.core.series.Series:
               raise ValueError('gis_data dict values should be panda series.')
        return v
