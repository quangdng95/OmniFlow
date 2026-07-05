import PlatformTag from "./PlatformTag";
import SectionCard from "./SectionCard";
import type { VideoInfo } from "../types";
import { useLanguage } from "../i18n/LanguageContext";

interface VideoInfoCardProps {
  info: VideoInfo;
}

const VideoInfoCard = ({ info }: VideoInfoCardProps) => {
  const { t } = useLanguage();
  return (
    <SectionCard>
      <div className="omniflow-video-info" style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        {info.thumbnail && (
          <img
            className="omniflow-thumb"
            src={info.thumbnail}
            alt={info.title}
            style={{
              aspectRatio: "280 / 158",
              borderRadius: 8,
              objectFit: "cover",
              flexShrink: 0,
              background: "#e5e7eb",
            }}
          />
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: 8, minWidth: 0, alignItems: "flex-start" }}>
          <PlatformTag platform={info.platform} />
          <div style={{ fontSize: 12, display: "flex", gap: 4 }}>
            <span>{t.videoInfo.titleLabel}</span>
            <span style={{ fontWeight: 500, wordBreak: "break-word" }}>{info.title}</span>
          </div>
          {info.uploader && (
            <div style={{ fontSize: 12, display: "flex", gap: 4 }}>
              <span>{t.videoInfo.authorLabel}</span>
              <span style={{ fontWeight: 500 }}>{info.uploader}</span>
            </div>
          )}
          {info.duration && (
            <div style={{ fontSize: 12, display: "flex", gap: 4 }}>
              <span>{t.videoInfo.timeLabel}</span>
              <span style={{ fontWeight: 500 }}>{info.duration}</span>
            </div>
          )}
        </div>
      </div>
    </SectionCard>
  );
};

export default VideoInfoCard;
