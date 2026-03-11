# Future Test Simulator UI

## Purpose

This document outlines the design goals and architecture for a **future graphical test simulator UI** for the hardware module under development.
The UI will provide an interactive environment to test, debug, and visualize the behavior of the RTL module through the Python simulation infrastructure built around PyMTL.

This document is intentionally forward-looking so the repository structure and APIs created today remain compatible with the UI when it is implemented later.

---

# Goals

The simulator UI will allow developers and testers to:

* Run simulations interactively
* Inject inputs into the DUT (Device Under Test)
* Step through simulation cycles
* Run predefined test vectors
* Inspect outputs in real time
* Visualize signal waveforms
* Log and export test results
* Debug data flow through the system

The UI will act as a **frontend layer**, while the actual simulation logic will remain inside a reusable Python simulation API.

---

# Architecture Overview

The system will follow a layered architecture to keep responsibilities separated.

```
UI
 |
 v
Simulation API
 |
 v
PyMTL Wrapper
 |
 v
Verilog DUT (RTL)
```

## Layer Description

### 1. UI Layer

Responsible only for presentation and user interaction.

Examples of features:

* input controls
* simulation controls
* waveform viewer
* logs and status messages
* test result summaries

The UI should **never directly manipulate the DUT**.

Instead it calls functions in the simulation API.

---

### 2. Simulation API

This layer acts as a stable interface between the UI and the hardware model.

Responsibilities:

* initialize the DUT
* reset the simulation
* perform simulation steps
* run simulations for N cycles
* collect signal traces
* export results

Example conceptual interface:

```python
class Simulator:

    def reset(self):
        pass

    def step(self, inputs: dict) -> dict:
        pass

    def run(self, cycles: int):
        pass

    def get_trace(self):
        pass

    def export_vcd(self, path):
        pass
```

Both the **UI** and **automated tests** will use this API.

---

### 3. PyMTL Wrapper

This layer connects the Python environment to the Verilog module.

Responsibilities:

* expose DUT ports
* integrate Verilog simulation via PyMTL
* translate Python inputs into signal assignments
* read signal values back from the DUT

Wrappers are typically generated automatically from the Verilog module interface.

Generated files will live in:

```
pymtl/wrappers/generated/
```

Manual adapters can be placed in:

```
pymtl/wrappers/manual/
```

---

### 4. Verilog DUT

The actual hardware module located under:

```
rtl/
```

This contains the RTL implementation of the system under test.

---

# Planned Features

## Simulation Controls

The UI will allow users to:

* Reset DUT
* Step 1 cycle
* Run N cycles
* Run until condition
* Load test vectors
* Pause simulation

Example controls:

```
[ Reset ] [ Step ] [ Run 100 ] [ Stop ]
```

---

## Input Injection

Users should be able to manually set input values.

Example:

```
Inputs
--------------------------------
in_valid     [ 0 / 1 ]
in_data      [ 0x00000000 ]
config_reg   [ 0x00000010 ]
```

Inputs are applied before each simulation cycle.

---

## Output Monitoring

Outputs will be displayed in real time.

Example:

```
Outputs
--------------------------------
out_valid    1
out_data     0x12345678
status       OK
```

---

# Waveform Visualization

A future version of the UI will include waveform visualization.

The waveform viewer will display signals over time.

Example signals:

```
in_valid
in_data
out_valid
out_data
```

Example timeline:

```
Cycle →   0   1   2   3   4

in_valid  ────████████────
in_data   00  10  11  00
out_valid ───────████████
out_data  00  00  10  11
```

The UI should support:

* zooming
* scrolling
* cursor inspection
* bus display
* grouping signals

---

# Trace Recording

The simulator API will record signal values during simulation.

Example trace format:

```python
{
    "cycles": [0,1,2,3],
    "signals": {
        "in_valid": [0,1,1,0],
        "in_data":  [0,10,11,0],
        "out_valid":[0,0,1,1],
        "out_data": [0,0,10,11]
    }
}
```

This data can be used to:

* render waveforms
* debug runs
* export traces
* compare expected vs actual results

---

# Waveform Export

The simulator should support exporting traces to standard formats such as:

* VCD
* JSON
* CSV

Example usage:

```
sim.export_vcd("trace.vcd")
```

This allows external tools to inspect waveforms if needed.

---

# Test Vector Support

The simulator UI should support loading test vectors.

Example vector format (JSON):

```json
[
  {"in_valid":0, "in_data":0},
  {"in_valid":1, "in_data":10},
  {"in_valid":1, "in_data":11},
  {"in_valid":0, "in_data":0}
]
```

The simulator can run vectors sequentially.

Results can be compared against expected outputs.

---

# Logging and Debugging

The UI will include a log panel showing:

* simulation events
* input changes
* detected errors
* assertions
* warnings

Example:

```
[00:00:01] Reset applied
[00:00:02] Step cycle 1
[00:00:02] Input in_data=0x10
[00:00:03] Output out_valid=1
```

---

# Possible UI Technologies

The UI technology is not fixed yet. Possible options include:

## Desktop UI

Python based frameworks:

* PyQt / PySide
* Tkinter
* Textual (terminal UI)

Advantages:

* direct Python integration
* simpler architecture

---

## Web UI

Python backend with web frontend.

Possible stack:

Backend:

* FastAPI
* Flask

Frontend:

* HTML + JavaScript
* React
* visualization libraries for waveforms

Advantages:

* accessible from browser
* easier complex UI layouts
* easier remote access

---

# Repository Integration

The UI will likely live in a new directory:

```
ui/
```

Possible structure:

```
ui/
 ├── desktop/
 ├── web/
 └── common/
```

The UI will interact with:

```
sim/core/simulator.py
```

which contains the simulation API.

---

# Development Roadmap

Recommended development phases:

## Phase 1

Create simulation API

* reset
* step
* run
* collect outputs

## Phase 2

Add trace recording

* record signal values per cycle
* export trace data

## Phase 3

Create basic UI

* simulation controls
* input fields
* output display

## Phase 4

Waveform viewer

* signal traces
* zoom and cursor
* signal selection

## Phase 5

Advanced debugging

* signal hierarchy
* breakpoints
* long simulation runs

---

# Design Principles

The UI should follow these principles:

* **separation of concerns**
* **simulation logic independent from UI**
* **stable simulator API**
* **support automated testing**
* **easy extensibility**

---

# Long Term Vision

The final simulator UI should provide a development environment similar to lightweight hardware simulators, allowing:

* rapid experimentation
* debugging signal flow
* validating algorithms
* testing packet flows
* visualizing hardware behavior

All while remaining tightly integrated with the Python-based simulation environment.

---
