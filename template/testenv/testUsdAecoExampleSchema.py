#!/pxrpythonsubst
import os
from pathlib import Path
import unittest
from pxr import Plug, Usd

ROOT = Path(__file__).resolve().parents[1]


class TestSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("CORE_PLUGIN_DIR"):
            Plug.Registry().RegisterPlugins(os.environ["CORE_PLUGIN_DIR"])
        Plug.Registry().RegisterPlugins(str(ROOT / "usdAecoExample"))

    def test_registry(self):
        self.assertIsNotNone(Usd.SchemaRegistry().FindAppliedAPIPrimDefinition("AecoExampleAPI"))

    def test_refusal(self):
        stage = Usd.Stage.CreateInMemory()
        self.assertFalse(stage.DefinePrim("/Material", "Material").CanApplyAPI("AecoExampleAPI"))


if __name__ == "__main__":
    unittest.main()
