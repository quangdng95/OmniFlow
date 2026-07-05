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
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true, amount: 0.2 }}
    transition={{ duration: 0.45, ease: "easeOut" }}
    style={{
      background: "white",
      border: "1px solid #f0f0f0",
      borderRadius: 12,
      boxShadow: "0px 1px 1px rgba(0,0,0,0.03), 0px 1px 3px rgba(0,0,0,0.02), 0px 2px 2px rgba(0,0,0,0.02)",
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
