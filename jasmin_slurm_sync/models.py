import functools
import subprocess as sp
import typing

from . import settings as settings_module
import itertools


class User:
    """Class which represents a JASMINUser and their SLURM Accounts."""

    def __init__(
        self,
        ldap_user: dict[str, typing.Any],
        settings: settings_module.SettingsSchema,
    ) -> None:
        self.ldap_user = ldap_user
        self.username: str = self.ldap_user["cn"][0]
        self.settings: settings_module.SettingsSchema = settings

        self.managed_slurm_accounts = set(itertools.chain.from_iterable(self.settings.ldap_tag_mapping.values()))

    @functools.cached_property
    def existing_slurm_accounts(self) -> set[str]:
        """Get the list of SLURM accounts which the user has already."""
        args = [
            "sacctmgr",
            "show",
            "user",
            "withassoc",
            "format=account%50",
            "--noheader",
            self.username,
        ]
        cmd_output = sp.run(args, capture_output=True, check=True)
        # sacctmgr returns a newline seperated list of strings,
        # padded to 50 characters as specified above.
        # padding is necessary to ensure no account names are trucated.
        # we split on the newlines,
        # strip any whitespace then filter out any blank lines.
        accounts_strings = cmd_output.stdout.splitlines()
        accounts = set(x.decode("utf-8").strip() for x in accounts_strings)
        accounts = set(x for x in accounts if x)
        return accounts

    @functools.cached_property
    def expected_slurm_accounts(self) -> set[str]:
        """Get the list of SLURM accounts which the user is expected to have."""
        known_tags = self.settings.ldap_tag_mapping.keys()
        expected_tags = itertools.chain.from_iterable(self.settings.ldap_tag_mapping[x] for x in self.ldap_user['description'] if x in known_tags)
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
            args = ["sacctmgr", "-i", "add", "user", self.username, f"account={account}"]
            print(" ".join(args))
            # sp.run(args, capture_output=False, check=True)
        else:
            print(f"Not adding {self.username} to {account}, because {account} is not managed.")
            print(list(self.managed_slurm_accounts))

    def remove_user_from_account(self, account: str) -> None:
        """Remove the user from a given SLURM account."""
        if account in self.managed_slurm_accounts:
            args = ["sacctmgr", "-i", "remove", "user", self.username, f"account={account}"]
            print(" ".join(args))
            # sp.run(args, capture_output=False, check=True)
        else:
            print(f"Not removing {self.username} from {account}, because {account} is not managed.")

    def sync_slurm_accounts(self) -> None:
        """Do a full sync of the user's SLURM accounts."""
        for account in self.to_be_added:
            self.add_user_to_account(account)
        for account in self.to_be_removed:
            self.remove_user_from_account(account)
