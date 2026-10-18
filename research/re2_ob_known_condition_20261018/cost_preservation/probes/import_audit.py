"""Locate optional pandas imports without importing pandas or fitting a solver."""
import builtins
import json
from pathlib import Path
import sys
import traceback

sys.dont_write_bytecode = True
original = builtins.__import__
events = []


def checked_import(name, *args, **kwargs):
    if name == "pandas" or name.startswith("pandas."):
        events.append({"name": name, "stack": traceback.format_stack(limit=40)})
        raise ImportError("pandas explicitly unavailable in cost-preservation experiment")
    return original(name, *args, **kwargs)


builtins.__import__ = checked_import
try:
    import numpy as np
    from native_runtime import HawkesADM4
    from tick.prox import ProxNuclear
finally:
    builtins.__import__ = original
    with Path(__file__).with_name("import_isolated.json").open("x") as stream:
        json.dump({"pandas_loaded": "pandas" in sys.modules, "events": events},
                  stream, indent=2)
assert "pandas" not in sys.modules
print("NUMERICS_IMPORT_AUDIT_PASS", len(events), flush=True)
