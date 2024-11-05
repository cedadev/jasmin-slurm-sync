import functools
import logging
import pwd

from .. import cli, errors
from .. import settings as settings_module
from .. import utils

logger = logging.getLogger(__name__)


class User:
    """Class which represents a JASMINUser and their SLURM Accounts."""

    def __init__(
        self,
        username: str,
        portal_services: set[str],
        slurm_accounts: set[str],
        existing_default_account: str,
        settings: settings_module.SyncSettings,
        args: cli.SyncArgParser,
    ) -> None:
        self.portal_services = portal_services
        self.slurm_accounts = slurm_accounts
        self.existing_default_account = existing_default_account
        self.username = username
        self.settings = settings
        self.args = args

    @functools.cached_property
    def existing_slurm_accounts(self) -> set[str]:
        """Get the list of SLURM accounts which the user has already."""
        return self.slurm_accounts

    @functools.cached_property
    def expected_slurm_accounts(self) -> set[str]:
        """Get the list of SLURM accounts which the user is expected to have."""
        return self.portal_services

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
        if account not in self.settings.unmanaged_accounts:
            args = [
                "sacctmgr",
                "-i",
                "add",
                "user",
                self.username,
                f"account={account}",
            ]
            if self.args.dry_run:
                logger.warning(
                    "Would add user %s to account %s, but we are in dry run mode so not doing anything.",
                    self.username,
                    account,
                )
            else:
                cmd_output = utils.run_ratelimited(
                    args, capture_output=True, check=True
                )
                logger.info("Added user %s to account %s", self.username, account)
                if cmd_output.stderr:
                    logger.error(cmd_output.stderr)
                if cmd_output.stdout:
                    logger.debug(cmd_output.stdout)
        else:
            logger.info(
                "Not adding %s to %s, because account is not managed.",
                self.username,
                account,
            )

    def remove_user_from_account(self, account: str) -> None:
        """Remove the user from a given SLURM account."""
        if account not in self.settings.unmanaged_accounts:
            args = [
                "sacctmgr",
                "-i",
                "remove",
                "user",
                self.username,
                f"account={account}",
            ]
            if self.args.dry_run:
                logger.warning(
                    "Would remove user %s from account %s, but we are in dry run mode so not doing anything.",
                    self.username,
                    account,
                )
            else:
                cmd_output = utils.run_ratelimited(
                    args, capture_output=True, check=True
                )
                logger.info("Removed user %s from account %s", self.username, account)
                if cmd_output.stderr:
                    logger.error(cmd_output.stderr)
                if cmd_output.stdout:
                    logger.debug(cmd_output.stdout)
        else:
            logger.debug(
                "Not removing %s from %s, because account is not managed.",
                self.username,
                account,
            )

    def update_default_account(self) -> None:
        """Change the users' default account."""
        args = [
            "sacctmgr",
            "-i",
            "modify",
            "user",
            self.username,
            f"defaultaccount={self.settings.default_account}",
        ]
        if self.args.dry_run:
            logger.warning(
                "Change user %s's default account to %s, but we are in dry run mode so not doing anything.",
                self.username,
                self.settings.default_account,
            )
        else:
            cmd_output = utils.run_ratelimited(args, capture_output=True, check=True)
            logger.info(
                "Changed user %s's default account to %s",
                self.username,
                self.settings.default_account,
            )
            if cmd_output.stderr:
                logger.error(cmd_output.stderr)
            if cmd_output.stdout:
                logger.debug(cmd_output.stdout)

    def sync_slurm_accounts(self) -> None:
        """Do a full sync of the user's SLURM accounts."""
        # Check if there are any accounts to be added or removed so we don't have to check things if
        # we have no work to do.
        if self.to_be_added or self.to_be_removed:
            # If the user does not exist in linux, SLURM accounts should not be synced for the user.
            try:
                pwd.getpwnam(self.username)
            except KeyError as err:
                logger.warning(
                    "Unix User %s does not exist. Not syncing SLURM accounts.",
                    self.username,
                )
                raise errors.NoUnixUser from err

            # Add user to new accounts.
            for account in self.to_be_added:
                self.add_user_to_account(account)

            # Change the users' default account if required.
            if self.existing_default_account != self.settings.default_account:
                self.update_default_account()

            # Remove user from old accounts.
            for account in self.to_be_removed:
                self.remove_user_from_account(account)
