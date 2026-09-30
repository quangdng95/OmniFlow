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
  onPreview?: () => void;
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
  onPreview,
  busy,
  available,
}: FileProps) {
  const { t } = useLanguage();

  const handleActionClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onAction();
  };

  const handlePreviewClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onPreview?.();
  };

  const formattedNum = String(position).padStart(numWidth, "0");

  return (
    <div
      onClick={() => !busy && available && onToggle()}
      className={`flex flex-wrap sm:flex-nowrap items-center gap-x-3 gap-y-2 sm:gap-4 px-3 py-2 sm:py-0 rounded-lg border border-transparent transition-colors w-full select-none sm:h-[60px] ${
        !available 
          ? "opacity-45 cursor-default bg-neutral-50/50" 
          : busy 
          ? "cursor-default" 
          : "cursor-pointer hover:bg-neutral-50"
      }`}
    >
      {/* Checkbox */}
      {/* Base UI renders a hidden <input> beside the checkbox; a click on the
          box makes that input fire its own click, which bubbles to the row and
          would toggle a second time (net: nothing changes). The wrapper
          swallows both, so the checkbox toggles itself exactly once while a
          click anywhere else on the row still toggles via the row handler. */}
      <span className="shrink-0 flex items-center" onClick={(e) => e.stopPropagation()}>
        <Checkbox
          checked={checked && available}
          disabled={busy || !available}
          onCheckedChange={() => onToggle()}
          className="shrink-0 w-4 h-4"
        />
      </span>

      {/* Index Number */}
      <span className="text-xs font-semibold text-slate-400 w-8 text-right shrink-0">
        {formattedNum}.
      </span>

      {/* Thumbnail (click to enlarge) or Fallback Placeholder */}
      {thumbnail && onPreview ? (
        <button
          type="button"
          onClick={handlePreviewClick}
          aria-label={t.playlist.previewItem.replace("{title}", title)}
          className="h-11 w-11 rounded-lg bg-neutral-100 shrink-0 border border-neutral-200/50 overflow-hidden flex items-center justify-center cursor-zoom-in focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0d9585]"
        >
          <img
            src={thumbnail}
            referrerPolicy="no-referrer"
            alt=""
            className="h-full w-full object-cover"
          />
        </button>
      ) : (
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
      )}

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

      {/* Right Content Area. Phones: the status + action drop onto their own line
          under the row (a 32px button beside the title left no room for it).
          sm and up: the original fixed 146px column at the right of the row. */}
      {available && (
        <div className="flex flex-row sm:flex-col items-center sm:items-end justify-between sm:justify-start gap-2 sm:gap-1 w-full sm:w-[146px] shrink-0 sm:text-right">
          {state === "Downloading" && (
            <div className="w-full flex flex-col gap-1">
              <span className="text-[11px] font-semibold text-[#0d9585] leading-none">
                {t.playlist.percentDownloading.replace("{p}", String(Math.round(percent)))}
              </span>
              <Progress value={percent} className="h-1 w-full bg-neutral-100 [&>[data-slot=progress-indicator]]:bg-[#0d9585]" />
            </div>
          )}

          {state === "Completed" && (
            <div className="flex flex-row sm:flex-col items-center sm:items-end justify-between sm:justify-start gap-2 sm:gap-1 w-full sm:w-auto shrink-0">
              <span className="flex items-center gap-1 text-[11px] font-semibold text-[#0d9585] leading-none">
                <FolderCheck className="h-3.5 w-3.5" />
                {t.playlist.downloaded}
              </span>
              <Button
                variant="outline"
                className="border-neutral-200 text-slate-700 hover:bg-neutral-100 hover:text-slate-900 rounded-lg shadow-none"
                onClick={handleActionClick}
                disabled={busy}
              >
                <RefreshCw className="h-4 w-4" />
                {t.playlist.downloadAgain}
              </Button>
            </div>
          )}

          {state === "Fail" && (
            <div className="flex flex-row sm:flex-col items-center sm:items-end justify-between sm:justify-start gap-2 sm:gap-1 w-full sm:w-auto shrink-0">
              <span className="flex items-center gap-1 text-[11px] font-semibold text-red-500 leading-none">
                <FolderX className="h-3.5 w-3.5" />
                {t.playlist.failed}
              </span>
              <Button
                variant="destructive"
                className="bg-red-50 text-red-600 hover:bg-red-100 hover:text-red-700 rounded-lg shadow-none border-none"
                onClick={handleActionClick}
                disabled={busy}
              >
                <RefreshCw className="h-4 w-4" />
                {t.playlist.retry}
              </Button>
            </div>
          )}

          {state === "Default" && (
            <Button
              variant="outline"
              className="ml-auto sm:ml-0 border-[#0d9585] text-[#0d9585] hover:bg-[#0d9585]/5 rounded-lg shadow-none"
              onClick={handleActionClick}
              disabled={busy}
              aria-label="download-item"
            >
              <Download className="h-4 w-4" />
              {t.playlist.download}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
