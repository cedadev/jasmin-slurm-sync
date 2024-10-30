import asyncio
import collections
import functools
import logging
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
        ldap_server: typing.Optional[ldap3.Server] = None,
        ldap_conn: typing.Optional[ldap3.Connection] = None,
        api_client: typing.Optional[
            jasmin_account_api_client.AuthenticatedClient
        ] = None,
    ) -> None:
        """Initialise a connection to the jasmin acounts portal."""
        self.settings = settings
        self.args = args

        # Init LDAP server connection.
        if ldap_server is None:
            self.ldap_server = ldap3.Server(
                self.settings.ldap_server_addr,
                get_info=ldap3.ALL,
            )
        else:
            self.ldap_server = ldap_server

        if ldap_conn is None:
            self.ldap_conn = ldap3.Connection(
                self.ldap_server,
                auto_bind=True,
                auto_encode=True,
                check_names=True,
                client_strategy=ldap3.SAFE_RESTARTABLE,
            )
        else:
            self.ldap_conn = ldap_conn

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
    async def expected_slurm_accounts(self) -> set[tuple[str, str]]:
        """Get a list of all the SLURM accounts from the projects portal."""
        client = self.api_client.get_async_httpx_client()

        # Run all the web requests we need to make in paralell.
        async with asyncio.TaskGroup() as tg:
            all_services_task = tg.create_task(
                client.get(self.settings.api_projects_base_url + "services/")
            )
            all_projects_task = tg.create_task(
                client.get(self.settings.api_projects_base_url + "projects/")
            )
            all_consortia_task = tg.create_task(
                client.get(self.settings.api_projects_base_url + "consortia/")
            )

        # Get the json results and rearrange for easy access.
        all_services = all_services_task.result().json()
        all_projects = {x["id"]: x for x in all_projects_task.result().json()}
        all_consortia = {x["id"]: x for x in all_consortia_task.result().json()}

        accounts = set()
        # Get a list of all active services.
        for service in all_services:
            # Group workspaces are category 1.
            if service["category"] == 1:
                for req in service["requirements"]:
                    # status 50 is 'active'
                    if req["status"] == 50:
                        project = all_projects[service["project"]]
                        consortium = all_consortia[project["consortium"]]
                        accounts.add(
                            (consortium["name"], service["name"]),
                            service.get("fairshare", 1),
                        )
                        accounts.add(
                            ("root", consortium["name"], service.get("fairshare", 1))
                        )
                        break
        return accounts

    @functools.cached_property
    def existing_slurm_accounts(self) -> set[tuple[str, str]]:
        args = [
            "sacctmgr",
            "show",
            "account",
            "withassoc",
            "format=parentname%50,account%50,fairshare%50",
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
        return set(x for x in accounts_pairs if len(x) == 3)

    @asyncstdlib.cached_property(asyncio.Lock)
    async def accounts_to_be_synced(self) -> set[tuple[str, str, str]]:
        """Return accounts which don't exactly match in both sets."""
        wrong_accounts = (
            await self.expected_slurm_accounts
        ) ^ self.existing_slurm_accounts
        # Exclude fairshare from the set to deduplicate where fairshare is wrong.
        return {x[0:2] for x in wrong_accounts}

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

    async def users(self) -> typing.AsyncIterator[user.User]:
        """Get list of users whose SLURM accounts should be synced."""
        # Convert each user model to the user class.
        for ldap_user in self.all_ldap_users:
            (username,) = ldap_user["cn"]
            yield user.User(
                ldap_user, self.all_slurm_users[username], self.settings, self.args
            )

    async def accounts(self) -> typing.AsyncIterable[account.Account]:
        """Get list of SLURM accounts which should be synced."""
        existing_slurm_accounts = {x[1]: x for x in self.existing_slurm_accounts}
        expected_slurm_accounts = {x[1]: x for x in self.expected_slurm_accounts}
        for account_tuple in await self.accounts_to_be_synced:
            yield account.Account(
                account_tuple,
                existing_slurm_accounts,
                expected_slurm_accounts,
                self.settings,
                self.args,
            )

    async def sync(self) -> None:
        """Call sync on each user in turn."""
        async for account in self.accounts():
            account.sync_account()

        async for user in self.users():
            try:
                user.sync_slurm_accounts()
            except errors.UserSyncError:
                logger.warning("User %s failed to sync.", user.username)
