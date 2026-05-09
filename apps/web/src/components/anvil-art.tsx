const FLAMES_A = `         )  (    )  (
        ( )( )  ( )( )
         )(  )  (  )(
            *      *`;

const FLAMES_B = `         (  )    (  )
          )(      )(
         (  *    *  )
            *      *`;

const ANVIL = `       _________________
      /                 \\____
      \\                      \\
       \\______________________/
            |          |
            |          |
        ____|__________|____
       /                    \\
      /______________________\\`;

const MARK_ANVIL = `  __/__\\__
 /________\\
   |____|`;

export function AnvilArtLarge({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`inline-flex flex-col items-center font-mono leading-[1.05] ${className}`}
    >
      <div className="relative h-[4.4em] w-full">
        <pre className="flame-a absolute inset-x-0 top-0 m-0 whitespace-pre text-center text-[12px] text-ember sm:text-sm">
          {FLAMES_A}
        </pre>
        <pre className="flame-b absolute inset-x-0 top-0 m-0 whitespace-pre text-center text-[12px] text-forge sm:text-sm">
          {FLAMES_B}
        </pre>
      </div>
      <pre className="m-0 whitespace-pre text-[12px] text-foreground/85 sm:text-sm">
        {ANVIL}
      </pre>
    </div>
  );
}

export function AnvilArtMark({ className = "" }: { className?: string }) {
  return (
    <pre
      aria-hidden="true"
      className={`m-0 whitespace-pre font-mono text-[8px] leading-[1.05] text-foreground/70 ${className}`}
    >
      {MARK_ANVIL}
    </pre>
  );
}
