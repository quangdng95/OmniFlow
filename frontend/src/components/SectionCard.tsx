import type { CSSProperties, ReactNode } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface SectionCardProps {
  children: ReactNode;
  style?: CSSProperties;
  className?: string;
}

const SectionCard = ({ children, style, className }: SectionCardProps) => (
  <motion.div
    className={cn(
      "w-full flex flex-col gap-4 border-[3px] border-ink bg-card p-4 md:p-6",
      className
    )}
    initial={{ opacity: 0, y: 24 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.45, ease: "easeOut" }}
    style={style}
  >
    {children}
  </motion.div>
);

export default SectionCard;
