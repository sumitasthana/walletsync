"""Bank registry.

Add a new bank by creating a package under src/banks/<key>/ with a
BankConfig and registering it in BANKS below. See docs/ONBOARDING_NEW_BANK.md.
"""

from src.banks.base import BankConfig
from src.banks.chase import CHASE
from src.banks.pnc import PNC

BANKS = {bank.key: bank for bank in (CHASE, PNC)}


def get_bank(key: str) -> BankConfig:
    """Return the BankConfig for a bank key. Exits with a clear error if unknown."""
    try:
        return BANKS[key]
    except KeyError:
        known = ", ".join(sorted(BANKS))
        raise SystemExit(f"Unknown bank '{key}'. Known banks: {known}")
