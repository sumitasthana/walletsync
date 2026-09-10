import { useState } from "react";
import { ArrowRight, ChevronDown, CreditCard } from "lucide-react";
import type { Card } from "../types";

export function CardResult({
  card,
  featured,
  onAsk,
  disabled,
}: {
  card: Card;
  featured: boolean;
  onAsk: (text: string) => void;
  disabled: boolean;
}) {
  const [imageFailed, setImageFailed] = useState(false);
  const currency =
    card.reward_currency?.toLowerCase().includes("cash") ||
    card.reward_currency === "Disney Rewards Dollars"
      ? "%"
      : "x";
  return (
    <article className={`card-result ${featured ? "first" : ""}`}>
      <div className="card-heading">
        {featured && <span className="eyebrow">IN FOCUS</span>}
        <span className="bank-label">{card.bank}</span>
      </div>
      <div className="card-overview">
        <div className={`card-art ${card.bank}`}>
          {card.has_image && !imageFailed ? (
            <img
              src={`/card-images/${encodeURIComponent(card.bank)}/${encodeURIComponent(card.card_id)}.png`}
              alt=""
              loading="lazy"
              onError={() => setImageFailed(true)}
            />
          ) : (
            <div className="card-fallback">
              <CreditCard size={24} />
              <span>{card.bank}</span>
            </div>
          )}
        </div>
        <div>
          <h3>{card.card_name}</h3>
          {card.annual_fee_usd != null && (
            <p>
              {card.annual_fee_usd === 0
                ? "No annual fee"
                : `$${card.annual_fee_usd.toLocaleString()} annual fee`}
            </p>
          )}
        </div>
      </div>
      <div className="reward-list">
        {card.matched.slice(0, 3).map((m) => (
          <div className="reward" key={m.category}>
            <strong>
              {m.rate}
              {currency}
            </strong>
            <span>
              {m.category.replaceAll("_", " ")}
              {m.requires_activation && <small>Activation required</small>}
              {m.notes && <small>{m.notes}</small>}
              {m.cap_usd != null && (
                <small>Cap: ${m.cap_usd.toLocaleString()}</small>
              )}
            </span>
          </div>
        ))}
      </div>
      {card.reward_currency === "Disney Rewards Dollars" && (
        <p className="reward-currency">Earned in Disney Rewards Dollars</p>
      )}
      <details>
        <summary>
          Fees & rewards <ChevronDown size={14} />
        </summary>
        <div className="card-details">
          {card.foreign_transaction_fee_pct != null && (
            <p>Foreign transaction fee: {card.foreign_transaction_fee_pct}%</p>
          )}
          <button
            className="text-button"
            disabled={disabled}
            onClick={() =>
              onAsk(
                `How does ${card.card_name} fit my spending needs? Explain the benefits and tradeoffs that matter for me.`,
              )
            }
          >
            Ask about this card <ArrowRight size={14} />
          </button>
        </div>
      </details>
    </article>
  );
}
