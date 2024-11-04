import asyncio
import collections
import functools
import logging
import textwrap
import typing

import asyncstdlib
import jasmin_account_api_client
import ldap3

from . import account, cli, errors
from . import settings as settings_module
from . import user, utils

logger = logging.getLogger(__name__)


class SLURMSyncer:
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

    @asyncstdlib.cached_property(asyncio.Lock)
    async def expected_slurm_accounts(self) -> set[account.AccountInfo]:
        """Get a list of all the SLURM accounts from the projects portal."""
        client = self.api_client.get_async_httpx_client()

        # Run all the web requests we need to make in paralell.
        async with asyncio.TaskGroup() as tg:
            all_services_task = tg.create_task(
                client.get(self.settings.api_projects_base_url + "services/")
            )
            all_consortia_task = tg.create_task(
                client.get(self.settings.api_projects_base_url + "consortia/")
            )

        # Get the json results and rearrange for easy access.
        all_services = all_services_task.result().json()
        all_consortia = {x["id"]: x for x in all_consortia_task.result().json()}

        # Get only services which are group workspaces (category 1) and have active requirements.
        interested_services = [
            x
            for x in all_services
            if x["has_active_requirements"] and (x["category"] == 1)
        ]

        accounts = set()
        # Get a list of all active services.
        for service in interested_services:
            # Group workspaces are category 1.
            consortium = all_consortia[service["consortium"]]
            accounts.add(
                account.AccountInfo(
                    name=service["name"],
                    parent=consortium["name"],
                    fairshare=int(service.get("project_fairshare", 1)),
                )
            )
            accounts.add(
                account.AccountInfo(
                    name=consortium["name"],
                    parent="root",
                    fairshare=int(service.get("consortium_fairshare", 1)),
                )
            )
        return accounts

    @functools.cached_property
    def existing_slurm_accounts(self) -> set[account.AccountInfo]:
        args = [
            "sacctmgr",
            "show",
            "account",
            "withassoc",
            "format=parentname%50,account%50,fairshare%50",
            "--parsable2",
            "--noheader",
        ]
        cmd_output = utils.run_ratelimited(args, capture_output=True, check=True)
        # sacctmgr returns a newline seperated list of strings,
        # padded to 50 characters as specified above.
        # padding is necessary to ensure no account names are trucated.
        # we split on the newlines,
        # strip any whitespace then filter out any blank lines.
        account_bytes = cmd_output.stdout.splitlines()
        account_lists = [x.decode("utf-8").split("|") for x in account_bytes]
        account_tuples = [
            account.AccountInfo(name=x[1], parent=x[0], fairshare=int(x[2]))
            for x in account_lists
        ]
        # filter out accounts which have no parent: this isn't possible.
        filtered_account_tuples = [x for x in account_tuples if x.parent]
        return set(filtered_account_tuples)

    @asyncstdlib.cached_property(asyncio.Lock)
    async def accounts_to_be_synced(self) -> set[str]:
        """Return accounts which don't exactly match in both sets."""
        wrong_accounts = (
            await self.expected_slurm_accounts
        ) ^ self.existing_slurm_accounts

        return {x.name for x in wrong_accounts}

    @asyncstdlib.cached_property(asyncio.Lock)
    async def users_to_be_synced(self) -> set[str]:
        """Return list of all users who should be synced.
        This is all the ones from both SLURM AND the accounts portal."""
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
        user_accounts = collections.defaultdict(set)
        for task in tasks:
            result = task.result().json()
            username = task.get_name()
            for grant in result:
                if grant["role"]["name"] == "USER":
                    # Add all the group workspaces.
                    if grant["service"]["category"]["name"] == "group_workspaces":
                        user_accounts[username].add(grant["service"]["name"])
                    # Add extra mappings.
                    service_name = f"{grant['service']['category']['name']}/{grant['service']['name']}"
                    if service_name in self.settings.extra_account_mapping.keys():
                        user_accounts[username].update(
                            self.settings.extra_account_mapping[service_name]
                        )

        return user_accounts

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

    async def users(self) -> typing.AsyncIterator[user.User]:
        """Get list of users whose SLURM accounts should be synced."""
        # Convert each user model to the user class.
        for username in await self.users_to_be_synced:
            if username not in self.settings.unmanaged_users:
                yield user.User(
                    username=username,
                    portal_services=(await self.portal_user_services).get(
                        username, set()
                    ),
                    slurm_accounts=self.all_slurm_users.get(username, set()),
                    settings=self.settings,
                    args=self.args,
                )

    async def accounts(self) -> typing.AsyncIterable[account.Account]:
        """Get list of SLURM accounts which should be synced."""
        expected = await self.expected_slurm_accounts

        for account_name in await self.accounts_to_be_synced:
            if account_name not in self.settings.unmanaged_accounts:
                yield account.Account(
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
