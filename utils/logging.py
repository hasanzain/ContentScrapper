import logging
import sys

_LOGGER_NAME = "tiktok_mcp"


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger that exclusively outputs to stderr.

    Protects MCP stdio JSON-RPC transport from stdout contamination.
    """
    logger_name = f"{_LOGGER_NAME}.{name}" if name else _LOGGER_NAME
    logger = logging.getLogger(logger_name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


class YtDlpStderrLogger:
    """Redirects yt-dlp internal messages to stderr via standard logging."""

    def __init__(self, logger: logging.Logger | None = None):
        self._logger = logger or get_logger("yt_dlp")

    def debug(self, msg: str) -> None:
        if not msg.startswith("[debug] "):
            self._logger.debug(msg)

    def info(self, msg: str) -> None:
        self._logger.info(msg)

    def warning(self, msg: str) -> None:
        self._logger.warning(msg)

    def error(self, msg: str) -> None:
        self._logger.error(msg)
