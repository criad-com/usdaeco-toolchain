#!/pxrpythonsubst
from pathlib import Path
import sys
import unittest
from pxr import Plug, Sdf, Usd, UsdValidation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
Plug.Registry().RegisterPlugins(str(ROOT / "usdAecoExampleValidators"))
Plug.Registry().RegisterPlugins(str(ROOT / "usdAecoExample"))


class TestValidators(unittest.TestCase):
    def test_InvalidDriver(self):
        stage = Usd.Stage.CreateInMemory()
        prim = stage.DefinePrim("/Example", "Xform")
        prim.CreateAttribute("aeco:example:driver", Sdf.ValueTypeNames.Double).Set(-1)
        validator = UsdValidation.ValidationRegistry().GetOrLoadValidatorByName(
            "usdAecoExampleValidators:DriverChecker")
        self.assertEqual([e.GetName() for e in validator.Validate(prim)], ["InvalidDriver"])
        prim.GetAttribute("aeco:example:driver").Set(1)
        self.assertEqual(validator.Validate(prim), [])

    def test_MissingDefaultPrim(self):
        stage = Usd.Stage.CreateInMemory()
        validator = UsdValidation.ValidationRegistry().GetOrLoadValidatorByName(
            "usdAecoExampleValidators:StageChecker")
        self.assertEqual([e.GetName() for e in validator.Validate(stage)], ["MissingDefaultPrim"])
        stage.SetDefaultPrim(stage.DefinePrim("/Example", "Xform"))
        self.assertEqual(validator.Validate(stage), [])


if __name__ == "__main__":
    unittest.main()
