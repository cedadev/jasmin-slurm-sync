from . import sync
import logging

logging.basicConfig(level=logging.INFO)

syncer = sync.SLURMSyncer()

syncer.sync()
