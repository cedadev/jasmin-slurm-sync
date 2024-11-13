import pathlib
import unittest

import jasmin_slurm_sync.settings

from . import cases


class SettingsTestCase(unittest.TestCase):
    """Test loading settings from disk."""

    def test_settings_load(self):
        """Test the settings module can load settings from disk."""
        settings = jasmin_slurm_sync.settings.load_settings(
            pathlib.Path(__file__).parent / "config.example.toml"
        )
        self.assertIsInstance(settings, jasmin_slurm_sync.settings.SyncSettings)
        self.assertEqual(settings.list_users_role, "category/service")
