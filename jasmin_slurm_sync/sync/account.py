import asyncio
import functools

import asyncstdlib
import jasmin_account_api_client

from .. import cli
from .. import settings as settings_module
from .. import utils
from ..models import account


class AccountSyncingMixin:
    """Mixin defining logic for syning SLURM accounts."""

    settings: settings_module.SyncSettings
    args: cli.SyncArgParser
    api_client: jasmin_account_api_client.AuthenticatedClient

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
        # Add in accounts for default and noprojects so that the manager doesn't delete them.
        accounts.add(
            account.AccountInfo(
                name=self.settings.no_project_account, parent="root", fairshare=1
            )
        )
        accounts.add(
            account.AccountInfo(
                name=self.settings.default_account, parent="root", fairshare=1
            )
        )
        return accounts

    @functools.cached_property
    def existing_slurm_accounts(self) -> set[account.AccountInfo]:
        """Get a list of existing SLURM accounts from SLURM."""
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
