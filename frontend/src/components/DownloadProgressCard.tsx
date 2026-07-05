import { Button, Progress } from "antd";
import { CloseCircleOutlined } from "@ant-design/icons";
import SectionCard from "./SectionCard";
import { useLanguage } from "../i18n/LanguageContext";

interface DownloadProgressCardProps {
  percent: number;
  onCancel: () => void;
}

const DownloadProgressCard = ({ percent, onCancel }: DownloadProgressCardProps) => {
  const { t } = useLanguage();
  return (
    <SectionCard>
      <Progress percent={percent} showInfo={false} strokeColor="#1677ff" />
      <Button block danger type="primary" icon={<CloseCircleOutlined />} onClick={onCancel}>
        {t.downloadProgress.cancelDownload}
      </Button>
    </SectionCard>
  );
};

export default DownloadProgressCard;
