import copy
import pathlib
import typing

import pydantic_settings


class SyncSettings(pydantic_settings.BaseSettings):
    """Settings class for SLURM sync tool."""

    model_config = pydantic_settings.SettingsConfigDict(toml_file="config.toml")

    ldap_server_addr: str
    ldap_search_base: str
    ldap_search_filter: str

    ldap_tag_mapping: dict[str, list[str]]

    required_slurm_accounts: set[str]

    daemon_sleep_time: int = 600

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: typing.Type[pydantic_settings.BaseSettings],
        init_settings: pydantic_settings.PydanticBaseSettingsSource,
        env_settings: pydantic_settings.PydanticBaseSettingsSource,
        dotenv_settings: pydantic_settings.PydanticBaseSettingsSource,
        file_secret_settings: pydantic_settings.PydanticBaseSettingsSource,
    ) -> typing.Tuple[pydantic_settings.PydanticBaseSettingsSource, ...]:
        """Add TOML to settings sources."""
        return (pydantic_settings.TomlConfigSettingsSource(settings_cls),)


def load_settings(path: pathlib.Path) -> SyncSettings:
    """Inject path to settings file and load the settings."""
    Settings = copy.deepcopy(SyncSettings)
    Settings.model_config = pydantic_settings.SettingsConfigDict(toml_file=path)
    return Settings()
