from . import cli, errors
from . import settings as settings_module
from . import utils


class Account:
    """Representation of SLURM accounts themselves."""

    def __init__(
        self,
        account_tuple: tuple[str, str],
        expected_slurm_accounts: dict[str, tuple[str, str, str]],
        existing_slurm_accounts: dict[str, tuple[str, str, str]],
        settings: settings_module.SyncSettings,
        args: cli.SyncArgParser,
    ):
        self.settings = settings
        self.args = args

        self.parent_name = account_tuple[0]
        self.account_name = account_tuple[1]

        self.expected_slurm_accounts = expected_slurm_accounts
        self.existing_slurm_accounts = existing_slurm_accounts

    def create_account(self):
        pass

    def deactivate_account(self):
        pass

    def update_fairshare(self):
        pass

    def update_parent(self):
        pass

    def sync_account(self):
        """Sync account to make sure SLURM is the same as the projects portal."""
        # If it doesn't exist, create it.
        if self.existing_slurm_accounts.get(self.account_name, None) is None:
            self.create_account()
        # If it does exist but shouldn't, deactivate it.
        elif self.expected_slurm_accounts.get(self.account_name, None) is None:
            self.deactivate_account()
        # Otherwise, make sure the accounts parent and fairshare are correct.
        else:
            existing = self.existing_slurm_accounts[self.account_name]
            expected = self.expected_slurm_accounts[self.account_name]
            # If the account's parent is not correct, update it.
            if existing[0] != expected[0]:
                self.update_parent()
            # If the account's fairshare is not correct, update it.
            if existing[2] != existing[2]:
                self.update_fairshare()
