"""Keep internal catalog identifiers out of customer-facing answers."""

import re

from src.banks import BANKS
from src.common.merge import load_json_records


def customer_card_names(text: str) -> str:
    """Replace known card identifiers with catalog names, without changing facts."""
    names = {}
    for bank in BANKS.values():
        if bank.cards_clean_path.exists():
            for card in load_json_records(bank.cards_clean_path):
                if card.get("card_id") and card.get("card_name"):
                    names[card["card_id"]] = card["card_name"]
    if not names:
        return text
    pattern = r"(?<![\w-])(?:" + "|".join(re.escape(key) for key in names) + r")(?![\w-])"
    return re.sub(pattern, lambda match: names[match.group()], text)
