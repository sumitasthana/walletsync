export function BrandMark({ size = 40 }: { size?: number }) {
  return (
    <img
      className="brand-symbol"
      src={`${import.meta.env.BASE_URL}brand/walletsync-mark.svg`}
      width={size}
      height={size}
      alt=""
      aria-hidden="true"
    />
  );
}

export function Wordmark({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className={`wordmark${compact ? " compact" : ""}`}
      role="img"
      aria-label="WalletSync"
    >
      <span className="wordmark-wallet">wallet</span>
      <span className="wordmark-sync">sync</span>
    </span>
  );
}
