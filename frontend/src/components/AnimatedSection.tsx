import type { CSSProperties, ReactNode } from "react";
import { motion } from "framer-motion";

interface AnimatedSectionProps {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  delay?: number;
}

const AnimatedSection = ({ children, className, style, delay = 0 }: AnimatedSectionProps) => (
  <motion.div
    className={className}
    style={style}
    initial={{ opacity: 0, y: 24 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.45, delay, ease: "easeOut" }}
  >
    {children}
  </motion.div>
);

export default AnimatedSection;
