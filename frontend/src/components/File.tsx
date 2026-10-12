import { Download, RefreshCw, Check, AlertCircle, Image as ImageIcon, Film } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import { blockCheckbox, progressSlab, rowButton } from "../lib/blockStyles";
import { cn } from "@/lib/utils";
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
  hideRedownload?: boolean;
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
  hideRedownload = false,
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
    <li
      onClick={() => !busy && available && onToggle()}
      className={cn(
        "flex min-h-[76px] list-none flex-wrap items-center gap-x-3 gap-y-2 border-t-[3px] border-current py-3 select-none last:border-b-[3px] sm:flex-nowrap sm:gap-4",
        !available ? "cursor-default opacity-60" : busy ? "cursor-default" : "cursor-pointer"
      )}
    >
      {/* Base UI renders a hidden <input> beside the checkbox; a click on the
          box makes that input fire its own click, which bubbles to the row and
          would toggle a second time (net: nothing changes). The wrapper
          swallows both, so the checkbox toggles itself exactly once while a
          click anywhere else on the row still toggles via the row handler. */}
      <span className="flex shrink-0 items-center" onClick={(e) => e.stopPropagation()}>
        <Checkbox
          checked={checked && available}
          disabled={busy || !available}
          onCheckedChange={() => onToggle()}
          className={blockCheckbox}
        />
      </span>

      <span className="w-9 shrink-0 text-right font-display text-[1.375rem] font-bold tabular-nums">{formattedNum}.</span>

      {thumbnail && onPreview ? (
        <button
          type="button"
          onClick={handlePreviewClick}
          aria-label={t.playlist.previewItem.replace("{title}", title)}
          className="flex h-12 w-16 shrink-0 cursor-zoom-in items-center justify-center overflow-hidden border-2 border-current bg-black"
        >
          <img src={thumbnail} referrerPolicy="no-referrer" alt="" className="h-full w-full object-cover" />
        </button>
      ) : (
        <div className="flex h-12 w-16 shrink-0 items-center justify-center overflow-hidden border-2 border-current bg-black/30">
          {thumbnail ? (
            <img src={thumbnail} referrerPolicy="no-referrer" alt={title} className="h-full w-full object-cover" />
          ) : kind === "image" ? (
            <ImageIcon className="h-5 w-5" aria-hidden />
          ) : (
            <Film className="h-5 w-5" aria-hidden />
          )}
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <h4 className="m-0 line-clamp-2 font-display text-[clamp(1.125rem,3.2vw,1.625rem)] leading-[1.15] font-bold tracking-[-0.02em]">
          {title}
        </h4>
        <p className="m-0 flex flex-wrap items-center gap-x-3 text-base">
          {uploader && <span className="truncate">{uploader}</span>}
          {kind && <span className="font-bold uppercase">{kind === "image" ? t.playlist.photo : t.playlist.video}</span>}
          {!available && <span className="font-bold uppercase">{t.playlist.unavailable}</span>}
          {duration && <span className="tabular-nums">{duration}</span>}
        </p>
      </div>

      {/* Status + action: on phones they drop onto their own line under the
          row; from sm up they sit in a fixed column at the right. */}
      {available && (
        <div className="flex w-full shrink-0 flex-row items-center justify-between gap-2 sm:w-[11.5rem] sm:flex-col sm:items-end sm:justify-center">
          {state === "Downloading" && (
            <div role="status" className="flex w-full flex-col gap-1.5">
              <span className="font-display text-base font-bold">
                {t.playlist.percentDownloading.replace("{p}", String(Math.round(percent)))}
              </span>
              <Progress
                value={percent}
                aria-label={t.playlist.downloading}
                className={cn(progressSlab, "[&_[data-slot=progress-track]]:h-3.5")}
              />
            </div>
          )}

          {state === "Completed" && (
            <div className="flex w-full flex-row items-center justify-between gap-2 sm:w-auto sm:flex-col sm:items-end">
              <span className="inline-flex items-center gap-1.5 font-display text-base font-bold uppercase">
                <Check className="h-5 w-5" strokeWidth={3} aria-hidden />
                {t.playlist.downloaded}
              </span>
              {!hideRedownload && (
                <button type="button" className={rowButton} onClick={handleActionClick} disabled={busy}>
                  <RefreshCw className="h-5 w-5" aria-hidden />
                  {t.playlist.downloadAgain}
                </button>
              )}
            </div>
          )}

          {state === "Fail" && (
            <div className="flex w-full flex-row items-center justify-between gap-2 sm:w-auto sm:flex-col sm:items-end">
              <span className="inline-flex items-center gap-1.5 font-display text-base font-bold uppercase">
                <AlertCircle className="h-5 w-5" aria-hidden />
                {t.playlist.failed}
              </span>
              <button type="button" className={rowButton} onClick={handleActionClick} disabled={busy}>
                <RefreshCw className="h-5 w-5" aria-hidden />
                {t.playlist.retry}
              </button>
            </div>
          )}

          {state === "Default" && (
            <button
              type="button"
              className={cn(rowButton, "ml-auto sm:ml-0")}
              onClick={handleActionClick}
              disabled={busy}
              aria-label="download-item"
            >
              <Download className="h-5 w-5" aria-hidden />
              {t.playlist.download}
            </button>
          )}
        </div>
      )}
    </li>
  );
}
