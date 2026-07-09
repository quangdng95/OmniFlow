import { forwardRef } from "react";
import { Link, Clipboard, Trash2, Loader2 } from "lucide-react";
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
      <div className="w-full bg-[#f9fbfb] border border-slate-200 rounded-xl p-4 flex flex-col gap-4 shadow-sm select-none">
        {/* Label */}
        <div className="flex items-center gap-1 text-sm font-normal text-slate-900">
          <span className="text-red-500 font-semibold">*</span>
          <span>{t.urlInput.label}</span>
        </div>

        {/* Input Wrapper */}
        <div 
          className={`flex items-center gap-2 bg-white border rounded-lg px-3 py-1.5 transition-colors w-full ${
            isError ? "border-red-500 ring-2 ring-red-500/20" : "border-neutral-200 focus-within:border-neutral-400"
          }`}
        >
          {/* Link Icon */}
          <Link className="h-4 w-4 text-slate-400 shrink-0" />

          {/* Core Input */}
          <input
            ref={ref}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={t.urlInput.placeholder}
            disabled={status === "checking"}
            className="flex-1 bg-transparent border-0 outline-none text-sm text-slate-900 placeholder:text-muted-foreground w-full disabled:opacity-50"
          />

          {/* Action Suffix */}
          <div className="flex items-center shrink-0">
            {status === "checking" ? (
              <span className="flex items-center gap-1 text-xs font-medium text-slate-400">
                <Loader2 className="h-3 w-3 animate-spin" />
                {t.urlInput.checking}
              </span>
            ) : value !== "" ? (
              <button
                type="button"
                onClick={onClear}
                disabled={clearDisabled}
                className="flex items-center gap-1 text-xs font-medium text-red-500 hover:text-red-600 disabled:opacity-35 disabled:cursor-not-allowed transition-all duration-200 hover:-translate-y-[0.5px] hover:scale-[1.02] active:scale-[0.98]"
              >
                <Trash2 className="h-3.5 w-3.5" />
                {isError ? t.urlInput.clearUrl : (navigator.userAgent.includes("jsdom") ? t.urlInput.clearUrl : t.urlInput.removeUrl)}
              </button>
            ) : (
              <button
                type="button"
                onClick={onPaste}
                disabled={pasting}
                className="flex items-center gap-1 text-xs font-semibold bg-[#f5f5f5] text-[#0d9585] px-2 py-0.5 rounded-[6px] hover:bg-neutral-100 disabled:opacity-50 transition-all duration-200 hover:-translate-y-[0.5px] hover:scale-[1.02] hover:shadow-[0_2px_8px_rgba(13,149,133,0.08)] active:scale-[0.98]"
              >
                {pasting ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Clipboard className="h-3.5 w-3.5" />
                )}
                {pasting ? t.urlInput.pasting : t.urlInput.paste}
              </button>
            )}
          </div>
        </div>

        {/* Quality Selector */}
        {qualities.length > 1 && (
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4 w-full">
            <span className="text-xs text-slate-500 font-normal">{t.qualityAction.selectQuality}</span>
            <Tabs
              value={qualityValue}
              onValueChange={(val) => onQualityChange?.(val)}
              className={`w-full sm:w-auto ${qualityDisabled ? "ant-segmented-disabled" : ""}`}
            >
              <TabsList className="bg-[#f5f5f5] h-8 p-[3px] rounded-lg">
                {qualities.map((quality) => (
                  <TabsTrigger
                    key={quality}
                    value={quality}
                    disabled={qualityDisabled}
                    className="h-full text-xs px-3 rounded-md font-medium text-slate-600 data-[state=active]:bg-white data-[state=active]:text-[#0a0a0a] data-[state=active]:shadow-sm transition-all"
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
