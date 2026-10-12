import { useCallback } from "react";
import { Download, Save, Loader2, RefreshCw, FolderOpen, XCircle, AlertCircle, Check } from "lucide-react";
import PlatformTag from "./PlatformTag";
import PlatformBlock from "./PlatformBlock";
import { Progress } from "@/components/ui/progress";
import { bigStatus, ctaGhost, ctaLight, ctaSignal, progressSlab } from "../lib/blockStyles";
import { useLanguage } from "../i18n/LanguageContext";
import { preparePlainFile } from "../lib/saveFile";
import { usePreparedSave } from "../hooks/usePreparedSave";
import type { VideoInfo } from "../types";

export type DownloadActionState = "idle" | "downloading" | "done" | "fail";

interface VideoInfoCardProps {
  info: VideoInfo;
  actionState: DownloadActionState;
  percent: number;
  filename: string | null;
  onDownload: () => void;
  onCancel: () => void;
  onOpenFolder?: () => void;
  downloadUrl?: string;
  // Phone/remote: HomePage starts the download itself, so the card only shows
  // progress and then a single "Save to device" button.
  autoSave?: boolean;
}

const VideoInfoCard = ({
  info,
  actionState,
  percent,
  filename,
  onDownload,
  onCancel,
  onOpenFolder,
  downloadUrl,
  autoSave = false,
}: VideoInfoCardProps) => {
  const { t } = useLanguage();
  const prepareSingleFile = useCallback(
    (url: string) => preparePlainFile(url, filename || info.title),
    [filename, info.title]
  );
  // downloadUrl exists from the moment the job starts - only prefetch once
  // the file is actually finished on the server.
  const { saving, failed: saveFailed, save: handleSave } = usePreparedSave(
    actionState === "done" ? downloadUrl : undefined,
    prepareSingleFile
  );

  const isDownloading = actionState === "downloading" || (autoSave && actionState === "idle");
  // The block changes colour with the state: platform colour while choosing and
  // downloading, lime once saved, ink when it failed.
  const tone = actionState === "done" ? "done" : actionState === "fail" ? "ink" : info.platform;
  const saveLabel = saveFailed ? t.downloadSuccess.tryAgain : t.downloadSuccess.save;
  const saveIcon = saving ? <Loader2 className="h-6 w-6 animate-spin" aria-hidden /> : <Save className="h-6 w-6" aria-hidden />;

  return (
    <PlatformBlock tone={tone}>
      <div className={`grid items-start gap-6 md:gap-12 ${info.thumbnail ? "md:grid-cols-[5fr_7fr]" : ""}`}>
        {info.thumbnail && (
          <div className="flex flex-col gap-4">
            <PlatformTag platform={info.platform} />
            <img
              className="aspect-video w-full border-[3px] border-current bg-black object-cover"
              src={info.thumbnail}
              referrerPolicy="no-referrer"
              alt={info.title}
            />
          </div>
        )}

        <div className="flex min-w-0 flex-col gap-5">
          {!info.thumbnail && <PlatformTag platform={info.platform} />}
          <div className="flex flex-col gap-1.5">
            <h3 className="m-0 font-display text-[clamp(1.75rem,5vw,3.25rem)] leading-[1.05] font-bold tracking-[-0.04em] break-words [:lang(vi)_&]:leading-[1.15]">
              {info.title}
            </h3>
            {(info.uploader || info.duration) && (
              <p className="m-0 text-lg">
                {[info.uploader, info.duration].filter(Boolean).join(" · ")}
              </p>
            )}
          </div>

          {actionState === "idle" && !autoSave && (
            <button type="button" onClick={onDownload} className={ctaLight}>
              <Download className="h-6 w-6" aria-hidden />
              {t.qualityAction.startDownload}
            </button>
          )}

          {isDownloading && (
            <div role="status" className="flex flex-col gap-4">
              <p
                aria-hidden
                className="m-0 font-display text-[clamp(5rem,22vw,11rem)] leading-[0.85] font-bold tracking-[-0.07em] tabular-nums"
              >
                {Math.min(100, Math.round(percent))}%
              </p>
              <Progress value={percent} aria-label={t.qualityAction.downloading} className={progressSlab} />
              <p className="m-0 font-display text-xl font-bold">
                {percent >= 100 ? t.qualityAction.finalizing : `${percent}% ${t.qualityAction.downloading}…`}
              </p>
              <div>
                <button type="button" onClick={onCancel} className={ctaGhost}>
                  <XCircle className="h-5 w-5" aria-hidden />
                  {t.downloadProgress.cancelDownload}
                </button>
              </div>
            </div>
          )}

          {actionState === "done" && autoSave && downloadUrl && (
            <div>
              <button type="button" onClick={handleSave} disabled={saving} className={ctaLight}>
                {saveIcon}
                {saveLabel}
              </button>
            </div>
          )}

          {actionState === "done" && !autoSave && (
            <div role="status" className="flex flex-col gap-5">
              <p className={`${bigStatus} text-[clamp(2rem,8vw,4.5rem)]`}>
                <Check className="mr-2 inline h-[0.8em] w-[0.8em] align-baseline" strokeWidth={3} aria-hidden />
                {t.downloadSuccess.saved}
              </p>
              <p className="m-0 text-lg font-medium break-all">{filename || info.title}</p>
              <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap">
                {onOpenFolder && (
                  <button type="button" onClick={onOpenFolder} className={ctaLight}>
                    <FolderOpen className="h-6 w-6" aria-hidden />
                    {t.downloadSuccess.openFolder}
                  </button>
                )}
                {downloadUrl && (
                  <button type="button" onClick={handleSave} disabled={saving} className={ctaLight}>
                    {saveIcon}
                    {saveLabel}
                  </button>
                )}
                <button type="button" onClick={onDownload} className={ctaGhost}>
                  <RefreshCw className="h-5 w-5" aria-hidden />
                  {t.qualityAction.downloadAgain}
                </button>
              </div>
            </div>
          )}

          {actionState === "fail" && (
            <div role="alert" className="flex flex-col gap-5">
              <p className={`${bigStatus} text-[clamp(2rem,8vw,4.5rem)] text-signal`}>
                <AlertCircle className="mr-2 inline h-[0.8em] w-[0.8em] align-baseline" strokeWidth={3} aria-hidden />
                {t.playlist.failed}
              </p>
              <div>
                <button type="button" onClick={onDownload} className={ctaSignal}>
                  <RefreshCw className="h-5 w-5" aria-hidden />
                  {t.playlist.retry}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </PlatformBlock>
  );
};

export default VideoInfoCard;
