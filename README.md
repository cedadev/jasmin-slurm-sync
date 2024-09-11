# jasmin-slurm-sync
This python utility is used by [JASMIN](https://jasmin.ac.uk) to keep [SLURM Accounts](https://slurm.schedmd.com/sacctmgr.html#OPT_account) in sync with users' LDAP tags.

It gets a list of ldap tags for each user from LDAP then converts that list to SLURM accounts using the mapping provided in config.toml.
It then gets a list of current SLURM accounts for the user using [sacctmgr](https://slurm.schedmd.com/sacctmgr.html) and compares the two sets.
Then it runs the correct [sacctmgr](https://slurm.schedmd.com/sacctmgr.html) commands to add or remove the user from accounts to make the sets equal.

When running in daemon mode, it does this for every user then sleeps for an amount of time specified in config.toml, before running again.
