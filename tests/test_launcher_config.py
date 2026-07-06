import tempfile
import unittest
from pathlib import Path

from launcher.config_store import (
    LauncherConfig,
    ProjectConfig,
    assign_missing_ports,
    find_free_port,
    load_config,
    project_from_registration,
    save_config,
    validate_config,
    validate_project,
    drop_broken_sample_projects,
)


class LauncherConfigTest(unittest.TestCase):
    def test_round_trips_project_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "projects.json"
            folder = Path(tmp) / "app"
            folder.mkdir()
            config = LauncherConfig(
                projects=[
                    ProjectConfig(
                        name="Test App",
                        folder=str(folder),
                        setup=["echo setup"],
                        run="python app.py",
                        url="http://127.0.0.1:9000",
                        readiness={"type": "port", "port": 9000, "timeout_seconds": 5},
                        env={"A": "B"},
                    )
                ]
            )
            save_config(config, path)

            loaded = load_config(path)

            self.assertEqual(loaded.projects[0].name, "Test App")
            self.assertEqual(loaded.projects[0].setup, ["echo setup"])
            self.assertEqual(loaded.projects[0].env["A"], "B")

    def test_validation_reports_missing_folder_friendly_error(self):
        project = ProjectConfig(name="Missing", folder="C:\\definitely\\missing", run="python app.py")

        errors = validate_project(project)

        self.assertTrue(any("folder does not exist" in error for error in errors))

    def test_assigns_unique_ports_from_configured_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            config = LauncherConfig(
                settings={"port_range_start": 8120, "port_range_end": 8122},
                projects=[
                    ProjectConfig(name="One", folder=str(folder), run="python app.py"),
                    ProjectConfig(name="Two", folder=str(folder), run="python app.py"),
                ],
            )

            changed = assign_missing_ports(config)

            self.assertTrue(changed)
            self.assertEqual(config.projects[0].port, 8120)
            self.assertEqual(config.projects[1].port, 8121)
            self.assertEqual(config.projects[0].url, "http://localhost:8120")

    def test_duplicate_ports_are_flagged_inline(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            config = LauncherConfig(
                projects=[
                    ProjectConfig(name="One", folder=str(folder), run="python app.py", port=8100),
                    ProjectConfig(name="Two", folder=str(folder), run="python app.py", port=8100),
                ]
            )

            errors = validate_config(config)

            self.assertIn("One", errors)
            self.assertIn("Two", errors)

    def test_registration_block_auto_assigns_port(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            config = LauncherConfig(settings={"port_range_start": 8130, "port_range_end": 8131})
            project = project_from_registration(
                {
                    "name": "Imported",
                    "folder": str(folder),
                    "setup": [],
                    "run": "python app.py",
                    "wants_browser": True,
                    "port": "auto",
                },
                config,
            )

            self.assertEqual(project.port, 8130)
            self.assertEqual(project.url, "http://localhost:8130")

    def test_broken_sample_only_config_becomes_welcome_state(self):
        config = LauncherConfig(
            projects=[
                ProjectConfig(
                    name="Sample Python Server",
                    folder="C:\\Users\\muham\\AppData\\Local\\Temp\\_MEI123\\sample-project",
                    run="python server.py",
                    port=8100,
                )
            ]
        )

        changed = drop_broken_sample_projects(config)

        self.assertTrue(changed)
        self.assertEqual(config.projects, [])


if __name__ == "__main__":
    unittest.main()

