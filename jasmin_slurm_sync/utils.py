import logging
import subprocess as sp
import time
import typing

logger = logging.getLogger(__name__)


def run_ratelimited(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
    """Call subprocess to call a slurm command.

    Enforces rate limiting.
    """
    result = sp.run(*args, **kwargs)
    logger.debug("sp.run %s, %s", " ".join(args), kwargs)
    time.sleep(1)
    return result
