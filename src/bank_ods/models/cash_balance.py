from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Literal

from .base import BankDocument, IndexSpec


class CashBalance(BankDocument):
    COLLECTION: ClassVar[str] = "cash_balances"
    INDEXES: ClassVar[list[IndexSpec]] = [
        ([("accountId", 1), ("currency", 1), ("asOfDate", -1)], {"unique": True}),
        ("asOfDate", {}),
    ]

    balanceId: str
    accountId: str
    currency: str
    asOfDate: datetime
    openingBalance: float
    credits: float
    debits: float
    closingBalance: float
    pendingCredits: float
    pendingDebits: float
    projectedBalance: float
    snapshotType: Literal["EOD", "INTRADAY"]
    createdAt: datetime
    updatedAt: datetime
