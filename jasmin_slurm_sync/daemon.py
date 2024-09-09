import logging
import time

import pydantic_settings

from . import settings as settings_module
from . import sync

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


while True:
    logger.info("Starting sync of SLURM users.")

    logger.debug("Loading settings.")
    settings = pydantic_settings.TomlConfigSettingsSource(
        settings_module.SyncSettings, toml_file="config.toml"
    )

    logger.debug("Create syncer.")
    syncer = sync.SLURMSyncer(settings)

    logger.debug("Do the sync.")
    syncer.sync()

    logger.info("Finished sync, sleeping.")
    time.sleep(600)
