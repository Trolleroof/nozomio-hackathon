const LARGE_ANVIL = String.raw`
            (  .  )
          (    )  )
           )  (  ,
       _.--""--._
      /  ANVIL   \
   __/____________\__
  /__________________\
       ||      ||
       ||______||
      /__________\
`;

const MARK_ANVIL = String.raw`   _.--""--._
  /__________\
   ||______||`;

export function AnvilArtLarge({ className = "" }: { className?: string }) {
  return (
    <pre
      aria-hidden="true"
      className={`crucible-gradient-text whitespace-pre font-mono text-[12px] leading-[1.05] sm:text-sm ${className}`}
    >
      {LARGE_ANVIL}
    </pre>
  );
}

export function AnvilArtMark({ className = "" }: { className?: string }) {
  return (
    <pre
      aria-hidden="true"
      className={`crucible-gradient-text whitespace-pre font-mono text-[8px] leading-[1.05] ${className}`}
    >
      {MARK_ANVIL}
    </pre>
  );
}
