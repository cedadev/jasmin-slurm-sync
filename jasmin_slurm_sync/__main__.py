import asyncio
import logging
import os
import pathlib
import time

import pydantic_settings
import sdnotify  # type: ignore

from . import cli
from . import settings as settings_module
from . import sync

system_notify = sdnotify.SystemdNotifier()
args = cli.SyncArgParser().parse_args()
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

logger.info("Starting sync of SLURM users.")
system_notify.notify(f"MAINPID={os.getpid()}")
system_notify.notify("READY=1")


async def main() -> None:
    while True:
        logger.debug("Loading settings.")
        settings = settings_module.load_settings(pathlib.Path(args.config))

        logger.debug("Create syncer.")
        syncer = sync.SLURMSyncer(settings, args)

        logger.debug("Do the sync.")
        print(await syncer.expected_slurm_accounts)
        # await syncer.sync()

        if args.run_forever:
            logger.info(
                "Finished sync, sleeping for %s secs.", settings.daemon_sleep_time
            )
            await asyncio.sleep(settings.daemon_sleep_time)
        else:
            logger.info("Running in one-shot mode. Quitting.")
            system_notify.notify("STOPPING=1")
            break


asyncio.run(main())
