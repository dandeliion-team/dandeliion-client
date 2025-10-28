![DandeLiion_logo](https://simulation.dandeliion.com/static/dl_logo.png)

#

<div align="center">

[![ci-testing](https://github.com/dandeliion-team/dandeliion-client/actions/workflows/ci_testing.yml/badge.svg?branch=master)](https://github.com/dandeliion-team/dandeliion-client/actions/workflows/ci_testing.yml)
[![documentation](https://github.com/dandeliion-team/dandeliion-client/actions/workflows/documentation.yml/badge.svg?branch=master&action=push)](https://dandeliion-team.github.io/dandeliion-client  )
[![release](https://img.shields.io/github/v/release/dandeliion-team/dandeliion-client?color=yellow)](https://github.com/dandeliion-team/dandeliion-client/releases)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/dandeliion-team/dandeliion-client/badge)](https://scorecard.dev/viewer/?uri=github.com/dandeliion-team/dandeliion-client)

</div>

# DandeLiion client

The DandeLiion client is a client software written in Python to submit/run DandeLiion simulations on a remote server and to retrieve simulation results.

## Installation

```bash
pip install dandeliion-client
```

**NOTE:** `dandeliion-client` requires Python 3.9 and higher.

As of client version 1.1, `pybamm` is an optional dependency and will only be installed if you run:

```bash
pip install dandeliion-client[pybamm]
```

## Prerequisites

Import DandeLiion client and all relevant packages such as `numpy`, `matplotlib`, and (optionally) PyBaMM to validate PyBaMM’s `Experiment`:

```python
import dandeliion.client as dandeliion
import numpy as np
import matplotlib.pyplot as plt
import pybamm
```

The client version can be obtained using

```python
dandeliion.__version__
```

Create an instance of [`dandeliion.client.Simulator`](https://dandeliion-team.github.io/dandeliion-client/stubs/dandeliion.client.Simulator.html), providing the API URL and API token:

```python
api_url = "https://api.dandeliion.com/v1"
api_key = "API_TOKEN"
simulator = dandeliion.Simulator(api_url, api_key)
```

## Simulation parameters and models

Define the battery cell parameters by providing the BPX file name (as a string or `pathlib.Path`), a valid BPX as a `dict`, or `BPX` object itself. For example:

```python
params = "example_bpx.json"
```

The API client will validate the BPX. Currently supported BPX version is `0.5.0`.

Define a dictionary of extra parameters outside the BPX standard, such as mesh, initial state of charge or voltage, etc.:

```python
extra_params = {}
extra_params['Mesh'] = {"x_n": 16, "x_s": 16, "x_p": 16, "r_n": 16, "r_p": 16}
extra_params['Initial SOC'] = 1.0
extra_params['Lumped thermal model'] = 1.0  # Sets lumped thermal model
```

List of all supported parameters (`extra_params` keys):

| Parameter | Description |
| --- | --- |
| `'Mesh'` | Defines the number of mesh points in liquid and solid. Expects the following fields: `x_n`, `x_s`, `x_p`, `r_n`, `r_p`. Optional, all values default to `16`. Cannot be less than `4`. Mesh stretching factor: `alpha` (no implemented yet). See example above. |
| `'Initial SOC'` | Defines the initial State of Charge of the cell (or pack, for the pack model). Should be in the interval [`0`, `1`]. Default value is `1.0`. |
| `'Initial voltage [V]'` | Defines the initial voltage of the cell (or pack, for the pack model). Should be in the interval [`V_min`, `V_max`], where `V_min` and `V_max` are defined in the cell section of the BPX file. If both the initial SOC and initial voltage are provided, the initial SOC will be used and a warning will be produced. |
| `'Time series input'` | Allows the user to define the input current or power as time series (see [Drive cycles](#drive-cycles)). |
| `'Lumped thermal model'`| If this key is defined, the lumped thermal model will be used. The solver will read `"Specific heat capacity [J.K-1.kg-1]"`, `"Density [kg.m-3]"`, `"External surface area [m2]"`, `"Volume [m3]"` from the cell section of the BPX file. In addition, `"Heat transfer coefficient [W.m-2.K-1]"` extra parameter should be defined (see below). **Default model is isothermal.** |
| `'Heat transfer coefficient [W.m-2.K-1]'` | Heat transfer coefficient for the lumped thermal model. Cannot be negative. |
| `'Module'` | Defines the battery pack geometry and pack related parameters. |
| `'Safe mode'` | If defined, the solver will choose tighter convergence conditions, which may improve stability in some cases, but this also impacts performance. |
| `'extra_resources'` | Set `extra_resources` to `True` if runtime is estimated to exceed 15 mins or memory required exceeds 3 GB (Default is `False`). |

### A note about the initial conditions

The user can define the initial conditions in the input BPX file:

- The initial temperature of the cell is in the `"Cell"` section, `"Initial temperature [K]"` key.
- The initial concentration in electrolyte is in the `"Electrolyte"` section, `"Initial concentration in electrolyte [mol.m-3]"` key.
- The initial state of charge or initial voltage can be defined in the `"User-defined"` section, using `"DandeLiion: Initial SOC"` or `"DandeLiion: Initial voltage [V]"` keys. These keys will **not** invalidate the BPX file. Alternatively, `"Initial SOC"` or `"Initial voltage [V]"` can be added to the `extra_params` dictionary and passed to the solver.

## Defining the model input

Define the experiment in PyBaMM’s format, for example:

```python
experiment = dandeliion.Experiment(
  [
    (
      "Discharge at 1C until 3.8 V",
      "Hold at 3.8 V for 10 minutes (5 second period)",
      "Rest for 300 seconds",
      "Charge at 2000 mA for 1 hour or until 4.0 V",
      "Rest for 5 min",
      "Discharge at 20W for 25 minutes or until 2.5V",
      "Rest for 300 s (1 second period)",
      "Charge at C/2 until 4.0 V (0.5 min period)",
      "Hold at 4.0V for 0.1 hr (1s period)"
    )
  ]
  * 2,
  period = "10 s",
)
```

If PyBaMM is installed, `pybamm.experiment.Experiment` will be used, which includes validation of the experiment. Otherwise, [`dandeliion.client.Experiment`](https://dandeliion-team.github.io/dandeliion-client/stubs/dandeliion.client.experiment.Experiment.html) will be used, without validation.

## Drive cycles

The client allows the user to define the input current (or power) as time series.

Consider we have a CSV file with the drive cycle, where the first column is the time (in seconds), and the second column is the current (in Amps) or power (in Watts). This file can be read to a `numpy` array using `pandas` package:

```python
import pandas as pd

drive_cycle_data = pd.read_csv("US06.csv", comment="#", header=None).to_numpy()

# Negative current for discharge
drive_cycle = np.column_stack([drive_cycle_data[:, 0], -drive_cycle_data[:, 1]])
```

There are at least two ways of passing the time series to DandeLiion.

### Method 1

*Use this method if PyBaMM is not installed.*

Define DandeLiion experiment with the `"Time Series"` instruction, for example:

```python
experiment = dandeliion.Experiment(
  [
    (
      "Discharge at 1C until 3.8 V",
    ),
    (
      "Time series",
    ) * 3,
  ],
  period = "10 s",
)
```

Here we discharge the cell until 3.8V first, and then apply the drive cycle 3 times.

Note that the `period` does not need to be defined, as the solver will automatically adjust the time step based on the time points in the time series. However, if the user needs to refine the time step for the time series specifically, it can be done within the time series instruction:

```python
"Time series (1 s period)"
```

Finally, pass the time series to the client by using `extra_params` dictionary:

```python
# Current vs time
extra_params['Time series input'] = {
  "Time [s]": drive_cycle[:, 0].tolist(),
  "Current [A]": drive_cycle[:, 1].tolist(),
}
```

or

```python
# Power vs time
extra_params['Time series input'] = {
  "Time [s]": drive_cycle[:, 0].tolist(),
  "Power [W]": -drive_cycle[:, 1].tolist(),
}
```

### Method 2

*Use this method if PyBaMM is installed and you want to use PyBaMM’s experiment class (which performs basic validation of the experiment instructions).*

Define time series in the PyBaMM experiment:

```python
experiment = pybamm.Experiment(
  [
    (
      "Discharge at 1C until 3.8 V",
    ),
    (
      pybamm.step.current(drive_cycle),
    ) * 3,
  ],
  period = "10 s",
)
```

Unlike method 1, there is no need to update the `extra_params` dictionary.

## Starting the simulation

Start the simulation in the cloud using [`dandeliion.client.solve`](https://dandeliion-team.github.io/dandeliion-client/stubs/dandeliion.client.solve.html) method:

```python
solution = dandeliion.solve(
    simulator=simulator,
    params=params,
    experiment=experiment,
    extra_params=extra_params,
    is_blocking=True
)
```

The `solve` method parameters:

- `simulator` is the [`dandeliion.client.Simulator`](https://dandeliion-team.github.io/dandeliion-client/stubs/dandeliion.client.Simulator.html) object that stores the API key and URL, required.
- `params` refers to the BPX file (or `dict` or object), required. See [Simulation parameters and models](#simulation-parameters-and-models).
- `experiment` is optional (”1C discharge for 1 hour or until the `"Lower voltage cut-off [V]"` from BPX” will be used by default).
- `extra_params` is optional (initial conditions from the BPX, fully charged state, and single cell Newman model with constant temperature will be used by default).
- `is_blocking` is optional (default is `True`). It determines whether the `solve` command is blocking until computation has finished or returns right away. In the latter case, the `Solution` object may still point to an unfinished run (its status can be checked by printing `solution.status`).

The `solve` method returns [`dandeliion.client.Solution`](https://dandeliion-team.github.io/dandeliion-client/stubs/dandeliion.client.Solution.html) object that can be used to get access to the solution for further analysis and plotting, and also provides several helper methods and properties.

To get the simulation status:

```python
print(solution.status)
```

Possible `solution.status` values:

| `solution.status`  | Description |
| --- | --- |
| `queued`  | The simulation is in the queue and will be started as soon as possible |
| `running` | The simulation is currently running (use `solution.log` to get more details) |
| `success` | The simulation completed successfully |
| `failed`  | The simulation has failed. Print `solution.log` for more details. |

To get the simulation log, which can contain warnings, error messages, and other simulation-related information, use:

```python
print(solution.log)
```

This can be called during the simulation (in non-blocking mode).

## Running the simulation in non-blocking mode

In many cases, it's useful to run the simulation in **non-blocking mode** by passing `is_blocking=False` to the `solve` function. In this mode, `solve` immediately returns a solution object, even if the simulation is still running (or queued).

The user can request the simulation status and the backend logs by calling `solution.status` and `solution.log`.

If the user wants the program to wait for the simulation to finish, this can be done by calling

```python
solution.join()
```

This will block execution until the simulation finishes. If the simulation has already completed, `join()` returns immediately.

If there is a chance that the user’s connection will drop for any reason, the user can save the current solution object to a file. This file can later be used to reconnect to the simulation on the server and retrieve the latest updates:

```python
solution_file = 'solution.json'

# Save solution object
solution.dump(solution_file)

...

# Restore solution (reconnect to the server)
restored_solution = dandeliion.Simulator.restore(solution_file, api_url=api_url, api_key=api_key)
```

After reloading, `restored_solution` will point to a new solution object representing the simulation.

## Accessing simulation results

To print all available keys (outputs) in the solution object:

```python
for key in sorted(solution.keys()):
    print(key)
```

Currently available outputs:

```txt
Current [A]
Electrolyte concentration [mol.m-3]
Electrolyte potential [V]
Electrolyte x-coordinate [m]
Temperature [K]
Time [s]
Voltage [V]
X-averaged negative electrode exchange current density [A.m-2]
X-averaged negative electrode potential [V]
X-averaged negative electrode surface concentration [mol.m-3]
X-averaged positive electrode exchange current density [A.m-2]
X-averaged positive electrode potential [V]
X-averaged positive electrode surface concentration [mol.m-3]
```

To get access to the particular output, for example, to the voltage vs time vector:

```python
V_vs_t = solution['Voltage [V]']
```

To print the **final** values of time, voltage, and temperature:

```python
print(f"Final time [s]: {solution['Time [s]'][-1]}")
print(f"Final voltage [V]: {solution['Voltage [V]'][-1]}")
print(f"Final temperature [K]: {solution['Temperature [K]'][-1]}")
```

To plot the current and voltage vs time. Here we access scalar values vs time:

```python
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
```

To plot the concentration in the electrolyte vs `x` at the last time step. Here we access spatially dependent values vs time:

```python
plt.plot(
    solution["Electrolyte x-coordinate [m]"] * 1e6,
    solution["Electrolyte concentration [mol.m-3]"][-1],
    label="Dandeliion",
)
plt.xlabel(r"x [$\mu$m]")
plt.title("Electrolyte conc. (end of experiment) [mol.m-3]")
plt.legend()
plt.show()
```

If the user needs the solution at the `t_eval` times, the following code can be used (works only correctly on columns with timeline data):

```python
t_eval = np.arange(0, 3600, 1)
V_vs_t_eval = solution["Voltage [V]"](t=t_eval)
```

This is a linear interpolation with constant extrapolation.

## Save and load simulation results

The entire solution object can be saved to a JSON file:

```python
solution.dump("solution.json")
```

And restored using

```python
restored_solution = dandeliion.Simulator.restore("solution.json")
```

## Useful links

BPX repo: [https://github.com/FaradayInstitution/BPX](https://github.com/FaradayInstitution/BPX)

BPX website: [https://bpxstandard.com/](https://bpxstandard.com/)

## Documentation, examples, and CHANGELOG

- Link to auto-generated documentation: [https://dandeliion-team.github.io/dandeliion-client/index.html](https://dandeliion-team.github.io/dandeliion-client/index.html).
- Ready to use examples are given in the [examples](https://github.com/dandeliion-team/dandeliion-client/tree/master/examples) directory of this repository.
- All notable user-facing changes to this project are documented in the [CHANGELOG](https://github.com/dandeliion-team/dandeliion-client/blob/master/CHANGELOG.md).
