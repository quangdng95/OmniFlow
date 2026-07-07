import youtube from "../assets/tags/Youtube.svg";
import instagram from "../assets/tags/Instagram.svg";
import tiktok from "../assets/tags/Tiktok.svg";
import facebook from "../assets/tags/Facebook.svg";
import rednote from "../assets/tags/Rednote.svg";
import linkedin from "../assets/tags/LinkedIn.svg";
import threads from "../assets/tags/Threads.svg";
import type { Platform } from "../types";

const TAG_ICONS: Partial<Record<Platform, string>> = {
  YouTube: youtube,
  Instagram: instagram,
  TikTok: tiktok,
  Facebook: facebook,
  RedNote: rednote,
  LinkedIn: linkedin,
  Threads: threads,
};

interface PlatformTagProps {
  platform: Platform;
}

const PlatformTag = ({ platform }: PlatformTagProps) => {
  const icon = TAG_ICONS[platform];
  if (!icon) {
    return (
      <span
        style={{
          display: "inline-block",
          alignSelf: "flex-start",
          padding: "2px 8px",
          borderRadius: 4,
          background: "rgba(26,26,26,0.06)",
          fontSize: 12,
          fontWeight: 500,
        }}
      >
        {platform}
      </span>
    );
  }
  return <img src={icon} alt={platform} height={20} style={{ display: "block", alignSelf: "flex-start" }} />;
};

export default PlatformTag;
