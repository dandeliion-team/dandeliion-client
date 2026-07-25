# SPDX-License-Identifier: BSD-3-Clause


class Experiment:
    """
    Class for experimental conditions under which to run the model and linked to
    ``dandeliion.client.Experiment`` instead if ``pybamm.experiment.Experiment`` is not present.
    In general, a list of operating conditions should be passed in. Each operating condition
    should be a string.

    Parameters
    ----------
    operating_conditions : list[str]
        List of strings representing the operating conditions.
    period : str, optional
        Period (1/frequency) at which to record outputs. Default is 1 minute. Can be
        overwritten by individual operating conditions.
    temperature : float. optional
        The temperature of the experiment in Kelvin. Default is None whereby
        the ambient temperature is taken from the parameter set.
    termination : list[str], optional
        List of strings representing the conditions to terminate the experiment. Default is None.
    """

    def __init__(
        self,
        operating_conditions: list[str | tuple[str, ...]],
        period: str | None = None,
        temperature: float | str | None = None,
        termination: str | list[str] | None = None,
    ):
        # Save arguments
        self.args = (
            operating_conditions,
            period,
            temperature,
            termination,
        )
