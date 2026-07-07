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
      background: "rgba(17, 24, 39, 0.7)",
      backdropFilter: "blur(16px)",
      WebkitBackdropFilter: "blur(16px)",
      border: "1px solid rgba(255, 255, 255, 0.08)",
      borderRadius: 16,
      boxShadow: "0 10px 30px -10px rgba(0, 0, 0, 0.3)",
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
