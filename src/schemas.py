"""Pydantic schemas for structured extraction."""

from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


# Canonical category vocabulary
ALLOWED_CATEGORIES = [
    "dining",
    "travel",
    "travel_chase_portal",
    "gas",
    "groceries",
    "drugstores",
    "streaming",
    "transit",
    "hotels",
    "airlines",
    "car_rental",
    "home_improvement",
    "rotating_5pct",
    "lyft",
    "peloton",
    "all_other",
    "other"
]


class PricingExtended(BaseModel):
    """Extended pricing data extracted from Schumer Box."""
    
    # Identifiers
    card_id: str
    card_name: str
    pricing_terms_url: str
    
    # Purchase APR
    purchase_apr_min: Optional[float] = Field(None, description="Minimum purchase APR percentage")
    purchase_apr_max: Optional[float] = Field(None, description="Maximum purchase APR percentage")
    purchase_apr_intro_pct: Optional[float] = Field(None, description="Intro purchase APR percentage")
    purchase_apr_intro_months: Optional[int] = Field(None, description="Intro purchase APR duration in months")
    
    # Balance Transfer APR
    bt_apr_min: Optional[float] = Field(None, description="Minimum balance transfer APR percentage")
    bt_apr_max: Optional[float] = Field(None, description="Maximum balance transfer APR percentage")
    bt_apr_intro_pct: Optional[float] = Field(None, description="Intro balance transfer APR percentage")
    bt_apr_intro_months: Optional[int] = Field(None, description="Intro balance transfer APR duration in months")
    bt_intro_window_days: Optional[int] = Field(None, description="Days to complete balance transfer for intro rate")
    
    # Cash Advance APR
    cash_advance_apr: float = Field(description="Cash advance APR percentage")
    
    # Penalty APR
    penalty_apr_max: Optional[float] = Field(None, description="Maximum penalty APR percentage")
    
    # Fees
    foreign_transaction_fee_pct: float = Field(description="Foreign transaction fee as percentage")
    balance_transfer_fee_pct: Optional[float] = Field(None, description="Balance transfer fee percentage")
    balance_transfer_fee_min_usd: Optional[int] = Field(None, description="Minimum balance transfer fee in USD")
    balance_transfer_fee_max_usd: Optional[int] = Field(None, description="Maximum balance transfer fee in USD")
    cash_advance_fee_pct: Optional[float] = Field(None, description="Cash advance fee percentage")
    cash_advance_fee_min_usd: Optional[int] = Field(None, description="Minimum cash advance fee in USD")
    late_payment_fee_max_usd: int = Field(description="Maximum late payment fee in USD")
    authorized_user_fee_usd: Optional[int] = Field(None, description="Authorized user fee in USD, null if not charged")
    
    # APR Index
    apr_index: Optional[str] = Field(None, description="APR index (e.g., 'Prime Rate')")
    purchase_apr_margin: Optional[float] = Field(None, description="Purchase APR margin over index")
    
    # Metadata
    apr_disclosure_date: Optional[str] = Field(None, description="Date pricing info was accurate (YYYY-MM-DD format)")


def coerce_null_strings(data: dict) -> dict:
    """
    Coerce string 'null', 'None', or empty string to actual None.
    
    Args:
        data: Dictionary potentially containing null strings
        
    Returns:
        Dictionary with null strings converted to None
    """
    result = {}
    for key, value in data.items():
        if isinstance(value, str) and value.lower() in ['null', 'none', '']:
            result[key] = None
        else:
            result[key] = value
    return result


class EarningCategory(BaseModel):
    """Earning rate for a specific category."""
    category: str = Field(description="Category name from ALLOWED_CATEGORIES")
    rate: float = Field(description="Earn rate (e.g., 3.0 for 3x or 3%)")
    cap_usd: Optional[int] = Field(None, description="Spending cap in USD")
    cap_period: Optional[str] = Field(None, description="Cap period: 'quarterly', 'annual', 'per_transaction'")
    requires_activation: bool = Field(False, description="Whether category requires activation")
    notes: Optional[str] = Field(None, description="Additional context, required if category='other'")


class RedemptionOption(BaseModel):
    """Redemption method and value."""
    method: str = Field(description="Redemption method: 'cash_back', 'statement_credit', 'travel_portal', 'transfer', 'pay_with_points', 'gift_cards', 'amazon', 'apple'")
    value_cents_per_point: float = Field(description="Redemption value in cents per point (e.g., 1.0 for 1cpp)")
    notes: Optional[str] = Field(None, description="Additional details")


class TransferPartner(BaseModel):
    """Loyalty program transfer partner."""
    partner_name: str = Field(description="Partner program name (e.g., 'United MileagePlus', 'Marriott Bonvoy')")
    ratio_from: int = Field(description="Points you give up (e.g., 3 for 3:1 transfer)")
    ratio_to: int = Field(description="Points you receive (e.g., 1 for 3:1 transfer)")
    notes: Optional[str] = Field(None, description="Transfer details")


class RewardsExtended(BaseModel):
    """Extended rewards data extracted from rewards agreement."""
    
    # Identifiers
    card_id: str
    card_name: str
    rewards_agreement_url: str
    
    # Data quality
    data_quality_tier: Literal["tier_1_pdf"] = "tier_1_pdf"
    
    # Core rewards info
    reward_currency: str = Field(description="'Cash Back', 'Points', 'Miles'")
    point_value_cents_baseline: Optional[float] = Field(None, description="Cash redemption value in cents per point. Null if no cash redemption.")
    
    # Earning structure
    earning_categories: List[EarningCategory] = Field(description="List of earning categories. MUST include one with category='all_other'")
    
    # Redemption
    redemption_minimum_usd: Optional[int] = Field(None, description="Minimum redemption amount in USD")
    redemption_options: List[RedemptionOption] = Field(default_factory=list, description="Available redemption methods")
    
    # Transfer partners
    transfer_partners: List[TransferPartner] = Field(default_factory=list, description="Loyalty program transfer partners")
    
    # Constraints
    points_expiration_months: Optional[int] = Field(None, description="Months until points expire. Null if no expiration.")
    bonus_disqualifying_products: List[str] = Field(default_factory=list, description="Products that disqualify signup bonus (exact names)")
    
    # Benefits
    cardmember_anniversary_benefit: Optional[str] = Field(None, description="Annual benefit description, single sentence")
    
    @field_validator('earning_categories')
    @classmethod
    def validate_all_other_exists(cls, v: List[EarningCategory]) -> List[EarningCategory]:
        """Ensure exactly one 'all_other' category exists."""
        all_other_count = sum(1 for cat in v if cat.category == 'all_other')
        if all_other_count == 0:
            raise ValueError("earning_categories must contain exactly one entry with category='all_other'")
        if all_other_count > 1:
            raise ValueError("earning_categories must contain exactly one entry with category='all_other', found multiple")
        return v


def validate_rewards_categories(rewards: RewardsExtended) -> None:
    """
    Post-validation checks for rewards categories.
    
    Raises:
        ValueError: If validation fails
    """
    # Check all categories are in ALLOWED_CATEGORIES
    for cat in rewards.earning_categories:
        if cat.category not in ALLOWED_CATEGORIES:
            raise ValueError(
                f"Category '{cat.category}' not in ALLOWED_CATEGORIES. "
                f"Use closest match from: {', '.join(ALLOWED_CATEGORIES)}"
            )
        
        # If category is 'other', notes must be non-empty
        if cat.category == 'other' and not cat.notes:
            raise ValueError("Category 'other' requires non-empty 'notes' field")


class RewardsHtmlFallback(BaseModel):
    """
    Reduced rewards schema for cards without RPA PDF.
    Extracted from product page HTML (earning_rates field).
    Lower confidence than RewardsExtended.
    """
    card_id: str
    card_name: str
    source_type: str = "product_page_html"
    source_text_length: int
    
    # Data quality
    data_quality_tier: Literal["tier_2_html"] = "tier_2_html"
    
    # Fields recoverable from product page marketing copy
    earning_categories: list[EarningCategory]
    cardmember_anniversary_benefit: Optional[str] = None
    
    # Explicitly NOT recoverable from product page
    # (marked for clarity - these require legal agreement PDF)
    fields_not_available: list[str] = Field(
        default_factory=lambda: [
            "redemption_options",
            "point_value_cents_baseline", 
            "transfer_partners",
            "bonus_disqualifying_products",
            "bonus_clawback_period_months",
            "points_expiration_months",
            "redemption_minimum_usd"
        ]
    )
    
    @model_validator(mode='after')
    def validate_categories(self):
        """Same validation as RewardsExtended."""
        validate_rewards_categories(self)
        return self
