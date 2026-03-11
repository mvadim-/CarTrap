"""Logging helpers."""

import logging


def configure_logging(log_level: str) -> None:
    """Configure root logging once for the process."""

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
