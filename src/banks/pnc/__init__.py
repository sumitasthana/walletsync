"""PNC bank adapter.

Status is "spike": investigation only, no pipeline yet. Format findings live
in docs/reports/pnc_spike.md and the onboarding steps are documented in
docs/ONBOARDING_NEW_BANK.md.
"""

from src.banks.base import BankConfig

PNC = BankConfig(
    key="pnc",
    display_name="PNC",
    status="spike",
    category_extensions=(),
)
