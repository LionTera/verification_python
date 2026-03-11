    # Wrapper Generation

    Generated wrappers are expected to live under:

    - `pymtl/wrappers/generated/`

    Manual adjustments or higher-level adapters should live under:

    - `pymtl/wrappers/manual/`

    Recommended flow:

    1. Add Verilog files under `rtl/`
    2. Run `tools/gen_pymtl_wrapper.py`
    3. Review generated wrapper
    4. Add tests under `tests/`
    