# built-in modules
import json

# custom modules
from .simulator import Simulator
from .solution import Solution

# third-party modules
from pybamm import Experiment
from bpx import parse_bpx_obj


def _convert_experiment(experiment: Experiment):
    """
    converts pybamm experiment into dict
    """
    operating_conditions, period, temperature, termination = experiment.args
    steps = []
    for cond in operating_conditions:
        if isinstance(cond, tuple):
            steps += list(cond)
        else:
            steps.append(cond)

    return {
        "Instructions": steps,
        "Period": period,
        "Temperature": temperature,
        "Termination": termination,
    }


def solve(
        simulator: Simulator,
        params: str,
        experiment: Experiment,
        extra_params: dict = None,
) -> Solution:

    """Method for submitting/running a Dandeliion simulation.

    Args:
        simulator (Simulator): instance of simulator class providing information
            to connect to simulation server
        params (str): path to BPX parameter file
        experiment (Experiment): instance of pybamm Experiment defining steps
        extra_params (dict, optional): extra parameters e.g. simulation mesh, choice of discretisation method
            and initial conditions specified in the dictionary
            (if none or only subset is provided, either user-defined values
            stored in the bpx or, if not present, default values will be used instead)
    Returns:
        :class:`Solution`: solution for this simulation run
    """

    with open(params, 'r') as f:
        data = json.load(f)
    # validate BPX
    parse_bpx_obj(data)

    if "User-defined" not in data['Parameterisation']:
        data['Parameterisation']["User-defined"] = {}

    # add experiment
    data['Parameterisation']["User-defined"]["DandeLiion: Experiment"] = _convert_experiment(experiment)

    # add/overwrite extra parameters
    if extra_params:
        for param, value in extra_params.items():
            data['Parameterisation']["User-defined"][f"DandeLiion: {param}"] = value

    return simulator.submit(parameters=data, is_blocking=True)
