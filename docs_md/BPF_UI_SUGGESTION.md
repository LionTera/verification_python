# BPF Verification UI Suggestion

## Recommendation

Use `PySide6`, not `PyQt4`.

Reason:

- `PyQt4` is obsolete
- `PySide6` is current and easier to justify for a new internal tool
- the verification flow already depends on modern Python tooling, so a current Qt binding is the right fit

## UI Goal

The UI should not replace the verification logic.

It should be a front-end over the existing flow:

- choose test type
- choose traffic parameters
- preview the exact command
- run the selected test
- inspect console output
- inspect generated artifacts

That keeps one source of truth:

- the pytest tests and Python helpers remain the verification engine
- the UI only drives them

## Suggested Main Screens

### 1. Run Configuration

Inputs:

- test selection
- protocol mode
- number of unique packets
- packet count
- loss percent
- error level
- RNG seed
- run ID
- report on/off
- waveform on/off
- full artifacts on/off

### 2. Command Preview

Show the exact command before the run.

That is important because:

- advanced users can still run the same command in a terminal
- the UI remains transparent

### 3. Run Output

Live console output from pytest:

- packet prints
- progress lines
- pass/fail result

### 4. Artifacts Panel

Show generated:

- CSV traces
- Markdown reports
- VCD waveforms

The first useful action is simply:

- show artifact path on click

Later it can grow into:

- open report
- open waveform
- filter by run ID

## Why This UI Shape Fits The Current Repo

The current environment is already organized around:

- pytest tests
- CLI parameters
- generated reports
- generated waveforms

So the cleanest UI is:

- parameter editor
- command launcher
- artifact browser

not:

- a separate verification engine inside the GUI

## Initial Prototype

A starter prototype was added here:

- `tools/bpf_verification_ui.py`

It currently provides:

- test selection
- protocol selection
- packet-count / unique-packet controls
- loss-percent control
- error-level control
- seed and run ID fields
- command preview
- pytest run button
- live run output
- artifact list refresh

## Run The Prototype

Example:

```bash
python tools/bpf_verification_ui.py
```

Prerequisite:

```bash
pip install PySide6
```

## Suggested Next Improvements

If this UI is kept, the next useful additions are:

- packet generator preview execution inside the UI
- one-row-per-packet result table from the report
- open report and open waveform buttons
- saved presets for common runs
- a dedicated golden-model view:
  - expected loss cycles
  - actual loss cycles
  - comparison status
- waveform watch helpers:
  - IPv4 protocol word
  - destination port word
  - packet loss events

## Suggested Visual Layout

Left side:

- run configuration
- packet generator controls
- artifact list

Right side:

- command preview
- live console output

This matches the current workflow:

- configure
- run
- inspect artifacts

## Engineering Note

This UI should stay thin.

The rule should be:

- verification logic lives in tests and shared Python modules
- UI only reads parameters and launches the existing flow

That avoids creating two parallel systems.
