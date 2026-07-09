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
      "bg-white/85 backdrop-blur-[12px] border border-black/5 rounded-2xl shadow-[0_8px_30px_rgba(0,0,0,0.02),_0_1px_2px_rgba(0,0,0,0.01)] w-full flex flex-col gap-4 p-4",
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
