import pydantic_settings


class SyncSettings(pydantic_settings.BaseSettings):
    ldap_server_addr: str
    ldap_search_base: str
    ldap_search_filter: str

    ldap_tag_mapping: dict[str, list[str]]

    required_slurm_accounts: set[str]
