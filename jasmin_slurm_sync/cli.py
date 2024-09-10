import pathlib

import tap


class SyncArgParser(tap.Tap):
    """Utility to sync SLURM accounts with LDAP tags."""

    config: pathlib.Path = pathlib.Path("config.toml")
    dry_run: bool = False
    run_forever: bool = False
