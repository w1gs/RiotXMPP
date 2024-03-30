import sys

from loguru import logger


logger.remove()
logger.add(
    sys.stdout,
    level="INFO",
    format="<level>[{level}] {message}</level>",
)
logger.level("RESPONSE", no=23, color="<green>")
logger.level("REQUEST", no=22, color="<blue>")
logger.level("INFO", color="<magenta>")
logger.level("DECODED", no=24, color="<cyan>")

