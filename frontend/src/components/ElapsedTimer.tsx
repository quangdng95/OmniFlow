import { useEffect, useState } from "react";
import { formatElapsed } from "../lib/formatElapsed";

interface ElapsedTimerProps {
  // Accessible name for the counter ("Elapsed time").
  label: string;
}

// Counts up from the moment it mounts: mount it when processing starts and
// unmount it when that ends (finished, cancelled, failed), which stops and
// cleans the interval. The value comes from a stored start timestamp, not from
// adding up ticks, so a throttled background tab still shows the real time.
// role="timer" is aria-live="off" by default, so a screen reader is not
// interrupted every second.
const ElapsedTimer = ({ label }: ElapsedTimerProps) => {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const start = Date.now();
    const id = setInterval(() => setSeconds(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <span role="timer" aria-live="off" aria-label={label} className="tabular-nums [font-variant-numeric:tabular-nums]">
      {formatElapsed(seconds)}
    </span>
  );
};

export default ElapsedTimer;
