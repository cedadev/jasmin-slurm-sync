import pathlib
import unittest
import unittest.mock

import jasmin_slurm_sync.cli
import jasmin_slurm_sync.settings
import ldap3

from . import fixtures


@unittest.mock.patch("subprocess.run", fixtures.subprocess_run_fixture)
class BaseSlurmSyncTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.settings = jasmin_slurm_sync.settings.load_settings(
            pathlib.Path(__file__).parent / "../config.example.toml"
        )
        cls.args = jasmin_slurm_sync.cli.SyncArgParser().parse_args([])

        cls.ldap_server = ldap3.Server(
            "my_fake_server",
            get_info=ldap3.OFFLINE_SLAPD_2_4,
        )
        cls.ldap_conn = ldap3.Connection(
            cls.ldap_server,
            client_strategy=ldap3.MOCK_SYNC,
            # auto_bind=True,
            auto_encode=True,
            check_names=True,
        )
        cls.ldap_conn.strategy.thread_safe = True
        cls.ldap_conn.strategy.entries_from_json(
            pathlib.Path(__file__).parent / "fixtures/ldap_fixture.json",
        )
        cls.ldap_conn.bind()

    def setup(self) -> None:
        # pylint: disable=attribute-defined-outside-init
        pass
