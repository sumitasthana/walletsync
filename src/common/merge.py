"""Merge clean, pricing, and rewards records into one card document."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


def load_json_records(path) -> List[Dict]:
    """Load a JSON array from path, or an empty list if the file is missing.

    Skips metadata records (entries whose keys contain '_meta').
    """
    if not Path(path).exists():
        return []
    with open(path, 'r', encoding='utf-8') as f:
        records = json.load(f)
    return [r for r in records if '_meta' not in r]


def find_record(records: List[Dict], card_id: str) -> Optional[Dict]:
    """Return the record with a matching card_id, or None."""
    for r in records:
        if r.get('card_id') == card_id:
            return r
    return None


def merge_card(card: Dict, pricing: Optional[Dict], rewards: Optional[Dict],
               fallback: Optional[Dict] = None) -> Dict:
    """Merge one card's clean record with its pricing and rewards records.

    Uses the tier 1 rewards record when present; otherwise the tier 2 HTML
    fallback, under a separate key.
    """
    merged = {
        '_meta': {
            'card_id': card.get('card_id'),
            'bank': card.get('bank'),
            'extracted_at': datetime.now(timezone.utc).isoformat(),
            'data_sources': []
        },
        'card_info': {
            'card_id': card.get('card_id'),
            'card_name': card.get('card_name'),
            'bank': card.get('bank'),
            'annual_fee_usd': card.get('annual_fee_usd'),
            'waived_first_year': card.get('waived_first_year'),
            'reward_currency': card.get('reward_currency'),
            'sign_up_bonus_value': card.get('sign_up_bonus_value'),
            'sign_up_bonus_spend_req': card.get('sign_up_bonus_spend_req'),
            'sign_up_bonus_months': card.get('sign_up_bonus_months'),
            'base_earn_rate': card.get('base_earn_rate'),
            'pricing_terms_url': card.get('pricing_terms_url'),
            'rewards_agreement_url': card.get('rewards_agreement_url')
        }
    }

    if pricing:
        merged['pricing'] = pricing
        merged['_meta']['data_sources'].append('pricing_extended')

    if rewards:
        merged['rewards'] = rewards
        merged['_meta']['data_sources'].append('rewards_extended')
    elif fallback:
        merged['rewards_fallback'] = fallback
        merged['_meta']['data_sources'].append('rewards_html_fallback')

    return merged
