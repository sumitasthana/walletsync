export type Message = { role: "user" | "assistant"; content: string };
export type Match = {
  category: string;
  rate: number;
  cap_usd: number | null;
  requires_activation: boolean;
  notes?: string | null;
};
export type Card = {
  card_id: string;
  card_name: string;
  bank: string;
  reward_currency: string | null;
  annual_fee_usd: number | null;
  foreign_transaction_fee_pct: number | null;
  has_image: boolean;
  score: number;
  matched: Match[];
};
export type ChatResponse = {
  reply: string;
  cards: Card[];
  source: "live" | "agent";
  error?: string;
  comparison?: Comparison | null;
};

export type Comparison = {
  card_id: string;
  card_name: string;
  alternative_name: string;
  conclusion: string;
  impacts: {
    direction: "positive" | "negative" | "neutral";
    title: string;
    detail: string;
  }[];
};
