import { CheckCircle2, Download, RefreshCw, FolderOpen, XCircle, AlertCircle } from "lucide-react";
import PlatformTag from "./PlatformTag";
import SectionCard from "./SectionCard";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useLanguage } from "../i18n/LanguageContext";
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
}: VideoInfoCardProps) => {
  const { t } = useLanguage();

  return (
    <SectionCard className="p-4 bg-white/90 border border-neutral-200 shadow-sm rounded-xl select-none">
      {/* Information Row */}
      <div className="flex flex-col sm:flex-row gap-4 items-start w-full">
        {info.thumbnail && (
          <img
            className="w-full sm:w-[120px] aspect-video sm:aspect-square rounded-lg object-cover bg-neutral-100 shrink-0 border border-neutral-200/50"
            src={info.thumbnail}
            referrerPolicy="no-referrer"
            alt={info.title}
          />
        )}
        <div className="flex flex-col gap-2 min-w-0 items-start flex-1">
          <PlatformTag platform={info.platform} />
          <h3 className="text-sm font-semibold text-slate-900 leading-snug break-words">
            {info.title}
          </h3>
          {info.uploader && (
            <p className="text-xs text-slate-500 truncate w-full">
              {info.uploader}
            </p>
          )}
          {info.duration && (
            <p className="text-xs text-slate-400 font-normal">
              {info.duration}
            </p>
          )}
        </div>
      </div>

      {/* Action States inside the card */}
      <div className="w-full border-t border-neutral-100 pt-4 flex flex-col gap-3">
        {actionState === "idle" && (
          <Button
            onClick={onDownload}
            className="w-full bg-[#0d9585] text-white hover:bg-[#0d9585]/90 gap-1.5 shadow-sm rounded-lg py-2"
          >
            <Download className="h-4 w-4" />
            {t.qualityAction.startDownload}
          </Button>
        )}

        {actionState === "downloading" && (
          <div className="flex flex-col gap-3 w-full">
            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-semibold text-[#0d9585] leading-none">
                {percent}% {t.qualityAction.downloading}…
              </span>
              <Progress value={percent} className="h-1.5 w-full bg-neutral-100 [&>[data-slot=progress-indicator]]:bg-[#0d9585]" />
            </div>
            <Button
              onClick={onCancel}
              variant="destructive"
              className="w-full bg-red-50 text-red-600 hover:bg-red-100 hover:text-red-700 border-none shadow-none gap-1.5 rounded-lg"
            >
              <XCircle className="h-4 w-4" />
              {t.downloadProgress.cancelDownload}
            </Button>
          </div>
        )}

        {actionState === "done" && (
          <div className="flex flex-col gap-3 w-full">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-[#0d9585]">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span className="truncate max-w-full">
                {t.downloadSuccess.saved} {filename || info.title}
              </span>
            </div>

            <div className="flex flex-col sm:flex-row gap-2 w-full">
              <Button
                variant="outline"
                onClick={onDownload}
                className="flex-1 border-[#0d9585] text-[#0d9585] hover:bg-[#0d9585]/5 gap-1.5 shadow-none rounded-lg font-semibold py-2"
              >
                <RefreshCw className="h-4 w-4" />
                {t.qualityAction.downloadAgain}
              </Button>

              {onOpenFolder && (
                <Button
                  onClick={onOpenFolder}
                  className="flex-1 bg-[#0d9585] text-white hover:bg-[#0d9585]/90 gap-1.5 shadow-sm rounded-lg py-2"
                >
                  <FolderOpen className="h-4 w-4" />
                  {t.downloadSuccess.openFolder}
                </Button>
              )}

              {downloadUrl && (
                <a href={downloadUrl} className="flex-1">
                  <Button
                    className="w-full bg-[#0d9585] text-white hover:bg-[#0d9585]/90 gap-1.5 shadow-sm rounded-lg py-2"
                  >
                    <Download className="h-4 w-4" />
                    {t.downloadSuccess.download}
                  </Button>
                </a>
              )}
            </div>
          </div>
        )}

        {actionState === "fail" && (
          <div className="flex flex-col gap-3 w-full">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-red-500">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{t.playlist.failed}</span>
            </div>
            <Button
              onClick={onDownload}
              variant="destructive"
              className="w-full bg-red-50 text-red-600 hover:bg-red-100 hover:text-red-700 border-none shadow-none gap-1.5 rounded-lg py-2"
            >
              <RefreshCw className="h-4 w-4" />
              {t.playlist.retry}
            </Button>
          </div>
        )}
      </div>
    </SectionCard>
  );
};

export default VideoInfoCard;
