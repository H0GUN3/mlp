"""Load installed ADM4 unchanged without unrelated pandas-dependent learners."""
import importlib
from pathlib import Path
import sys
from types import ModuleType

import tick


def package(name, path):
    """Namespace only; numerical modules still execute their installed source."""
    module = ModuleType(name)
    module.__path__ = [str(path)]
    module.__package__ = name
    sys.modules[name] = module
    parent, _, child = name.rpartition(".")
    setattr(sys.modules[parent], child, module)
    return module


assert tick.__file__ is not None
tick_path = Path(tick.__file__).parent
base_model = package("tick.base_model", tick_path / "base_model")
for module_name, class_name in (
        ("model", "Model"), ("model_first_order", "ModelFirstOrder"),
        ("model_second_order", "ModelSecondOrder"),
        ("model_self_concordant", "ModelSelfConcordant"),
        ("model_lipschitz", "ModelLipschitz")):
    loaded = importlib.import_module("tick.base_model." + module_name)
    setattr(base_model, class_name, getattr(loaded, class_name))
    if module_name == "model":
        for constant in vars(loaded):
            if constant.isupper():
                setattr(base_model, constant, getattr(loaded, constant))
solver = package("tick.solver", tick_path / "solver")
solver_base = package("tick.solver.base", tick_path / "solver/base")
loaded_solver = importlib.import_module("tick.solver.base.solver")
setattr(solver_base, "Solver", loaded_solver.Solver)
hawkes = package("tick.hawkes", tick_path / "hawkes")
for subpackage in ("model", "simulation"):
    module = importlib.import_module("tick.hawkes." + subpackage)
    for name in module.__all__:
        setattr(hawkes, name, getattr(module, name))
inference = package("tick.hawkes.inference", tick_path / "hawkes/inference")
base = package("tick.hawkes.inference.base", tick_path / "hawkes/inference/base")
learner = importlib.import_module("tick.hawkes.inference.base.learner_hawkes_noparam")
setattr(base, "LearnerHawkesNoParam", learner.LearnerHawkesNoParam)
adm4 = importlib.import_module("tick.hawkes.inference.hawkes_adm4")
HawkesADM4 = adm4.HawkesADM4
setattr(hawkes, "HawkesADM4", HawkesADM4)
setattr(inference, "HawkesADM4", HawkesADM4)
if "pandas" in sys.modules:
    raise RuntimeError("Isolated native imports unexpectedly loaded pandas")


if __name__ == "__main__":
    print("NUMERICS_NATIVE_IMPORT_PASS", HawkesADM4.__module__, flush=True)
