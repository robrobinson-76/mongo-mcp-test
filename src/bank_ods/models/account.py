from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Literal, Optional

import pymongo

from .base import BankDocument, IndexSpec


class Account(BankDocument):
    COLLECTION: ClassVar[str] = "accounts"
    INDEXES: ClassVar[list[IndexSpec]] = [
        ("accountId", {"unique": True}),
        ("clientId", {}),
        ("status", {}),
    ]

    accountId: str
    accountName: str
    accountType: Literal["CUSTODY", "PROPRIETARY", "OMNIBUS"]
    clientId: str
    clientName: str
    baseCurrency: str
    status: Literal["ACTIVE", "SUSPENDED", "CLOSED"]
    openDate: datetime
    closeDate: Optional[datetime] = None
    custodianBranch: str
    createdAt: datetime
    updatedAt: datetime
