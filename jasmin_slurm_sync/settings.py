import copy
import pathlib
import typing

import pydantic_settings


class SyncSettings(pydantic_settings.BaseSettings):
    """Settings class for SLURM sync tool."""

    model_config = pydantic_settings.SettingsConfigDict(toml_file="config.toml")

    daemon_sleep_time: int = 600

    api_client_base_url: str
    api_client_id: str
    api_client_secret: str
    api_client_scopes: list[str]
    api_projects_base_url: str
    api_accounts_base_url: str

    unmanaged_accounts: list[str]
    unmanaged_users: list[str]

    list_users_role: str

    extra_account_mapping: dict[str, list[str]]

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
