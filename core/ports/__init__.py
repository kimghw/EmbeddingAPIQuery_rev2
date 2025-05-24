"""Core ports (interfaces) for external dependencies."""

from .repository import (
    UserRepository,
    AccountRepository,
    EmailRepository,
    TransmissionRecordRepository,
)
from .graph_api import GraphAPIPort
from .external_api import ExternalAPIPort
from .config import ConfigPort

__all__ = [
    "UserRepository",
    "AccountRepository", 
    "EmailRepository",
    "TransmissionRecordRepository",
    "GraphAPIPort",
    "ExternalAPIPort",
    "ConfigPort",
]
