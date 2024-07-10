import functools
import os
import typing

import ldap3

from . import models, settings


class SLURMSyncer:
    """Sync users' SLURM Accounts."""

    def __init__(self):
        """Initialise a connection to the jasmin acounts portal."""
        self.settings = settings.SyncSettings()
        self.ldap_server = ldap3.Server(
            self.settings.ldap_server_addr,
            get_info=ldap3.ALL,
        )
        self.ldap_conn = ldap3.Connection(
            self.ldap_server,
            auto_bind=True,
            auto_encode=True,
            check_names=True,
            client_strategy=ldap3.SAFE_RESTARTABLE,
        )

    @functools.cached_property
    def all_ldap_users(self):
        """Get the list of users from the JASMIN accounts portal."""
        _status, _result, response, _request = self.ldap_conn.search(
            self.settings.ldap_search_base,
            self.settings.ldap_search_filter,
            attributes=ldap3.ALL_ATTRIBUTES,
        )
        return (x["attributes"] for x in response)

    def users(self) -> typing.Iterator[models.User]:
        """Get list of users whose SLURM accounts should be synced."""
        # Convert each user model to the user class.
        for ldap_user in self.all_ldap_users:
            yield models.User(ldap_user, self.settings)

    def sync(self) -> None:
        """Call sync on each user in turn."""
        for user in self.users():
            user.sync_slurm_accounts()
