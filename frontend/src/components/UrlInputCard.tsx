import { forwardRef } from "react";
import { Clipboard, Trash2, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
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

// The V3 "command bar": a hard-edged ink frame with a blue offset shadow, the
// field on top and one big action below (mobile) / beside it (>= md). The link
// is checked automatically a moment after it changes, so the action is Paste
// (empty), Clear (filled) or a "Checking" status - never a separate Check button.
const barButton =
  "inline-flex min-h-[60px] flex-1 basis-1/2 cursor-pointer select-none items-center justify-center gap-2.5 border-0 px-8 font-display text-lg font-bold uppercase focus-on-ink focus-inset md:min-h-[84px] md:flex-none md:basis-auto md:text-xl";

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
      <div className="flex w-full flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor="url-input" className="font-display text-lg leading-tight font-bold text-ink">
            {t.urlInput.fieldLabel}
          </Label>

          <div className="flex flex-wrap bg-ink shadow-hard md:flex-nowrap">
            <Input
              id="url-input"
              ref={ref}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              placeholder={t.urlInput.placeholder}
              disabled={status === "checking"}
              aria-invalid={isError || undefined}
              type="url"
              inputMode="url"
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              className={cn(
                "focus-inset h-[68px] min-w-0 flex-[1_1_100%] rounded-none border-[3px] border-ink bg-white px-[18px] text-xl font-medium text-ink md:h-[84px] md:flex-1 md:px-7 md:text-[1.625rem]",
                "aria-invalid:bg-invalid aria-invalid:ring-0 disabled:opacity-100 disabled:bg-muted"
              )}
            />
            {status === "checking" ? (
              <span
                role="status"
                className="inline-flex min-h-[60px] flex-1 basis-1/2 select-none items-center justify-center gap-2.5 px-8 font-display text-lg font-bold text-on-ink uppercase md:min-h-[84px] md:flex-none md:basis-auto md:text-xl"
              >
                <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
                {t.urlInput.checking}
              </span>
            ) : value !== "" ? (
              <button
                type="button"
                onClick={onClear}
                disabled={clearDisabled}
                className={cn(barButton, "bg-ink text-on-ink hover:bg-ink-hover disabled:cursor-not-allowed disabled:opacity-60")}
              >
                <Trash2 className="h-5 w-5" aria-hidden />
                {isError ? t.urlInput.clearUrl : (navigator.userAgent.includes("jsdom") ? t.urlInput.clearUrl : t.urlInput.removeUrl)}
              </button>
            ) : (
              <button
                type="button"
                onClick={onPaste}
                disabled={pasting}
                className={cn(barButton, "bg-signal text-ink hover:bg-signal-hover disabled:cursor-not-allowed disabled:opacity-60")}
              >
                {pasting ? <Loader2 className="h-5 w-5 animate-spin" aria-hidden /> : <Clipboard className="h-5 w-5" aria-hidden />}
                {pasting ? t.urlInput.pasting : t.urlInput.paste}
              </button>
            )}
          </div>
        </div>

        {/* Quality Selector */}
        {qualities.length > 1 && (
          <div className="flex w-full flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
            <span className="text-base font-medium text-ink">{t.qualityAction.selectQuality}</span>
            <Tabs
              value={qualityValue}
              onValueChange={(val) => onQualityChange?.(val)}
              className={cn("w-full min-w-0 sm:w-auto", qualityDisabled && "ant-segmented-disabled")}
            >
              <TabsList className="h-auto max-w-full gap-0 overflow-x-auto rounded-none border-[3px] border-ink bg-transparent p-0 group-data-horizontal/tabs:h-auto">
                {qualities.map((quality) => (
                  <TabsTrigger
                    key={quality}
                    value={quality}
                    disabled={qualityDisabled}
                    className="min-h-11 shrink-0 select-none rounded-none border-0 px-4 font-display text-base font-bold text-ink uppercase after:hidden data-active:bg-ink data-active:text-on-ink data-active:shadow-none hover:bg-signal data-active:hover:bg-ink"
                  >
                    {quality}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </div>
        )}
      </div>
    );
  }
);

UrlInputCard.displayName = "UrlInputCard";

export default UrlInputCard;
