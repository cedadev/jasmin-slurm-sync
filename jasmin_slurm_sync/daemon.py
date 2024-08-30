import logging
import time

from . import sync

logger = logging.getLogger(__name__)

while True:
    logger.info("Starting sync of SLURM users.")
    syncer = sync.SLURMSyncer()
    syncer.sync()

    logger.info("Finished sync, sleeping.")
    time.sleep(600)
