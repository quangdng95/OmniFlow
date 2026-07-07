import { Button } from "antd";
import { DownloadOutlined, RedoOutlined } from "@ant-design/icons";
import SectionCard from "./SectionCard";
import { useLanguage } from "../i18n/LanguageContext";

export type ActionState = "idle" | "downloading" | "done";

interface QualityActionCardProps {
  actionState: ActionState;
  onAction: () => void;
}

// Quality selection itself lives in UrlInputCard now (Figma nests the
// "Quality" segmented control directly inside the URL card, not a separate
// downstream one) - this card is just the Start Download / Downloading /
// Download Again action button.
const QualityActionCard = ({ actionState, onAction }: QualityActionCardProps) => {
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

  return <SectionCard>{button}</SectionCard>;
};

export default QualityActionCard;
