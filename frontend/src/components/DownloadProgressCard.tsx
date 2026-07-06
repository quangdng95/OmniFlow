import { Button, Progress } from "antd";
import { CloseCircleOutlined } from "@ant-design/icons";
import SectionCard from "./SectionCard";
import { useLanguage } from "../i18n/LanguageContext";

interface DownloadProgressCardProps {
  percent: number;
  onCancel: () => void;
  // Optional status line (e.g. batch "Downloading item 2 of 10…").
  status?: string;
}

const DownloadProgressCard = ({ percent, onCancel, status }: DownloadProgressCardProps) => {
  const { t } = useLanguage();
  return (
    <SectionCard>
      {status && <p style={{ fontSize: 13, margin: 0, color: "rgba(0,0,0,0.65)" }}>{status}</p>}
      <Progress percent={percent} showInfo={false} strokeColor="#1677ff" />
      <Button block danger type="primary" icon={<CloseCircleOutlined />} onClick={onCancel}>
        {t.downloadProgress.cancelDownload}
      </Button>
    </SectionCard>
  );
};

export default DownloadProgressCard;
