import collections
import logging
import typing

from .. import cli
from .. import settings as settings_module
from .. import utils

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

        # Help out the type checker
        self.existing: typing.Optional[AccountInfo]
        self.expected: typing.Optional[AccountInfo]

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

    def create_account(self, expected: AccountInfo) -> None:
        if self.account_name not in self.settings.unmanaged_accounts:
            args = [
                "sacctmgr",
                "-i",
                "create",
                "account",
                f"name={self.account_name}",
                f"parent={expected.parent}",
                f"fairshare={expected.fairshare}",
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

    def deactivate_account(self) -> None:
        if self.account_name not in self.settings.unmanaged_accounts:
            args = [
                "sacctmgr",
                "-i",
                "modify",
                "account",
                "where",
                f"name={self.account_name}",
                "set",
                "maxjobs=0",
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
            )

    def update_fairshare(self, expected: AccountInfo) -> None:
        if self.account_name not in self.settings.unmanaged_accounts:
            args = [
                "sacctmgr",
                "-i",
                "modify",
                "account",
                "where",
                f"name={self.account_name}",
                "set",
                f"fairshare={expected.fairshare}",
            ]
            if self.args.dry_run:
                logger.warning(
                    "Would change fairshare of account %s to %s (currently %s), but we are in dry run mode so not doing anything.",
                    self.account_name,
                    expected.fairshare,
                    getattr(self.existing, "fairshare", None),
                )
            else:
                cmd_output = utils.run_ratelimited(
                    args, capture_output=True, check=True
                )
                logger.info(
                    "Changed fairshare of account %s to %s",
                    self.account_name,
                    expected.fairshare,
                )
                if cmd_output.stderr:
                    logger.error(cmd_output.stderr)
                if cmd_output.stdout:
                    logger.debug(cmd_output.stdout)
        else:
            logger.info(
                "Not changing fairshare of account %s to %s, because account is not managed.",
                self.account_name,
                expected.fairshare,
            )

    def update_parent(self, expected: AccountInfo) -> None:
        if self.account_name not in self.settings.unmanaged_accounts:
            args = [
                "sacctmgr",
                "-i",
                "modify",
                "account",
                "where",
                f"name={self.account_name}",
                "set",
                f"parent={expected.parent}",
            ]
            if self.args.dry_run:
                logger.warning(
                    "Would change parent of account %s to %s (currently %s), but we are in dry run mode so not doing anything.",
                    self.account_name,
                    expected.parent,
                    getattr(self.existing, "parent", None),
                )
            else:
                cmd_output = utils.run_ratelimited(
                    args, capture_output=True, check=True
                )
                logger.info(
                    "Changed parent of account %s to %s.",
                    self.account_name,
                    expected.parent,
                )
                if cmd_output.stderr:
                    logger.error(cmd_output.stderr)
                if cmd_output.stdout:
                    logger.debug(cmd_output.stdout)
        else:
            logger.info(
                "Not changing parent of account %s to %s, because account is not managed.",
                self.account_name,
                expected.parent,
            )

    def sync_account(self) -> None:
        """Sync account to make sure SLURM is the same as the projects portal."""
        # If it does exist but shouldn't, deactivate it.
        if self.expected is None:
            self.deactivate_account()
        # If it doesn't exist, create it.
        elif self.existing is None:
            self.create_account(self.expected)
        # Otherwise, make sure the accounts parent and fairshare are correct.
        else:
            # If the account's parent is not correct, update it.
            if self.existing.parent != self.expected.parent:
                self.update_parent(self.expected)
            # If the account's fairshare is not correct, update it.
            if self.existing.fairshare != self.expected.fairshare:
                self.update_fairshare(self.expected)
