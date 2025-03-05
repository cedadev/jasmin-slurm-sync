import asyncio
import collections
import functools
import logging

import asyncstdlib
import jasmin_account_api_client

from .. import cli
from .. import settings as settings_module
from .. import utils
from ..models import account, user

logger = logging.getLogger(__name__)


class UserSyncingMixin:
    """Mixin defining logic for sycing the accounts of SLURM users."""

    settings: settings_module.SyncSettings
    args: cli.SyncArgParser
    api_client: jasmin_account_api_client.AuthenticatedClient

    @asyncstdlib.cached_property(asyncio.Lock)
    async def users_to_be_synced(self) -> set[str]:
        """Return list of all users who should be synced.

        This is all the ones from both SLURM AND the accounts portal.
        """
        return (await self.portal_slurm_users) | set(self.all_slurm_users.keys())

    @asyncstdlib.cached_property(asyncio.Lock)
    async def portal_slurm_users(self) -> set[str]:
        """Get the list of users from the JASMIN accounts portal."""
        client = self.api_client.get_async_httpx_client()
        category, service = self.settings.list_users_role.split("/")

        role_user_list = (
            await client.get(
                self.settings.api_accounts_base_url
                + f"categories/{category}/services/{service}/roles/USER/"
            )
        ).json()["accesses"]
        usernames = [x["user"]["username"] for x in role_user_list]
        return set(usernames)

    @asyncstdlib.cached_property(asyncio.Lock)
    async def portal_user_services(self) -> dict[str, set[str]]:
        """Get a list of services for each user."""
        client = self.api_client.get_async_httpx_client()
        tasks = []
        async with asyncio.TaskGroup() as tg:
            for username in await self.portal_slurm_users:
                tasks.append(
                    tg.create_task(
                        client.get(
                            self.settings.api_accounts_base_url
                            + f"users/{username}/grants/"
                        ),
                        name=username,
                    )
                )
        # Pre-populate each users' list of accounts with the default account.
        user_accounts = collections.defaultdict(
            functools.partial(set, [self.settings.default_account])
        )
        for task in tasks:
            result = task.result().json()
            username = task.get_name()
            extra_accounts = set()  # Keep track of extra accounts.
            for grant in result:
                if grant["role"]["name"] == "USER":
                    # Add all the group workspaces.
                    if grant["service"]["category"]["name"] == "group_workspaces":
                        user_accounts[username].add(grant["service"]["name"])
                    # Add extra mappings.
                    service_name = f"{grant['service']['category']['name']}/{grant['service']['name']}"
                    if service_name in self.settings.extra_account_mapping.keys():
                        # Keep track of extra accounts so we know who to add to the no_project account.
                        extra_accounts.update(
                            self.settings.extra_account_mapping[service_name]
                        )
                        user_accounts[username].update(
                            self.settings.extra_account_mapping[service_name]
                        )
            # Add the no project account to users who have no other account.
            if len(user_accounts[username] - extra_accounts) <= 1:
                user_accounts[username].add(self.settings.no_project_account)
        return user_accounts

    @functools.cached_property
    def all_slurm_users(self) -> dict[str, set[str]]:
        """Get a list of all SLURM users, with their accounts, from SLURM."""
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

    @functools.cached_property
    def all_default_accounts(self) -> dict[str, str]:
        """Get a list of all SLURM users, with their default accounts, from SLURM."""
        args = [
            "sacctmgr",
            "show",
            "user",
            "withassoc",
            "format=user%50,defaultaccount%50",
            "--noheader",
            "--parsable2",
        ]
        cmd_output = utils.run_ratelimited(args, capture_output=True, check=True)
        user_bytes = cmd_output.stdout.splitlines()
        user_list = [x.decode("utf-8").split("|") for x in user_bytes]
        default_accounts = {x[0]: x[1] for x in user_list}
        return default_accounts
