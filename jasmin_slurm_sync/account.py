import collections
import logging

from . import cli, errors
from . import settings as settings_module
from . import utils

logger = logging.getLogger(__name__)

AccountInfo = collections.namedtuple("AccountInfo", ["name", "parent", "fairshare"])


class Account:
    """Representation of SLURM accounts themselves."""

    def __init__(
        self,
        account_name: str,
        expected_slurm_accounts: set[AccountInfo],
        existing_slurm_accounts: set[AccountInfo],
        settings: settings_module.SyncSettings,
        args: cli.SyncArgParser,
    ):
        self.settings = settings
        self.args = args

        self.account_name = account_name

        # Find the details of the existing and expected accounts.
        if existing := [
            x for x in existing_slurm_accounts if x.name == self.account_name
        ]:
            [self.existing] = existing
        else:
            self.existing = None
        if expected := [
            x for x in expected_slurm_accounts if x.name == self.account_name
        ]:
            [self.expected] = expected
        else:
            self.expected = None

    def create_account(self):
        if account not in self.settings.unmanaged_accounts:
            args = [
                "sacctmgr",
            ]
            if self.args.dry_run:
                logger.warning(
                    "Would create account %s, but we are in dry run mode so not doing anything.",
                    self.account_name,
                )
            else:
                cmd_output = utils.run_ratelimited(
                    args, capture_output=True, check=True
                )
                logger.info("Created account %s", self.account_name)
                if cmd_output.stderr:
                    logger.error(cmd_output.stderr)
                if cmd_output.stdout:
                    logger.debug(cmd_output.stdout)
        else:
            logger.info(
                "Not creating account %s, because account is not managed.",
                self.account_name,
            )

    def deactivate_account(self):
        if account not in self.settings.unmanaged_accounts:
            args = [
                "sacctmgr",
            ]
            if self.args.dry_run:
                logger.warning(
                    "Would deactivate account %s, but we are in dry run mode so not doing anything.",
                    self.account_name,
                )
            else:
                cmd_output = utils.run_ratelimited(
                    args, capture_output=True, check=True
                )
                logger.info("Deactivated account %s", self.account_name)
                if cmd_output.stderr:
                    logger.error(cmd_output.stderr)
                if cmd_output.stdout:
                    logger.debug(cmd_output.stdout)
        else:
            logger.info(
                "Not deactivating account %s, because account is not managed.",
                self.account_name,

    def update_fairshare(self):
        if account not in self.settings.unmanaged_accounts:
            args = [
                "sacctmgr",
            ]
            if self.args.dry_run:
                logger.warning(
                    "Would change fairshare of account %s to %s, but we are in dry run mode so not doing anything.",
                    self.account_name,
                    self.expected.fairshare,
                )
            else:
                cmd_output = utils.run_ratelimited(
                    args, capture_output=True, check=True
                )
                logger.info("Changed fairshare of account %s to %s", self.account_name, self.expected.fairshare)
                if cmd_output.stderr:
                    logger.error(cmd_output.stderr)
                if cmd_output.stdout:
                    logger.debug(cmd_output.stdout)
        else:
            logger.info(
                "Not changing fairshare of account %s to %s, because account is not managed.",
                self.account_name,
                self.expected.fairshare,
                )

    def update_parent(self):
        if account not in self.settings.unmanaged_accounts:
            args = [
                "sacctmgr",
            ]
            if self.args.dry_run:
                logger.warning(
                    "Would change parent of account %s to %s, but we are in dry run mode so not doing anything.",
                    self.account_name,
                    self.expected.parent,
                )
            else:
                cmd_output = utils.run_ratelimited(
                    args, capture_output=True, check=True
                )
                logger.info("Changed parent of account %s to %s.", self.account_name, self.expected.parent)
                if cmd_output.stderr:
                    logger.error(cmd_output.stderr)
                if cmd_output.stdout:
                    logger.debug(cmd_output.stdout)
        else:
            logger.info(
                "Not changing parent of account %s to %s, because account is not managed.",
                self.account_name,
                self.expected.parent,
                )

    def sync_account(self):
        """Sync account to make sure SLURM is the same as the projects portal."""
        # If it doesn't exist, create it.
        if self.existing is None:
            self.create_account()
        # If it does exist but shouldn't, deactivate it.
        elif self.expected is None:
            self.deactivate_account()
        # Otherwise, make sure the accounts parent and fairshare are correct.
        else:
            # If the account's parent is not correct, update it.
            if self.existing.parent != self.expected.parent:
                self.update_parent()
            # If the account's fairshare is not correct, update it.
            if self.existing.fairshare != self.expected.fairshare:
                self.update_fairshare()
