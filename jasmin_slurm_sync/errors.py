class UserSyncError(Exception):
    """Error Group for errors which prevent a single user from being synced"""


class NoUnixUser(UserSyncError):
    """Error raised when the user being synded does not have a unix account."""


class NotInRequiredAccounts(UserSyncError):
    """Error raised when the user isn't in a SLURM account which they are required to be in for syncing."""
