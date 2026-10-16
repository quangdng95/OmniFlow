import type { Platform } from "../types";

// Full class strings (not built up piecemeal) so Tailwind can see every one.
// --block-bg / --block-fg let the controls inside a block (checkbox, switch,
// progress bar) pick up the block's colours without knowing which platform it is.
const BLOCK_TONES: Record<Platform, string> = {
  YouTube: "bg-platform-youtube [--block-bg:var(--platform-youtube)]",
  Instagram: "bg-platform-instagram [--block-bg:var(--platform-instagram)]",
  TikTok: "bg-platform-tiktok [--block-shadow:var(--on-ink)] [--block-bg:var(--platform-tiktok)]",
  Facebook: "bg-platform-facebook [--block-bg:var(--platform-facebook)]",
  RedNote: "bg-platform-rednote [--block-bg:var(--platform-rednote)]",
  LinkedIn: "bg-platform-linkedin [--block-bg:var(--platform-linkedin)]",
  Threads: "bg-platform-threads [--block-shadow:var(--on-ink)] [--block-bg:var(--platform-threads)]",
  Pinterest: "bg-platform-pinterest [--block-bg:var(--platform-pinterest)]",
  X: "bg-platform-x [--block-shadow:var(--on-ink)] [--block-bg:var(--platform-x)]",
  Link: "bg-platform-link [--block-shadow:var(--on-ink)] [--block-bg:var(--platform-link)]",
};

export type BlockTone = Platform | "ink" | "done";

const ON_DARK = "on-block text-on-ink [--block-fg:var(--on-ink)]";

export const blockToneClass = (tone: BlockTone): string => {
  if (tone === "ink") return `bg-ink [--block-bg:var(--ink)] [--block-shadow:var(--on-ink)] ${ON_DARK}`;
  if (tone === "done") return "on-block-light bg-lime text-ink [--block-bg:var(--lime)] [--block-fg:var(--ink)]";
  return `${BLOCK_TONES[tone] ?? BLOCK_TONES.Link} ${ON_DARK}`;
};
