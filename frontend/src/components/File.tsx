import { Download, RefreshCw, FolderCheck, FolderX } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useLanguage } from "../i18n/LanguageContext";

export type FileState = "Default" | "Downloading" | "Completed" | "Fail";

interface FileProps {
  title: string;
  uploader?: string;
  thumbnail?: string;
  duration?: string;
  kind?: string;
  position: number;
  numWidth: number;
  state?: FileState;
  percent?: number;
  checked: boolean;
  onToggle: () => void;
  onAction: () => void;
  busy: boolean;
  available: boolean;
}

export default function File({
  title,
  uploader,
  thumbnail,
  duration,
  kind,
  position,
  numWidth,
  state = "Default",
  percent = 0,
  checked,
  onToggle,
  onAction,
  busy,
  available,
}: FileProps) {
  const { t } = useLanguage();

  const handleActionClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onAction();
  };

  const formattedNum = String(position).padStart(numWidth, "0");

  return (
    <div
      onClick={() => !busy && available && state !== "Completed" && onToggle()}
      className={`flex items-center gap-4 px-3 rounded-lg border border-transparent transition-colors w-full select-none h-[60px] ${
        !available 
          ? "opacity-45 cursor-default bg-neutral-50/50" 
          : busy 
          ? "cursor-default" 
          : "cursor-pointer hover:bg-neutral-50"
      }`}
    >
      {/* Checkbox */}
      <Checkbox
        checked={checked && available && state !== "Completed"}
        disabled={busy || !available || state === "Completed"}
        onClick={(e) => e.stopPropagation()}
        onCheckedChange={() => onToggle()}
        className="shrink-0 w-4 h-4"
      />

      {/* Index Number */}
      <span className="text-xs font-semibold text-slate-400 w-8 text-right shrink-0">
        {formattedNum}.
      </span>

      {/* Thumbnail or Fallback Placeholder */}
      <div className="h-11 w-11 rounded-lg bg-neutral-100 shrink-0 border border-neutral-200/50 overflow-hidden flex items-center justify-center">
        {thumbnail ? (
          <img
            src={thumbnail}
            referrerPolicy="no-referrer"
            alt={title}
            className="h-full w-full object-cover"
          />
        ) : (
          <span className="text-[14px]">
            {kind === "image" ? "📷" : "🎥"}
          </span>
        )}
      </div>

      {/* Info Description */}
      <div className="flex-1 min-w-0 flex flex-col gap-0.5">
        <h4 className="text-xs font-medium text-slate-900 truncate leading-snug">
          {title}
        </h4>
        {uploader && (
          <p className="text-[11px] text-slate-500 truncate leading-none">
            {uploader}
          </p>
        )}
        <div className="flex items-center gap-2 mt-0.5">
          {kind && (
            <span 
              className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                kind === "image" 
                  ? "bg-blue-50 text-blue-600" 
                  : "bg-green-50 text-green-600"
              }`}
            >
              {kind === "image" ? t.playlist.photo : t.playlist.video}
            </span>
          )}
          {!available && (
            <span className="text-[10px] font-semibold bg-neutral-100 text-neutral-500 px-1.5 py-0.5 rounded">
              {t.playlist.unavailable}
            </span>
          )}
          {duration && (
            <span className="text-[11px] text-slate-400 font-normal">
              {duration}
            </span>
          )}
        </div>
      </div>

      {/* Right Content Area */}
      {available && (
        <div className="flex flex-col items-end gap-1 w-[146px] shrink-0 text-right">
          {state === "Downloading" && (
            <div className="w-full flex flex-col gap-1">
              <span className="text-[11px] font-semibold text-[#0d9585] leading-none">
                {t.playlist.percentDownloading.replace("{p}", String(Math.round(percent)))}
              </span>
              <Progress value={percent} className="h-1 w-full bg-neutral-100 [&>[data-slot=progress-indicator]]:bg-[#0d9585]" />
            </div>
          )}

          {state === "Completed" && (
            <div className="flex flex-col items-end gap-1 shrink-0">
              <span className="flex items-center gap-1 text-[11px] font-semibold text-[#0d9585] leading-none">
                <FolderCheck className="h-3.5 w-3.5" />
                {t.playlist.downloaded}
              </span>
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs border-neutral-200 text-slate-700 hover:bg-neutral-100 hover:text-slate-900 gap-1 rounded-md px-2 py-1 shadow-none"
                onClick={handleActionClick}
                disabled={busy}
              >
                <RefreshCw className="h-3 w-3" />
                {t.playlist.downloadAgain}
              </Button>
            </div>
          )}

          {state === "Fail" && (
            <div className="flex flex-col items-end gap-1 shrink-0">
              <span className="flex items-center gap-1 text-[11px] font-semibold text-red-500 leading-none">
                <FolderX className="h-3.5 w-3.5" />
                {t.playlist.failed}
              </span>
              <Button
                variant="destructive"
                size="sm"
                className="h-7 text-xs bg-red-50 text-red-600 hover:bg-red-100 hover:text-red-700 gap-1 rounded-md px-2 py-1 shadow-none border-none"
                onClick={handleActionClick}
                disabled={busy}
              >
                <RefreshCw className="h-3 w-3" />
                {t.playlist.retry}
              </Button>
            </div>
          )}

          {state === "Default" && (
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-xs border-[#0d9585] text-[#0d9585] hover:bg-[#0d9585]/5 gap-1 rounded-md px-2.5 py-1 shadow-none"
              onClick={handleActionClick}
              disabled={busy}
              aria-label="download-item"
            >
              <Download className="h-3.5 w-3.5" />
              {t.playlist.download}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
