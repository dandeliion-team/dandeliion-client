# built-in modules
import json
from pathlib import Path
from typing import Union

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
        params: Union[str, Path, dict],
        experiment: Experiment = None,
        extra_params: dict = None,
) -> Solution:

    """Method for submitting/running a DandeLiion simulation.

    Args:
        simulator (Simulator): instance of simulator class providing information
            to connect to simulation server
        params (str|Path|dict): path to BPX parameter file or already read-in valid BPX as dict
        experiment (Experiment, optional): instance of pybamm Experiment defining steps
        extra_params (dict, optional): extra parameters e.g. simulation mesh, choice of discretisation method
            and initial conditions specified in the dictionary
            (if none or only subset is provided, either user-defined values
            stored in the bpx or, if not present, default values will be used instead)
    Returns:
        :class:`Solution`: solution for this simulation run
    """

    if not isinstance(params, dict):
        with open(params, 'r') as f:
            params = json.load(f)

    # validate BPX
    parse_bpx_obj(params)

    if "User-defined" not in params['Parameterisation']:
        params['Parameterisation']["User-defined"] = {}

    # add experiment
    if experiment:
        params['Parameterisation']["User-defined"]["DandeLiion: Experiment"] = _convert_experiment(experiment)

    # add/overwrite extra parameters
    if extra_params:
        for param, value in extra_params.items():
            params['Parameterisation']["User-defined"][f"DandeLiion: {param}"] = value

    return simulator.submit(parameters=params, is_blocking=True)
