import { ArrowDownRight, ArrowUpRight, Equal } from "lucide-react";
import { useId } from "react";
import type { Comparison } from "../types";

export function ComparisonSummary({ comparison }: { comparison: Comparison }) {
  const titleId = useId();
  return (
    <section className="comparison-summary" aria-labelledby={titleId}>
      <span className="eyebrow">THE TRADEOFFS</span>
      <h3 id={titleId}>How it compares</h3>
      <p className="comparison-pair">
        <strong>{comparison.card_name}</strong>
        <span>compared with</span>
        <strong>{comparison.alternative_name}</strong>
      </p>
      <p className="comparison-conclusion">{comparison.conclusion}</p>
      <div className="impact-list">
        {comparison.impacts.map((impact, i) => {
          const Icon =
            impact.direction === "positive"
              ? ArrowUpRight
              : impact.direction === "negative"
                ? ArrowDownRight
                : Equal;
          return (
            <div className={`impact ${impact.direction}`} key={i}>
              <div className="impact-label">
                <Icon size={15} />
                <span>
                  {impact.direction === "positive"
                    ? "Positive impact"
                    : impact.direction === "negative"
                      ? "Negative impact"
                      : "Worth weighing"}
                </span>
              </div>
              <h4>{impact.title}</h4>
              <p>{impact.detail}</p>
            </div>
          );
        })}
      </div>
      <p className="comparison-note">
        Examples use $100 of eligible spending, not an estimate of your budget.
        Your mix of purchases, reward limits and redemption choices affect the
        outcome.
      </p>
    </section>
  );
}
