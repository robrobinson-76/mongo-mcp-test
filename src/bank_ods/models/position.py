from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Literal

from .base import BankDocument, IndexSpec


class Position(BankDocument):
    COLLECTION: ClassVar[str] = "positions"
    INDEXES: ClassVar[list[IndexSpec]] = [
        ([("accountId", 1), ("securityId", 1), ("asOfDate", -1)], {"unique": True}),
        ("asOfDate", {}),
        ("accountId", {}),
    ]

    positionId: str
    accountId: str
    securityId: str
    asOfDate: datetime
    quantity: float
    currency: str
    costBasis: float
    marketPrice: float
    marketValue: float
    unrealizedPnL: float
    positionType: Literal["LONG", "SHORT"]
    snapshotType: Literal["EOD", "INTRADAY", "SETTLEMENT"]
    createdAt: datetime
    updatedAt: datetime
