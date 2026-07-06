import importlib
import pkgutil
import unittest

import launcher


class LauncherImportTest(unittest.TestCase):
    def test_every_launcher_module_imports(self):
        failures = []
        for module in pkgutil.walk_packages(launcher.__path__, launcher.__name__ + "."):
            try:
                importlib.import_module(module.name)
            except Exception as exc:
                failures.append(f"{module.name}: {exc}")
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
