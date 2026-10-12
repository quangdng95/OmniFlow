import { Ban, Loader2, TriangleAlert } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useLanguage } from "../i18n/LanguageContext";

interface CheckingStatusCardProps {
  seconds: number;
  onCancel: () => void;
  showKeychainHint?: boolean;
}

const CheckingStatusCard = ({ seconds, onCancel, showKeychainHint }: CheckingStatusCardProps) => {
  const { t } = useLanguage();
  return (
    <Card className="w-full select-none">
      <CardContent className="flex flex-col gap-3">
        <span className="flex items-center gap-2 text-sm font-medium">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          {t.checkingStatus.checkingLink} ({seconds}s)
        </span>
        {showKeychainHint && (
          <Alert>
            <TriangleAlert />
            <AlertDescription>{t.checkingStatus.keychainHint}</AlertDescription>
          </Alert>
        )}
        <Button variant="outline" className="w-full" onClick={onCancel}>
          <Ban />
          {t.checkingStatus.cancel}
        </Button>
      </CardContent>
    </Card>
  );
};

export default CheckingStatusCard;
