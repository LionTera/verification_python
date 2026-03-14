import sys

def create_wrapper(mod_name, ports):
    """
    mod_name: str (e.g., 'full_adder_8bit')
    ports: list of tuples (name, direction, width)
    """
    wrapper = f"from pymtl3 import *\nfrom pymtl3.passes.backends.verilog import *\n\n"
    wrapper += f"class {mod_name.title().replace('_','')}( VerilogPlaceholder, Component ):\n"
    wrapper += f"    def construct( s ):\n"
    
    for name, direction, width in ports:
        ptype = "InPort" if direction == "in" else "OutPort"
        wrapper += f"        s.{name} = {ptype}( Bits{width} )\n"
    
    wrapper += f"\n        s.set_metadata( VerilogPlaceholderPass.src_file, '{mod_name}.v' )\n"
    
    with open(f"{mod_name}_wrapper.py", "w") as f:
        f.write(wrapper)
    print(f"Generated {mod_name}_wrapper.py")

# Example usage for the 8-bit adder:
if __name__ == "__main__":
    # You can eventually expand this to parse the .v file automatically
    create_wrapper("full_adder_8bit", [
        ("a", "in", 8), ("b", "in", 8), ("cin", "in", 1),
        ("sum", "out", 8), ("cout", "out", 1)
    ])