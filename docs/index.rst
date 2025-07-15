.. DandeLiion Client documentation master file, created by
   sphinx-quickstart on Fri Jul 26 22:05:03 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

===============================
DandeLiion Client documentation
===============================

The DandeLiion client provides a PyBaMM-like python interface to run on local or remote DandeLiion server instances.

Installation
============

The DandeLiion client can be installed directly from pypi using pip with the following command::

  pip install dandeliion-client

Example
=======

The following code is an example for how to write a python script to run a simulation::

  import dandeliion.client as dandeliion
  import numpy as np
  import matplotlib.pyplot as plt

  api_url = "https://api.dandeliion.com/v1"
  api_key = "API KEY"  # Replace with your actual API key
  simulator = dandeliion.Simulator(api_url, api_key)

  # BPX file or already read-in valid BPX as dict or BPX object
  params = "BPX_file.json"

  experiment = dandeliion.Experiment(
      [
          (
              "Discharge at 10 A for 100 seconds",
              "Rest for 10 seconds",
              "Charge at 6 A for 100 seconds",
          )
      ]
      * 2,
      period="1 second",
  )

  extra_params = {}
  extra_params["Mesh"] = {"x_n": 16, "x_s": 16, "x_p": 16, "r_n": 16, "r_p": 16}
  extra_params["Initial SOC"] = 1.0

  print("Validating parameters and the API key, then starting the simulation...")

  solution = dandeliion.solve(
      simulator=simulator,
      params=params,
      experiment=experiment,
      extra_params=extra_params,
  )

  print("\nSolution status:", solution.status)
  print("\nSolution log:", solution.log)

  # Print all available keys in the solution object
  print("Available keys in the solution object:")
  for key in sorted(solution.keys()):
      print(key)

  # Print the final values of time, voltage, and temperature
  print(f"\nFinal time [s]: {solution['Time [s]'][-1]}")
  print(f"Final voltage [V]: {solution['Voltage [V]'][-1]}")
  print(f"Final temperature [K]: {solution['Temperature [K]'][-1]}")

  # Plot current and voltage vs time
  fig, axs = plt.subplots(2, 1, figsize=(10, 8))
  axs[0].plot(solution["Time [s]"], solution["Current [A]"], label="DandeLiion")
  axs[0].set_xlabel("time [s]")
  axs[0].set_title("Current [A]")
  axs[0].legend()
  axs[1].plot(solution["Time [s]"], solution["Voltage [V]"], label="DandeLiion")
  axs[1].set_xlabel("time [s]")
  axs[1].set_title("Voltage [V]")
  axs[1].legend()
  plt.tight_layout()
  plt.show()

  # Plot concentration in the electrolyte vs `x` at the last time step
  plt.plot(
      solution["Electrolyte x-coordinate [m]"] * 1e6,
      solution["Electrolyte concentration [mol.m-3]"][-1],
      label="Dandeliion",
  )
  plt.xlabel(r"x [$\mu$m]")
  plt.title("Electrolyte conc. (end of experiment) [mol.m-3]")
  plt.legend()
  plt.show()

  # If the user needs the solution at the `t_eval` times, the following code can be used
  t_eval = np.arange(0, 20, 1)  # A list of output times
  print("\nTime [s]\tVoltage [V]")
  for t, voltage in zip(t_eval, solution["Voltage [V]"](t=t_eval)):
      print(f"{t}\t{voltage}")

  # Save the solution to a file and load it back
  solution_file = 'test_solution.json'
  solution.dump(solution_file)
  restored_solution = dandeliion.Simulator.restore(solution_file, api_key=api_key)

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
   dandeliion.client.experiment.Experiment
