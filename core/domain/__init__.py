"""Domain entities for GraphAPIQuery project."""

from .user import User
from .email import Email
from .account import Account
from .transmission_record import TransmissionRecord

__all__ = ["User", "Email", "Account", "TransmissionRecord"]
