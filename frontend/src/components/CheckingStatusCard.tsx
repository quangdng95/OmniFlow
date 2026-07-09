import { Ban } from "lucide-react";
import { Button } from "@/components/ui/button";
import SectionCard from "./SectionCard";
import { useLanguage } from "../i18n/LanguageContext";

interface CheckingStatusCardProps {
  seconds: number;
  onCancel: () => void;
  showKeychainHint?: boolean;
}

const CheckingStatusCard = ({ seconds, onCancel, showKeychainHint }: CheckingStatusCardProps) => {
  const { t } = useLanguage();
  return (
    <SectionCard style={{ alignItems: "flex-start" }} className="p-4 bg-white/90 border border-neutral-200 shadow-sm rounded-xl">
      <span className="text-[#0d9585] text-sm font-semibold select-none">
        {t.checkingStatus.checkingLink} ({seconds}s)
      </span>
      {showKeychainHint && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 m-0 leading-relaxed">
          {t.checkingStatus.keychainHint}
        </p>
      )}
      <Button
        variant="destructive"
        className="w-full flex items-center justify-center gap-1.5 bg-red-50 text-red-600 hover:bg-red-100 hover:text-red-700 border-none shadow-none"
        onClick={onCancel}
      >
        <Ban className="h-4 w-4" />
        {t.checkingStatus.cancel}
      </Button>
    </SectionCard>
  );
};

export default CheckingStatusCard;
