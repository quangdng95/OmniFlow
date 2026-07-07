import type { CSSProperties, ReactNode } from "react";
import { motion } from "framer-motion";

interface SectionCardProps {
  children: ReactNode;
  style?: CSSProperties;
}

const SectionCard = ({ children, style }: SectionCardProps) => (
  <motion.div
    className="omniflow-card"
    initial={{ opacity: 0, y: 24 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.45, ease: "easeOut" }}
    style={{
      background: "rgba(255, 255, 255, 0.85)",
      backdropFilter: "blur(12px)",
      WebkitBackdropFilter: "blur(12px)",
      border: "1px solid rgba(0, 0, 0, 0.05)",
      borderRadius: 16,
      boxShadow: "0 8px 30px rgba(0, 0, 0, 0.02), 0 1px 2px rgba(0, 0, 0, 0.01)",
      width: "100%",
      display: "flex",
      flexDirection: "column",
      gap: 16,
      ...style,
    }}
  >
    {children}
  </motion.div>
);

export default SectionCard;
