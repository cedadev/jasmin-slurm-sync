import os
import tomllib
import typing

import typeguard


class SettingsSchema(typing.TypedDict):
    ldap_server_addr: str
    ldap_search_base: str
    ldap_search_filter: str

    ldap_tag_mapping: dict[str, list[str]]


class SyncSettings:
    def __init__(self, path: str = "config.toml") -> None:
        with open(path, "rb") as thefile:
            toml_dict = typing.cast(SettingsSchema, tomllib.load(thefile))

        typeguard.check_type(toml_dict, SettingsSchema)
        for key, value in toml_dict.items():
            setattr(self, key, value)
