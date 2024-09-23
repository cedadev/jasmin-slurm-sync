import unittest
import unittest.mock

import jasmin_slurm_sync.sync
import jasmin_slurm_sync.user
import ldap3

from . import base, fixtures


class TestUser(base.BaseSlurmSyncTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _status, _result, response, _request = cls.ldap_conn.search(
            cls.settings.ldap_search_base,
            cls.settings.ldap_search_filter,
            attributes=ldap3.ALL_ATTRIBUTES,
        )
        raise Exception(response)

    def test_create_syncer(self):
        """Check that it is possible in instantiate a syncer object."""
        jasmin_slurm_sync.sync.SLURMSyncer(
            self.settings,
            self.args,
            ldap_server=self.ldap_server,
            ldap_conn=self.ldap_conn,
        )

    # def test_create_user(self):
    #    jasmin_slurm_sync.user.User(
    #        self.ldap_user, self.slurm_accounts, self.settings, self.args
    #    )
