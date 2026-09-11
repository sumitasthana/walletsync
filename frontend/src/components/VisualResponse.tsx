import { ChevronDown } from "lucide-react";
import type { Card, Comparison } from "../types";
import { CardResult } from "./CardResult";
import { ComparisonSummary } from "./ComparisonSummary";

export function VisualResponse({
  cards,
  comparison,
  onAsk,
  disabled,
  preview = false,
}: {
  cards: Card[];
  comparison?: Comparison | null;
  onAsk: (text: string) => void;
  disabled: boolean;
  preview?: boolean;
}) {
  return (
    <section
      className="visual-response"
      aria-label={preview ? "Card preview" : "Your card matches"}
    >
      <div className="visual-heading">
        <div>
          <span className="eyebrow">
            {preview ? "A FIRST LOOK" : "YOUR SHORTLIST"}
          </span>
          <h2>
            Your card matches <span>{cards.length}</span>
          </h2>
        </div>
      </div>
      {comparison && (
        <div className="quick-take">
          <p className="takeaway-label">
            Where{" "}
            {cards
              .find((card) => card.card_id === comparison.card_id)
              ?.bank.toUpperCase() ?? "the featured card"}{" "}
            stands
          </p>
          <p className="takeaway-text">{comparison.conclusion}</p>
          <details className="tradeoff-details">
            <summary>
              See how they compare <ChevronDown size={14} />
            </summary>
            <ComparisonSummary comparison={comparison} />
          </details>
        </div>
      )}
      <div className="visual-cards">
        {cards.slice(0, 2).map((card, i) => (
          <div
            key={card.card_id}
            className={i === 0 ? "focus-card" : "alternative-card"}
          >
            <CardResult
              card={card}
              featured={card.card_id === comparison?.card_id}
              onAsk={onAsk}
              disabled={disabled}
            />
          </div>
        ))}
      </div>
      {cards.length > 2 && (
        <details className="more-matches">
          <summary>
            Explore {cards.length - 2} more cards <ChevronDown size={14} />
          </summary>
          <div className="extra-cards">
            {cards.slice(2).map((card) => (
              <CardResult
                key={card.card_id}
                card={card}
                featured={false}
                onAsk={onAsk}
                disabled={disabled}
              />
            ))}
          </div>
        </details>
      )}
      <p className="visual-note">Always check the latest issuer terms.</p>
    </section>
  );
}
