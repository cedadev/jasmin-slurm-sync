import logging
import subprocess as sp

logger = logging.getLogger(__name__)


def run_ratelimited(self, *args, **kwargs):
    """Wrapper to call subprocess to call a slurm command.

    Enforces rate limiting.
    """
    result = sp.run(*args, **kwargs)
    logger.debug("sp.run %s, %s", " ".join(args), kwargs)
    time.sleep(1)
    return result
