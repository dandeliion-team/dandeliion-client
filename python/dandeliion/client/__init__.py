# built-in modules
import json

# custom modules
from .simulator import Simulator
from .mock_simulator import MockSimulator
from .solution import Solution
from dandeliion.client.tools.misc import unflatten_dict, update_dict

# third-party modules
from pybamm import Experiment
from bpx import parse_bpx_obj

discretizations = {
}

initial_condition_fields = {
    'Initial temperature [K]': 'params.cell.T0',
    'Initial concentration in electrolyte [mol.m-3]': 'params.cell.c0',
    'Initial state of charge': 'params.cell.Z0',
}

sim_params = {
    'x_n': 'params.anode.N',
    'x_s': 'params.separator.N',
    'x_p': 'params.cathode.N',
    'r_n': 'params.anode.M',
    'r_p': 'params.cathode.M',
}


def solve(
        simulator: Simulator,
        params: str,
        experiment: Experiment,
        var_pts: dict = None,
        model: str = 'DFN',
        initial_condition: dict = None,
        t_output: list = None,
        dt_eval: float = 0.1,
) -> Solution:

    """Method for submitting/running a Dandeliion simulation.

    Args:
        simulator (Simulator): instance of simulator class providing information
            to connect to simulation server
        params (str): path to BPX parameter file
        experiment (Experiment): instance of pybamm Experiment;
        var_pts (dict, optional): simulation mesh specified by the following parameters in dictionary
            (if none or only subset is provided, either user-defined values
            stored in the bpx or, if not present, default values will be used instead):

            * 'x_n' - Number of nodes in the electrolyte (negative electrode). Default is 30.
            * 'x_s' - Number of nodes in the electrolyte (separator). Default is 20.
            * 'x_p' - Number of nodes in the electrolyte (positive electrode). Default is 30.
            * 'r_n' - Number of nodes in particles (negative electrode). Default is 30.
            * 'r_p' - Number of nodes in particles (positive electrode). Default is 30.
        model (str, optional): name of model to be simulated. Default is 'DFN'. Currently supported models are:

            * 'DFN' - Newman 1D model
        initial_condition (dict, optional): dictionary of additional initial conditions
            (overwrites parameters provided in parameter file if they exist).
            Currently supported initial conditions are:

            * 'Initial temperature [K]'
            * 'Initial concentration in electrolyte [mol.m-3]'
            * 'Initial state of charge'

    Returns:
        :class:`Solution`: solution for this simulation run
    """

    with open(params) as f:
        data = json.load(f)
    # validate BPX
    parse_bpx_obj(data)

    # add/overwrite initial conditions
    if initial_condition:
        update_dict(data, unflatten_dict(
            {initial_condition_fields[field]: value
             for field, value in initial_condition.items()}
        ))

    # add/overwrite simulation params
    if var_pts is not None:
        update_dict(data, unflatten_dict(
            {sim_params[field]: value
             for field, value in var_pts.items()}
        ))

    return simulator.submit(parameters=params, is_blocking=True)
