"""Chase bank adapter."""

from src.banks.base import BankConfig

CHASE = BankConfig(
    key="chase",
    display_name="Chase",
    status="ready",
    category_extensions=("travel_chase_portal", "lyft", "peloton"),
)
