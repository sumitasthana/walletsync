"""Presentation order and factual spending comparisons across the bank catalog."""

from src.recommend.matcher import load_catalog, match_cards, parse_needs

FOCUS_BANK = "pnc"


def comparison_matches(text, top=6, catalog=None, selected=None):
    """Show one focus-bank candidate, then relevant alternatives. Scores stay intact."""
    catalog = load_catalog() if catalog is None else catalog
    ranked = match_cards(text, top=len(catalog), catalog=catalog)
    by_id = {card["card_id"]: card for card in ranked}
    preferred = [by_id[c["card_id"]] for c in (selected or []) if c.get("card_id") in by_id]
    candidates = preferred + ranked
    # Agent-selected general-purpose cards must not crowd out an explicitly
    # requested destination or loyalty program.
    candidates.sort(key=lambda card: -len(card.get("intent_matches", [])))
    focus = next((c for c in candidates if c["bank"] == FOCUS_BANK), None)
    result = [focus] if focus else []
    seen = {focus["card_id"]} if focus else set()
    for card in candidates:
        if card["bank"] != FOCUS_BANK and card["card_id"] not in seen:
            result.append(card)
            seen.add(card["card_id"])
    return result[:top]


def _rate(card, category):
    match = next((m for m in card.get("matched", []) if m["category"] == category), None)
    if match:
        return match.get("rate")
    return card.get("base_earn_rate") if category == "all_other" else None


def comparison_summary(cards, text):
    """Compare confirmed fees and same-currency rates, without projecting spending."""
    if len(cards) < 2 or cards[0].get("bank") != FOCUS_BANK:
        return None
    focus, alternative = cards[0], cards[1]
    needs = parse_needs(text)
    impacts = []
    def add(direction, title, detail):
        impacts.append({"direction": direction, "title": title, "detail": detail})

    categories = list(needs["categories"]) or ["all_other"]
    cash = "cash" in (focus.get("reward_currency") or "").lower()
    same_currency = cash and "cash" in (alternative.get("reward_currency") or "").lower()
    for category in categories:
        a, b = _rate(focus, category), _rate(alternative, category)
        if not same_currency or a is None or b is None:
            continue
        delta = float(a) - float(b)
        label = "everyday spending" if category == "all_other" else category.replace("_", " ")
        unit = "% cash back" if cash else " points per dollar"
        direction = "positive" if delta > 0 else "negative" if delta < 0 else "neutral"
        title = f"{'Higher' if delta > 0 else 'Lower' if delta < 0 else 'Equal'} rewards on {label}"
        detail = f"{float(a):g}{unit} versus {float(b):g}{unit}."
        if delta and cash:
            detail += f" That is ${abs(delta):g} {'more' if delta > 0 else 'less'} per $100 of eligible spending, before caps."
        conditions = []
        for card in (focus, alternative):
            for match in card.get("matched", []):
                if match["category"] != category:
                    continue
                terms = []
                if match.get("cap_usd") is not None:
                    terms.append(f"${match['cap_usd']:g} spending cap")
                if match.get("requires_activation"):
                    terms.append("activation required")
                if terms:
                    conditions.append(f"{card['card_name']}: {', '.join(terms)}.")
        add(direction, title, " ".join([detail] + conditions))

    a, b = focus.get("annual_fee_usd"), alternative.get("annual_fee_usd")
    if a is not None and b is not None:
        delta = float(b) - float(a)
        add("positive" if delta > 0 else "negative" if delta < 0 else "neutral",
            "Lower annual cost" if delta > 0 else "Higher annual cost" if delta < 0 else "Same annual fee",
            f"${float(a):g} versus ${float(b):g} per year." +
            (f" You pay ${abs(delta):g} {'less' if delta > 0 else 'more'} each year." if delta else ""))
    if needs["international"]:
        a, b = focus.get("foreign_transaction_fee_pct"), alternative.get("foreign_transaction_fee_pct")
        if a is not None and b is not None:
            delta = float(b) - float(a)
            add("positive" if delta > 0 else "negative" if delta < 0 else "neutral",
                "Lower cost abroad" if delta > 0 else "Higher cost abroad" if delta < 0 else "Same foreign transaction fee",
                f"{float(a):g}% versus {float(b):g}%." +
                (f" That is ${abs(delta):g} {'less' if delta > 0 else 'more'} in fees per $100 spent abroad." if delta else ""))
    if not same_currency:
        add("neutral", "Different ways to use rewards",
            f"{focus['card_name']} earns {focus.get('reward_currency') or 'rewards'}; "
            f"{alternative['card_name']} earns {alternative.get('reward_currency') or 'rewards'}. "
            "Compare where you can use those rewards, not just the earning rates.")
    positive = sum(item["direction"] == "positive" for item in impacts)
    negative = sum(item["direction"] == "negative" for item in impacts)
    conclusion = (
        "This card offers " + ", ".join(i["title"].lower() for i in impacts if i["direction"] == "positive") +
        ". The tradeoff is " + ", ".join(i["title"].lower() for i in impacts if i["direction"] == "negative") + "."
        if positive and negative else
        "This card has an advantage on the costs and rewards compared below."
        if positive else
        "The alternative has an advantage on the features compared below."
        if negative else
        "These features do not establish a clear advantage. Consider the benefits you will actually use."
    )
    return {"card_id": focus["card_id"], "card_name": focus["card_name"],
            "alternative_name": alternative["card_name"], "impacts": impacts,
            "conclusion": conclusion}
