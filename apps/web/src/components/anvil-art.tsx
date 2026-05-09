const FLAMES_A = String.raw`        (   )       (   )       (   )
         ) (         ) (         ) (
       _(   )_     _(   )_     _(   )_
      /  \|/  |   |  \|/  |   |  \|/  |
         ***         ***         ***`;

const FLAMES_B = String.raw`         ) (         ) (         ) (
       _(   )_     _(   )_     _(   )_
      /  \|/  |   |  \|/  |   |  \|/  |
        ** **       ** **       ** **
         * *         * *         * *`;

const ANVIL = String.raw`          ____________________________________
     ____/####################################\____
    /##############################################|
   /###### ________________________________ #######|
   \######|================================|########/
    \#####|################################|#######/
     \____|################################|______/
           |###########________###########|
           |##########|        |##########|
        ___|##########|________|##########|___
       /########################################|
      /##########################################|
     \____________________________________________/`;

const MARK_ANVIL = `  __/__\\__
 /________\\
   |____|`;

export function AnvilArtLarge({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`inline-flex flex-col items-center font-mono leading-[1.05] ${className}`}
    >
      <div className="relative h-[5.4em] w-full">
        <pre className="flame-a absolute inset-x-0 top-0 m-0 whitespace-pre text-center text-[11px] text-ember sm:text-sm lg:text-[15px]">
          {FLAMES_A}
        </pre>
        <pre className="flame-b absolute inset-x-0 top-0 m-0 whitespace-pre text-center text-[11px] text-forge sm:text-sm lg:text-[15px]">
          {FLAMES_B}
        </pre>
      </div>
      <pre className="m-0 whitespace-pre text-[11px] text-foreground/85 sm:text-sm lg:text-[15px]">
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
