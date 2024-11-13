"""Reusable test cases for jasmin-slurm-sync."""

import pathlib
import unittest

import jasmin_slurm_sync.cli


class CliArgsMixin(unittest.TestCase):
    """Mixin for when command line args are required."""

    def setUp(self) -> None:
        """Set a path to the example configuration."""
        args = jasmin_slurm_sync.cli.SyncArgParser()
        args.config = pathlib.Path(__file__).parent / "config.example.toml"
        args.dry_run = False
        args.run_forever = False
        self.args = args
