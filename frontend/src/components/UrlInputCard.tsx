import { forwardRef, type ReactNode } from "react";
import { Input, Segmented, type InputRef } from "antd";
import { CloseCircleOutlined, CopyOutlined, LoadingOutlined } from "@ant-design/icons";
import SectionCard from "./SectionCard";
import { useLanguage } from "../i18n/LanguageContext";

export type UrlInputStatus = "idle" | "checking" | "result";

interface UrlInputCardProps {
  value: string;
  onChange: (value: string) => void;
  status: UrlInputStatus;
  onPaste: () => void;
  onClear: () => void;
  clearDisabled?: boolean;
  pasting?: boolean;
  // Quality selector - rendered in this same card, directly below the URL
  // field, once a scan has produced a non-empty quality list (Figma: node
  // 2420:19077 / 2428:26245 "URL" nests "Quality" right inside the URL card).
  qualities?: string[];
  qualityValue?: string;
  onQualityChange?: (value: string) => void;
  qualityDisabled?: boolean;
}

const UrlInputCard = forwardRef<InputRef, UrlInputCardProps>(
  (
    {
      value,
      onChange,
      status,
      onPaste,
      onClear,
      clearDisabled = false,
      pasting = false,
      qualities = [],
      qualityValue,
      onQualityChange,
      qualityDisabled = false,
    },
    ref
  ) => {
    const { t } = useLanguage();
    let suffix: ReactNode;
    if (status === "checking") {
      suffix = (
        <span style={{ display: "flex", alignItems: "center", gap: 4, color: "rgba(0, 0, 0, 0.45)", fontSize: 12, fontWeight: 500 }}>
          <LoadingOutlined spin /> {t.urlInput.checking}
        </span>
      );
    } else if (value !== "") {
      suffix = (
        <button
          type="button"
          onClick={onClear}
          disabled={clearDisabled}
          className="omniflow-suffix-btn-clear"
          style={{
            font: "inherit",
            display: "flex",
            alignItems: "center",
            gap: 4,
            fontSize: 10,
            fontWeight: 500,
            cursor: clearDisabled ? "not-allowed" : "pointer",
            background: "none",
            border: "none",
            padding: 0,
            opacity: clearDisabled ? 0.35 : 1,
          }}
        >
          <CloseCircleOutlined /> {t.urlInput.clearUrl}
        </button>
      );
    } else {
      suffix = (
        <button
          type="button"
          onClick={onPaste}
          disabled={pasting}
          className="omniflow-suffix-btn-paste"
          style={{
            font: "inherit",
            display: "flex",
            alignItems: "center",
            gap: 4,
            fontSize: 12,
            fontWeight: 500,
            cursor: pasting ? "default" : "pointer",
            background: "none",
            border: "none",
            padding: 0,
          }}
        >
          {pasting ? <LoadingOutlined spin /> : <CopyOutlined />} {pasting ? t.urlInput.pasting : t.urlInput.paste}
        </button>
      );
    }

    return (
      <SectionCard style={{ alignItems: "center" }}>
        <div style={{ width: "100%" }}>
          <div style={{ display: "flex", gap: 4, fontSize: 14, marginBottom: 4 }}>
            <span style={{ color: "#ff4d4f" }}>*</span>
            <span style={{ color: "rgba(31, 41, 55, 0.85)" }}>{t.urlInput.label}</span>
          </div>
          <Input
            ref={ref}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={t.urlInput.placeholder}
            suffix={suffix}
            disabled={status === "checking"}
          />
        </div>
        {qualities.length > 1 && (
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", width: "100%" }}>
            <span style={{ fontSize: 12 }}>{t.qualityAction.selectQuality}</span>
            <Segmented
              options={qualities}
              value={qualityValue}
              onChange={(v) => onQualityChange?.(v as string)}
              disabled={qualityDisabled}
            />
          </div>
        )}
      </SectionCard>
    );
  }
);

UrlInputCard.displayName = "UrlInputCard";

export default UrlInputCard;
