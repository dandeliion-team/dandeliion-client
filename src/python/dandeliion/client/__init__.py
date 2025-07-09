# built-in modules
import importlib.metadata
from pathlib import Path
from typing import Union
from collections.abc import Sequence

# custom modules
from .simulator import Simulator
from .solution import Solution

# third-party modules
try:
    from pybamm import Experiment, Interpolant
    from pybamm.experiment.step import Power, Current, Voltage, BaseStep
    __has_pybamm__ = True
except ModuleNotFoundError:
    from .experiment import Experiment
    __has_pybamm__ = False
from bpx import parse_bpx_obj, parse_bpx_file, BPX

__version__ = importlib.metadata.version('dandeliion-client')


def _convert_experiment(experiment: Experiment) -> tuple[dict, dict]:
    """
    converts pybamm experiment into dict
    """
    operating_conditions, period, temperature, termination = experiment.args
    steps = []
    time_series = None
    for cond in operating_conditions:
        if isinstance(cond, tuple):
            steps += list(cond)
        elif isinstance(cond, str):
            steps.append(cond)
        elif __has_pybamm__ and isinstance(cond, (Current, Power)):
            if isinstance(cond.value, Interpolant):
                if cond.input_duration is not None:
                    raise TypeError("'duration' argument not supported for drive cycles yet.")
                time_series = {
                    'Time [s]': list(cond.value.x[0] if isinstance(cond.value.x, Sequence)
                                     else cond.value.x)
                }
                if isinstance(cond, Current):
                    time_series['Current [A]'] = list(cond.value.y)
                else:
                    time_series['Power [W]'] = list(cond.value.y)
                steps.append('Time series')
            else:
                raise TypeError(f"{type(cond)} only supported as drive cycle at the moment.")
        else:
            raise TypeError(f"Unsupported type found in Experiment: {type(cond)}")

    return {
        "Instructions": steps,
        "Period": period,
        "Temperature": temperature,
        "Termination": termination,
    }, time_series


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
        experiment_, time_series = _convert_experiment(experiment)
        params['Parameterisation']["User-defined"]["DandeLiion: Experiment"] = experiment_
        if time_series is not None:
            # check if time series already exists and only accept it if identical
            if "DandeLiion: Time series input" in params['Parameterisation']["User-defined"]:
                if params['Parameterisation']["User-defined"]["DandeLiion: Time series input"] != time_series:
                    raise ValueError("Currently only identical drive cycles are supported")
            else:
                params['Parameterisation']["User-defined"]["DandeLiion: Time series input"] = time_series

    # add/overwrite extra parameters
    if extra_params:
        for param, value in extra_params.items():
            params['Parameterisation']["User-defined"][f"DandeLiion: {param}"] = value

    return simulator.submit(parameters=params, is_blocking=is_blocking)
