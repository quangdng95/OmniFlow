import { forwardRef, type ReactNode } from "react";
import { Input, type InputRef } from "antd";
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
}

const UrlInputCard = forwardRef<InputRef, UrlInputCardProps>(
  ({ value, onChange, status, onPaste, onClear, clearDisabled = false, pasting = false }, ref) => {
    const { t } = useLanguage();
    let suffix: ReactNode;
    if (status === "checking") {
      suffix = (
        <span style={{ display: "flex", alignItems: "center", gap: 4, color: "rgba(26,26,26,0.4)", fontSize: 12, fontWeight: 500 }}>
          <LoadingOutlined spin /> {t.urlInput.checking}
        </span>
      );
    } else if (value !== "") {
      suffix = (
        <button
          type="button"
          onClick={onClear}
          disabled={clearDisabled}
          style={{
            font: "inherit",
            display: "flex",
            alignItems: "center",
            gap: 4,
            color: clearDisabled ? "rgba(26,26,26,0.25)" : "#ff4d4f",
            fontSize: 10,
            fontWeight: 500,
            cursor: clearDisabled ? "not-allowed" : "pointer",
            background: "none",
            border: "none",
            padding: 0,
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
          style={{
            font: "inherit",
            display: "flex",
            alignItems: "center",
            gap: 4,
            color: "#0d9585",
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
            <span style={{ color: "rgba(26,26,26,0.92)" }}>{t.urlInput.label}</span>
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
      </SectionCard>
    );
  }
);

UrlInputCard.displayName = "UrlInputCard";

export default UrlInputCard;
