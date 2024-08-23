import collections
import functools
import logging
import os
import typing

import ldap3

from . import errors, settings, user, utils

logger = logging.getLogger(__name__)


class SLURMSyncer:
    """Sync users' SLURM Accounts."""

    def __init__(self) -> None:
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
    def all_ldap_users(self) -> typing.Generator[dict[str, typing.Any], None, None]:
        """Get the list of users from the JASMIN accounts portal."""
        _status, _result, response, _request = self.ldap_conn.search(
            self.settings.ldap_search_base,
            self.settings.ldap_search_filter,
            attributes=ldap3.ALL_ATTRIBUTES,
        )
        return (x["attributes"] for x in response)

    @functools.cached_property
    def all_slurm_users(self) -> dict[str, set[str]]:
        args = [
            "sacctmgr",
            "show",
            "user",
            "withassoc",
            "format=user%50,account%50",
            "--noheader",
        ]
        cmd_output = utils.run_ratelimited(args, capture_output=True, check=True)
        # sacctmgr returns a newline seperated list of strings,
        # padded to 50 characters as specified above.
        # padding is necessary to ensure no account names are trucated.
        # we split on the newlines,
        # strip any whitespace then filter out any blank lines.
        accounts_strings = cmd_output.stdout.splitlines()
        accounts_pairs = (x.decode("utf-8").split() for x in accounts_strings)
        valid_pairs = (x for x in accounts_pairs if len(x) == 2)

        # Convert the user: account pairs into a dict of sets
        # for
        user_accounts = collections.defaultdict(set)
        for user, account in valid_pairs:
            user_accounts[user].add(account)

        return user_accounts

    def users(self) -> typing.Iterator[user.User]:
        """Get list of users whose SLURM accounts should be synced."""
        # Convert each user model to the user class.
        for ldap_user in self.all_ldap_users:
            username = ldap_user["cn"]
            yield user.User(
                username, ldap_user, self.all_slurm_users[username], self.settings
            )

    def sync(self) -> None:
        """Call sync on each user in turn."""
        for user in self.users():
            try:
                user.sync_slurm_accounts()
            except errors.UserSyncError:
                logger.warning("User %s failed to sync.", user.username)
