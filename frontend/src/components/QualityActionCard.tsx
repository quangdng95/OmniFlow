import { Button, Segmented } from "antd";
import { DownloadOutlined, RedoOutlined } from "@ant-design/icons";
import SectionCard from "./SectionCard";
import { useLanguage } from "../i18n/LanguageContext";

export type ActionState = "idle" | "downloading" | "done";

interface QualityActionCardProps {
  qualities: string[];
  value: string;
  onChange: (value: string) => void;
  actionState: ActionState;
  onAction: () => void;
}

const QualityActionCard = ({ qualities, value, onChange, actionState, onAction }: QualityActionCardProps) => {
  const { t } = useLanguage();
  let button;
  if (actionState === "downloading") {
    button = (
      <Button block type="primary" disabled icon={<DownloadOutlined />}>
        {t.qualityAction.downloading}
      </Button>
    );
  } else if (actionState === "done") {
    button = (
      <Button block ghost type="primary" icon={<RedoOutlined />} onClick={onAction}>
        {t.qualityAction.downloadAgain}
      </Button>
    );
  } else {
    button = (
      <Button block type="primary" icon={<DownloadOutlined />} onClick={onAction}>
        {t.qualityAction.startDownload}
      </Button>
    );
  }

  return (
    <SectionCard>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span style={{ fontSize: 12 }}>{t.qualityAction.videoQuality}</span>
        <Segmented
          options={qualities}
          value={value}
          onChange={(v) => onChange(v as string)}
          disabled={actionState === "downloading"}
        />
      </div>
      {button}
    </SectionCard>
  );
};

export default QualityActionCard;
