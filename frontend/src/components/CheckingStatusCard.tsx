import { Loader2, TriangleAlert } from "lucide-react";
import PlatformBlock from "./PlatformBlock";
import { bigStatus, linkButton } from "../lib/blockStyles";
import { useLanguage } from "../i18n/LanguageContext";

interface CheckingStatusCardProps {
  seconds: number;
  onCancel: () => void;
  showKeychainHint?: boolean;
}

const CheckingStatusCard = ({ seconds, onCancel, showKeychainHint }: CheckingStatusCardProps) => {
  const { t } = useLanguage();
  return (
    <PlatformBlock tone="ink" role="status">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <Loader2 className="h-10 w-10 shrink-0 animate-spin" aria-hidden />
        <p className={`${bigStatus} text-[clamp(2rem,9vw,5.5rem)]`}>
          {t.checkingStatus.checkingLink} ({seconds}s)
        </p>
      </div>
      {showKeychainHint && (
        <p className="m-0 flex max-w-[42em] items-start gap-3 text-lg leading-snug">
          <TriangleAlert className="mt-1 h-5 w-5 shrink-0 text-signal" aria-hidden />
          {t.checkingStatus.keychainHint}
        </p>
      )}
      <div>
        <button type="button" onClick={onCancel} className={linkButton}>
          {t.checkingStatus.cancel}
        </button>
      </div>
    </PlatformBlock>
  );
};

export default CheckingStatusCard;
