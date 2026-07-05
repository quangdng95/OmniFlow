import { Button } from "antd";
import { StopOutlined } from "@ant-design/icons";
import SectionCard from "./SectionCard";
import { useLanguage } from "../i18n/LanguageContext";

interface CheckingStatusCardProps {
  seconds: number;
  onCancel: () => void;
}

const CheckingStatusCard = ({ seconds, onCancel }: CheckingStatusCardProps) => {
  const { t } = useLanguage();
  return (
    <SectionCard style={{ alignItems: "flex-start" }}>
      <span style={{ color: "#0d9585", fontSize: 14 }}>
        {t.checkingStatus.checkingLink} ({seconds}s)
      </span>
      <Button
        block
        icon={<StopOutlined />}
        onClick={onCancel}
        style={{ background: "#fff2f0", color: "#ff4d4f", border: "none" }}
      >
        {t.checkingStatus.cancel}
      </Button>
    </SectionCard>
  );
};

export default CheckingStatusCard;
