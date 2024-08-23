import subprocess as sp
def run_ratelimited(self, *args, **kwargs):
    """Wrapper to call subprocess to call a slurm command.

    Enforces rate limiting.
    """
    result = sp.run(*args, **kwargs)
    time.sleep(1)
    return result
