import logging
import subprocess as sp
import time
import typing

logger = logging.getLogger(__name__)


def run_ratelimited(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
    """Call subprocess to call a slurm command.

    Enforces rate limiting.
    """
    logger.debug("sp.run %s, %s", args, kwargs)
    try:
        result = sp.run(*args, **kwargs)
    except sp.CalledProcessError as err:
        logger.critical("Command output was: %s", err.output)
        raise err
    time.sleep(1)
    return result
