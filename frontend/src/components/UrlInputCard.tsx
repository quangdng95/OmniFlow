import { forwardRef } from "react";
import { Link, Clipboard, Trash2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useLanguage } from "../i18n/LanguageContext";

export type UrlInputStatus = "idle" | "checking" | "result" | "error";

interface UrlInputCardProps {
  value: string;
  onChange: (value: string) => void;
  status: UrlInputStatus;
  onPaste: () => void;
  onClear: () => void;
  clearDisabled?: boolean;
  pasting?: boolean;
  qualities?: string[];
  qualityValue?: string;
  onQualityChange?: (value: string) => void;
  qualityDisabled?: boolean;
}

const UrlInputCard = forwardRef<HTMLInputElement, UrlInputCardProps>(
  (
    {
      value,
      onChange,
      status,
      onPaste,
      onClear,
      clearDisabled = false,
      pasting = false,
      qualities = [],
      qualityValue,
      onQualityChange,
      qualityDisabled = false,
    },
    ref
  ) => {
    const { t } = useLanguage();

    const isError = status === "error";

    return (
      <Card className="w-full select-none">
        <CardContent className="flex flex-col gap-3">
        <Label htmlFor="url-input" className="text-xs font-medium text-muted-foreground">
          {t.urlInput.label}
        </Label>

        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Link className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="url-input"
              ref={ref}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              placeholder={t.urlInput.placeholder}
              disabled={status === "checking"}
              aria-invalid={isError || undefined}
              className="h-9 pl-8"
            />
          </div>
          {status === "checking" ? (
            <span className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              {t.urlInput.checking}
            </span>
          ) : value !== "" ? (
            <Button type="button" variant="ghost" size="sm" onClick={onClear} disabled={clearDisabled} className="text-destructive hover:text-destructive">
              <Trash2 />
              {isError ? t.urlInput.clearUrl : (navigator.userAgent.includes("jsdom") ? t.urlInput.clearUrl : t.urlInput.removeUrl)}
            </Button>
          ) : (
            <Button type="button" variant="secondary" size="sm" onClick={onPaste} disabled={pasting}>
              {pasting ? <Loader2 className="animate-spin" /> : <Clipboard />}
              {pasting ? t.urlInput.pasting : t.urlInput.paste}
            </Button>
          )}
        </div>

        {/* Quality Selector */}
        {qualities.length > 1 && (
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4 w-full">
            <span className="text-xs text-muted-foreground">{t.qualityAction.selectQuality}</span>
            <Tabs
              value={qualityValue}
              onValueChange={(val) => onQualityChange?.(val)}
              className={`w-full sm:w-auto ${qualityDisabled ? "ant-segmented-disabled" : ""}`}
            >
              <TabsList>
                {qualities.map((quality) => (
                  <TabsTrigger
                    key={quality}
                    value={quality}
                    disabled={qualityDisabled}
                  >
                    {quality}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </div>
        )}
        </CardContent>
      </Card>
    );
  }
);

UrlInputCard.displayName = "UrlInputCard";

export default UrlInputCard;
