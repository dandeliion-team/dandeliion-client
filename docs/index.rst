.. Dandeliion Client documentation master file, created by
   sphinx-quickstart on Fri Jul 26 22:05:03 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

===============================
Dandeliion Client documentation
===============================

The Dandeliion client provides a pybamm-like python interface to run on a local or remote Dandeliion server instance.

Installation
============

The Dandeliion client can be installed directly from pypi using pip with the following command::

  pip install dandeliion-client

Example
=======

The following code is an example for how to write a python script to run a simulation::
  
  import dandeliion.client as dandeliion
  import numpy as np
  import matplotlib.pyplot as plt
  from pybamm import Experiment

  api_url = "https://server-address"
  api_key = "some_hash"
  simulator = dandeliion.Simulator(api_url, api_key)

  params = 'example_bpx.json'
  experiment = Experiment(
    [
        (
            "Discharge at 10 A for 100 seconds",
            "Rest for 10 seconds",
            "Charge at 6 A for 100 seconds",
        )
    ]
    * 2,
    termination="250 s",
    period="1 second",
  )

  extra_params = {"Mesh": {"x_n": 16, "x_s": 8, "x_p": 16, "r_n": 16, "r_p": 16}}

  solution = dandeliion.solve(
        simulator=simulator,
        params=params,
        experiment=experiment,
        extra_params=extra_params,
  )

  # Plot current and voltage vs time.
  # Here we access scalar values vs time.
  fig, axs = plt.subplots(2, 1, figsize=(10, 8))
  axs[0].plot(solution["Time [s]"], solution["Current [A]"], label="Dandeliion")
  axs[0].set_xlabel("time [s]")
  axs[0].set_title("Current [A]")
  axs[0].legend()
  axs[0].grid()
  axs[1].plot(solution["Time [s]"], solution["Voltage [V]"], label="Dandeliion")
  axs[1].set_xlabel("time [s]")
  axs[1].set_title("Voltage [V]")
  axs[1].legend()
  axs[1].grid()
  plt.tight_layout()
  plt.show()

  # If the user needs the solution at the `t_eval` times, the following code can be used (works only correctly on columns with timeline data)
  # This is a linear interpolation with constant extrapolation
  solution["Voltage [V]"](t=t_eval)

where the following classes & methods have been used:
  
.. toctree::
   :hidden:

   self

.. autosummary::
   :toctree: stubs
   :nosignatures:

   dandeliion.client.Simulator
   dandeliion.client.Solution
   dandeliion.client.solve
