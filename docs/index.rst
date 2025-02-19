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

  credential = ("juser", "dandeliion")
  simulator = dandeliion.Simulator(credential)

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

  var_pts = {"x_n": 16, "x_s": 8, "x_p": 16, "r_n": 16, "r_p": 16}

  solution = dandeliion.solve(
        simulator=simulator,
        params=params,
        model='DFN',
        experiment=experiment,
        var_pts=var_pts,
  )

  plt.plot(
      solution["Time [s]"],
      solution["Current [A]"],
      label="DandeLiion",
  )  # Current vs Time

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
