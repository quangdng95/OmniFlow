import { Button } from "antd";
import { CheckCircleFilled, DownloadOutlined, FolderOpenOutlined } from "@ant-design/icons";
import SectionCard from "./SectionCard";
import { useLanguage } from "../i18n/LanguageContext";

interface DownloadSuccessCardProps {
  filename: string;
  onOpenFolder?: () => void;
  downloadUrl?: string;
  // When set (batch downloads), replaces the "Saved: <filename>" line with a
  // custom summary like "Saved 5 of 6 videos".
  label?: string;
}

const DownloadSuccessCard = ({ filename, onOpenFolder, downloadUrl, label }: DownloadSuccessCardProps) => {
  const { t } = useLanguage();
  return (
    <SectionCard>
      <div style={{ display: "flex", alignItems: "center", gap: 4, color: "#0d9585", fontSize: 12 }}>
        <CheckCircleFilled />
        {label ? (
          <span style={{ fontWeight: 500, wordBreak: "break-word" }}>{label}</span>
        ) : (
          <>
            <span>{t.downloadSuccess.saved}</span>
            <span style={{ fontWeight: 500, wordBreak: "break-word" }}>{filename}</span>
          </>
        )}
      </div>
      {onOpenFolder && (
        <Button block type="primary" icon={<FolderOpenOutlined />} onClick={onOpenFolder}>
          {t.downloadSuccess.openFolder}
        </Button>
      )}
      {downloadUrl && (
        <Button block type="primary" icon={<DownloadOutlined />} href={downloadUrl}>
          {t.downloadSuccess.download}
        </Button>
      )}
    </SectionCard>
  );
};

export default DownloadSuccessCard;
