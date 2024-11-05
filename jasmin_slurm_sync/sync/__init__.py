import logging
import typing

import jasmin_account_api_client

from .. import cli, errors, models
from .. import settings as settings_module
from . import account, user

logger = logging.getLogger(__name__)


class SLURMSyncer(account.AccountSyncingMixin, user.UserSyncingMixin):
    """Sync users' SLURM Accounts."""

    def __init__(
        self,
        settings: settings_module.SyncSettings,
        args: cli.SyncArgParser,
        *,
        api_client: typing.Optional[
            jasmin_account_api_client.AuthenticatedClient
        ] = None,
    ) -> None:
        """Initialise a connection to the jasmin acounts portal."""
        self.settings = settings
        self.args = args

        # Init connection to jasmin accounts api.
        if api_client is None:
            self.api_client = jasmin_account_api_client.AuthenticatedClient(
                settings.api_client_base_url
            )
            self.api_client.client_credentials_flow(
                settings.api_client_id,
                settings.api_client_secret,
                settings.api_client_scopes,
            )
        else:
            self.api_client = api_client

    async def users(self) -> typing.AsyncIterator[models.user.User]:
        """Get list of users whose SLURM accounts should be synced."""
        # Convert each user model to the user class.
        for username in await self.users_to_be_synced:
            if username not in self.settings.unmanaged_users:
                yield models.user.User(
                    username=username,
                    portal_services=(await self.portal_user_services).get(
                        username, set()
                    ),
                    slurm_accounts=self.all_slurm_users.get(username, set()),
                    existing_default_account=self.all_default_accounts.get(
                        username, ""
                    ),
                    settings=self.settings,
                    args=self.args,
                )

    async def accounts(self) -> typing.AsyncIterable[models.account.Account]:
        """Get list of SLURM accounts which should be synced."""
        expected = await self.expected_slurm_accounts

        for account_name in await self.accounts_to_be_synced:
            if account_name not in self.settings.unmanaged_accounts:
                yield models.account.Account(
                    account_name=account_name,
                    existing_slurm_accounts=self.existing_slurm_accounts,
                    expected_slurm_accounts=expected,
                    settings=self.settings,
                    args=self.args,
                )

    async def sync(self) -> None:
        """Call sync on each account and user in turn."""
        # Sync root accounts first so they are available when other accounts are created.
        async for account in self.accounts():
            if getattr(account.expected, "parent", None) == "root":
                account.sync_account()
        # Then sync all acounts
        async for account in self.accounts():
            account.sync_account()

        # Then sync the users.
        async for user in self.users():
            try:
                user.sync_slurm_accounts()
            except errors.UserSyncError:
                logger.warning("User %s failed to sync.", user.username)
