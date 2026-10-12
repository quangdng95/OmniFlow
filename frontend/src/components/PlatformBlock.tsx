import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { blockToneClass, type BlockTone } from "../lib/platform";

interface PlatformBlockProps {
  tone: BlockTone;
  children: ReactNode;
  className?: string;
  role?: "status" | "alert";
}

// V3's full-bleed colour block: it breaks out of the 1200px page column to the
// window edges (the parent is centred, so 50% - 50vw lands on the window edge)
// while its content stays on the same column as everything else.
const PlatformBlock = ({ tone, children, className, role }: PlatformBlockProps) => (
  <motion.section
    role={role}
    className={cn(
      "w-screen border-y-[3px] border-ink px-5 py-7 [margin-inline:calc(50%-50vw)] md:px-10 md:py-9",
      blockToneClass(tone),
      className
    )}
    initial={{ opacity: 0, y: 24 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.3, ease: "easeOut" }}
  >
    <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-5">{children}</div>
  </motion.section>
);

export default PlatformBlock;
