// Class strings shared by the V3 colour blocks (single video, playlist, checking).
// Kept whole so Tailwind's scanner sees them.

export const cta =
  "inline-flex min-h-16 w-full cursor-pointer select-none items-center justify-center gap-3 border-[3px] border-ink px-6 font-display text-xl font-bold uppercase transition-[transform,box-shadow] disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto sm:min-w-[20rem] md:text-[1.375rem]";

// Primary action: white slab with a hard ink shadow that "presses" on click.
export const ctaLight = `${cta} bg-white text-ink shadow-[6px_6px_0_var(--block-shadow,var(--ink))] hover:bg-signal active:translate-x-[3px] active:translate-y-[3px] active:shadow-[3px_3px_0_var(--block-shadow,var(--ink))]`;

// Secondary action: outline in the block's own text colour.
export const ctaGhost = `${cta} border-current bg-transparent text-current hover:bg-white/15`;

// Retry on a dark block.
export const ctaSignal = `${cta} bg-signal text-ink shadow-[6px_6px_0_var(--on-ink)] hover:bg-signal-hover active:translate-x-[3px] active:translate-y-[3px] active:shadow-[3px_3px_0_var(--on-ink)]`;

export const linkButton =
  "inline-flex min-h-11 min-w-11 cursor-pointer select-none items-center gap-2 bg-transparent px-1 font-display text-[1.0625rem] font-bold text-current underline underline-offset-4";

// Per-row action in a list.
export const rowButton =
  "inline-flex min-h-12 cursor-pointer select-none items-center gap-1.5 whitespace-nowrap border-[3px] border-current bg-transparent px-4 font-display text-base font-bold uppercase text-current hover:bg-white hover:text-ink disabled:cursor-not-allowed disabled:opacity-60";

export const bigStatus =
  "m-0 font-display text-[clamp(2.5rem,12vw,7.5rem)] leading-[0.95] font-bold tracking-[-0.05em] uppercase [:lang(vi)_&]:leading-[1.05]";

// Progress bar: a bordered slab filled with the block's text colour.
export const progressSlab =
  "w-full select-none flex-nowrap gap-0 [&_[data-slot=progress-track]]:h-7 [&_[data-slot=progress-track]]:rounded-none [&_[data-slot=progress-track]]:border-[3px] [&_[data-slot=progress-track]]:border-current [&_[data-slot=progress-track]]:bg-transparent [&_[data-slot=progress-indicator]]:bg-current";

// shadcn Checkbox / Switch recoloured from the block's --block-fg / --block-bg.
export const blockCheckbox =
  "size-6 shrink-0 rounded-none border-[3px] border-(--block-fg) bg-transparent after:-inset-y-3 data-checked:border-(--block-fg) data-checked:bg-(--block-fg) data-checked:text-(--block-bg)";

export const blockSwitch =
  "data-[size=default]:h-8 data-[size=default]:w-14 rounded-none border-[3px] border-(--block-fg) data-checked:bg-(--block-fg) data-unchecked:bg-transparent [&>span]:rounded-none [&>span]:bg-(--block-fg) group-data-[size=default]/switch:[&>span]:size-5 data-checked:[&>span]:bg-(--block-bg)";
