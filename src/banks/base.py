"""Shared bank configuration and per-bank data path helpers.

Every supported issuer is described by a BankConfig. Data for a bank always
lives under data/<key>/ so banks never share files.
"""

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass(frozen=True)
class BankConfig:
    """Configuration for one card issuer."""

    key: str                        # directory and CLI name, e.g. "chase"
    display_name: str              # human-readable name, e.g. "Chase"
    status: str                    # "ready" or "spike"
    category_extensions: tuple = ()  # earning categories beyond BASE_CATEGORIES

    @property
    def data_dir(self) -> Path:
        return PROJECT_ROOT / "data" / self.key

    @property
    def cards_raw_path(self) -> Path:
        return self.data_dir / "cards.json"

    @property
    def cards_clean_path(self) -> Path:
        return self.data_dir / "cards_clean.json"

    @property
    def raw_pricing_dir(self) -> Path:
        return self.data_dir / "raw" / "pricing"

    @property
    def raw_rewards_dir(self) -> Path:
        return self.data_dir / "raw" / "rewards"

    @property
    def extracted_pricing_path(self) -> Path:
        return self.data_dir / "extracted_pricing_extended.json"

    @property
    def extracted_rewards_path(self) -> Path:
        return self.data_dir / "extracted_rewards_extended.json"

    @property
    def extracted_fallback_path(self) -> Path:
        return self.data_dir / "extracted_rewards_html_fallback.json"

    @property
    def baseline_pricing_path(self) -> Path:
        return self.data_dir / "baseline_pricing_llm.json"

    @property
    def per_card_dir(self) -> Path:
        return self.data_dir / "cards"
