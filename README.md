    # pymtl-verilog-project

    Starter repository for a Verilog + PyMTL workflow.

    ## Intended structure

    - `rtl/` - Verilog/SystemVerilog source
    - `pymtl/` - PyMTL wrappers, adapters, and helper components
    - `sim/` - simulation harnesses and quick runners
    - `tests/` - pytest-based automated tests
    - `tools/` - developer utilities such as wrapper generation and repo inspection
    - `scripts/` - shell helpers for setup and test execution
    - `docs/` - architecture notes and design documentation

    ## Typical flow

    ```text
    rtl/ -> tools/gen_pymtl_wrapper.py -> pymtl/wrappers/generated/ -> sim/ + tests/
    ```

    ## Quick start

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    pytest
    ```

    ## Notes

    - Generated wrappers should go in `pymtl/wrappers/generated/`
    - Handwritten adapters or custom wrappers should go in `pymtl/wrappers/manual/`
    