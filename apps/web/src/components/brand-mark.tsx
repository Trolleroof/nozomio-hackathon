type BrandMarkProps = {
  className?: string;
  iconClassName?: string;
  showText?: boolean;
  textClassName?: string;
};

export function BrandMark({
  className = "",
  iconClassName = "",
  showText = true,
  textClassName = ""
}: BrandMarkProps) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <img
        alt=""
        aria-hidden="true"
        className={`h-8 w-8 rounded-md border border-border-strong bg-surface-raised object-cover shadow-[0_0_18px_rgba(232,104,38,0.16)] ring-1 ring-accent/20 ${iconClassName}`}
        src="/brand/crucible-logo.png"
      />
      {showText ? (
        <span className={`crucible-pixel-wordmark text-[13px] ${textClassName}`}>
          <span className="crucible-gradient-text">crucible</span>
          <span className="text-foreground/85"> compute</span>
        </span>
      ) : null}
    </span>
  );
}
