import logging

import pydantic_settings

from . import settings as settings_module
from . import sync

logging.basicConfig(level=logging.INFO)

settings = pydantic_settings.TomlConfigSettingsSource(
    settings_module.SyncSettings, toml_file="config.toml"
)

syncer = sync.SLURMSyncer(settings)

syncer.sync()
