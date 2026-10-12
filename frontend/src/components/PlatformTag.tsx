import { Play } from "lucide-react";
import type { Platform } from "../types";

interface PlatformTagProps {
  platform: Platform;
}

// A hard-edged outline pill in the surrounding text colour, so it reads on any
// platform block (and on the plain paper background, on the History page).
const PlatformTag = ({ platform }: PlatformTagProps) => (
  <span className="inline-flex w-fit items-center gap-2 self-start border-[3px] border-current px-2.5 py-0.5 font-display text-base font-bold uppercase">
    <Play className="h-3.5 w-3.5 fill-current" aria-hidden />
    {platform}
  </span>
);

export default PlatformTag;
