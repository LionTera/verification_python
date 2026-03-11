    #!/usr/bin/env python3
    import argparse
    from pathlib import Path

    TEMPLATE = """module {module_name} (
        input  wire clk,
        input  wire reset
    );

    endmodule
    """

    def main():
        ap = argparse.ArgumentParser(description="Create a basic Verilog module stub.")
        ap.add_argument("module_name", help="Module name")
        ap.add_argument("--subdir", default="core", help="Subdirectory under rtl/")
        args = ap.parse_args()

        root = Path(__file__).resolve().parents[1]
        out_dir = root / "rtl" / args.subdir
        out_dir.mkdir(parents=True, exist_ok=True)

        out_file = out_dir / f"{args.module_name}.v"
        if out_file.exists():
            print(f"Exists: {out_file}")
            return

        out_file.write_text(TEMPLATE.format(module_name=args.module_name), encoding="utf-8")
        print(f"Created: {out_file}")

    if __name__ == "__main__":
        main()
    