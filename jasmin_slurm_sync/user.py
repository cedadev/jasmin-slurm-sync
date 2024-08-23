import functools
import itertools
import logging
import pwd
import time
import typing

from . import errors
from . import settings as settings_module
from . import utils

logger = logging.getLogger(__name__)


class User:
    """Class which represents a JASMINUser and their SLURM Accounts."""

    def __init__(
        self,
        username: str,
        ldap_user: dict[str, typing.Any],
        slurm_accounts: set[str],
        settings: settings_module.SettingsSchema,
    ) -> None:
        self.ldap_user = ldap_user
        self.slurm_accounts = slurm_accounts
        self.username: str = self.ldap_user["cn"][0]
        self.settings: settings_module.SettingsSchema = settings

        self.managed_slurm_accounts = set(
            itertools.chain.from_iterable(self.settings.ldap_tag_mapping.values())
        )

    @functools.cached_property
    def existing_slurm_accounts(self) -> set[str]:
        """Get the list of SLURM accounts which the user has already."""
        return self.slurm_accounts

    @functools.cached_property
    def expected_slurm_accounts(self) -> set[str]:
        """Get the list of SLURM accounts which the user is expected to have."""
        known_tags = self.settings.ldap_tag_mapping.keys()
        expected_tags = itertools.chain.from_iterable(
            self.settings.ldap_tag_mapping[x]
            for x in self.ldap_user["description"]
            if x in known_tags
        )
        return set(expected_tags)

    @property
    def to_be_added(self) -> set[str]:
        """Return set of acccounts which user is expected to have but doesn't."""
        return self.expected_slurm_accounts - self.existing_slurm_accounts

    @property
    def to_be_removed(self) -> set[str]:
        """Return set of accounts which use has but shouldn't."""
        return self.existing_slurm_accounts - self.expected_slurm_accounts

    def add_user_to_account(self, account: str) -> None:
        """Add the user to a given SLURM account."""
        if account in self.managed_slurm_accounts:
            args = [
                "sacctmgr",
                "-i",
                "add",
                "user",
                self.username,
                f"account={account}",
            ]
            logger.info("Adding user %s to account %s", self.username, account)
            # utils.run_ratelimited(args, capture_output=False, check=True)
        else:
            logger.info(
                "Not adding %s to %s, because account is not managed.",
                self.username,
                account,
            )

    def remove_user_from_account(self, account: str) -> None:
        """Remove the user from a given SLURM account."""
        if account in self.managed_slurm_accounts:
            args = [
                "sacctmgr",
                "-i",
                "remove",
                "user",
                self.username,
                f"account={account}",
            ]
            logger.info("Removing user %s from account %s", self.username, account)
            # utils.run_ratelimited(args, capture_output=False, check=True)
        else:
            logger.info(
                "Not removing %s from %s, because account is not managed.",
                self.username,
                account,
            )

    def sync_slurm_accounts(self) -> None:
        """Do a full sync of the user's SLURM accounts."""
        # If the user does not exist in linux, SLURM accounts should not be synced for the user.
        try:
            pwd.getpwnam(self.username)
        except KeyError as err:
            logger.warning(
                f"Unix User %s does not exist. Not syncing SLURM accounts.",
                self.username,
            )
            raise errors.NoUnixUser from err

        # Check the user is going to be in the required slurm accounts.
        if not self.expected_slurm_accounts >= self.settings.required_slurm_accounts:
            logger.warning(
                f"User is not in required accounts: %s so won't be synced.",
                self.expected_slurm_accounts - self.settings.required_slurm_accounts,
            )
            raise errors.NotInRequiredAccounts

        # Do the sync.
        for account in self.to_be_added:
            self.add_user_to_account(account)
        for account in self.to_be_removed:
            self.remove_user_from_account(account)
