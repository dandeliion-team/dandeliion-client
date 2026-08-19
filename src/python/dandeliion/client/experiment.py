"""Fallback experiment container used when optional PyBaMM is unavailable."""

# SPDX-License-Identifier: BSD-3-Clause


class Experiment:
    """Store experimental conditions without validating them through PyBaMM.

    This class is exported as :class:`dandeliion.client.Experiment` only when
    ``pybamm.Experiment`` is unavailable. Each operating step should be a
    string; install the optional PyBaMM dependency for richer validation.
    """

    def __init__(
        self,
        operating_conditions: list[str | tuple[str, ...]],
        period: str | None = None,
        temperature: float | str | None = None,
        termination: str | list[str] | None = None,
    ):
        """Initialize an experiment when optional PyBaMM is unavailable.

        Args:
            operating_conditions: Ordered operating steps. Tuples group steps
                into a cycle.
            period: Default output sampling period, such as ``"1 second"``.
            temperature: Optional experiment temperature in Kelvin or as a
                supported descriptive string.
            termination: Optional global termination condition or conditions.

        """
        # Save arguments
        self.args = (
            operating_conditions,
            period,
            temperature,
            termination,
        )
