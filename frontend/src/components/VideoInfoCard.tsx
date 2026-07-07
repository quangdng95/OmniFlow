import PlatformTag from "./PlatformTag";
import SectionCard from "./SectionCard";
import type { VideoInfo } from "../types";

interface VideoInfoCardProps {
  info: VideoInfo;
}

const VideoInfoCard = ({ info }: VideoInfoCardProps) => {
  return (
    <SectionCard>
      <div className="omniflow-video-info" style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        {info.thumbnail && (
          <img
            className="omniflow-thumb"
            src={info.thumbnail}
            referrerPolicy="no-referrer"
            alt={info.title}
            style={{
              aspectRatio: "280 / 158",
              borderRadius: 8,
              objectFit: "cover",
              flexShrink: 0,
              background: "#f3f4f6",
            }}
          />
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: 8, minWidth: 0, alignItems: "flex-start" }}>
          <PlatformTag platform={info.platform} />
          <div style={{ fontSize: 14, fontWeight: 600, wordBreak: "break-word", color: "#1f2937" }}>{info.title}</div>
          {info.uploader && <div style={{ fontSize: 12, color: "rgba(31, 41, 55, 0.65)" }}>{info.uploader}</div>}
          {info.duration && <div style={{ fontSize: 12, color: "rgba(31, 41, 55, 0.45)" }}>{info.duration}</div>}
        </div>
      </div>
    </SectionCard>
  );
};

export default VideoInfoCard;
