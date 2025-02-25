# built-in modules
from pathlib import Path
from typing import Union

# custom modules
from .simulator import Simulator
from .solution import Solution

# third-party modules
from pybamm import Experiment
from bpx import parse_bpx_obj, parse_bpx_file, BPX


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
        params: Union[str, Path, dict, BPX],
        experiment: Experiment = None,
        extra_params: dict = None,
        is_blocking: bool = True,
) -> Solution:

    """Method for submitting/running a DandeLiion simulation.

    Args:
        simulator (Simulator): instance of simulator class providing information
            to connect to simulation server
        params (str|Path|dict|BPX): path to BPX parameter file or already read-in valid BPX as dict or BPX object
        experiment (Experiment, optional): instance of pybamm Experiment defining steps
        extra_params (dict, optional): extra parameters e.g. simulation mesh, choice of discretisation method
            and initial conditions specified in the dictionary
            (if none or only subset is provided, either user-defined values
            stored in the bpx or, if not present, default values will be used instead)
        is_blocking (bool, optional): determines whether command is blocking until computation has finished
            or returns right away. In the latter case, the Solution may still point to an unfinished run
            (its status can be checked with the property of the same name). Default: True
    Returns:
        :class:`Solution`: solution for this simulation run
    """

    # load & validate BPX
    if isinstance(params, dict):
        params = parse_bpx_obj(params)
    elif isinstance(params, str) or isinstance(params, Path):
        params = parse_bpx_file(params)
    elif not isinstance(params, BPX):
        raise ValueError("`params` has to be either `dict`, `str`, `Path` or `BPX`")

    # turn back into dict
    params = params.model_dump(by_alias=True, exclude_unset=True)

    if (
            "User-defined" not in params['Parameterisation'] or
            params['Parameterisation']["User-defined"] is None
    ):
        params['Parameterisation']["User-defined"] = {}

    # add experiment
    if experiment:
        params['Parameterisation']["User-defined"]["DandeLiion: Experiment"] = _convert_experiment(experiment)

    # add/overwrite extra parameters
    if extra_params:
        for param, value in extra_params.items():
            params['Parameterisation']["User-defined"][f"DandeLiion: {param}"] = value

    return simulator.submit(parameters=params, is_blocking=is_blocking)
