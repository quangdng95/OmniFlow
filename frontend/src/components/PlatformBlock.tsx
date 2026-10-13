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

// V3's full-bleed colour block: the colour spans the whole width of its parent
// (the page, which is full width) while the content sits in the shared
// .page-container column, so it lines up with the header, input and footer.
const PlatformBlock = ({ tone, children, className, role }: PlatformBlockProps) => (
  <motion.section
    role={role}
    className={cn(
      "w-full border-y-[3px] border-ink py-7 md:py-9",
      blockToneClass(tone),
      className
    )}
    initial={{ opacity: 0, y: 24 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.3, ease: "easeOut" }}
  >
    <div className="page-container flex flex-col gap-5">{children}</div>
  </motion.section>
);

export default PlatformBlock;
