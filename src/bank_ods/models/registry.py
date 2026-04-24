from .account import Account
from .security import Security
from .transaction import Transaction
from .position import Position
from .settlement import Settlement
from .cash_balance import CashBalance
from .base import BankDocument

# Ordered list of all entity models — used by ensure_indexes() and generate_sdl()
ENTITIES: list[type[BankDocument]] = [
    Account,
    Security,
    Transaction,
    Position,
    Settlement,
    CashBalance,
]
