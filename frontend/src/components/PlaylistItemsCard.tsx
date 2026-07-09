import { useMemo, useState } from "react";
import { Download, FolderOpen, XCircle, FolderCheck, FolderX, RefreshCw } from "lucide-react";
import SectionCard from "./SectionCard";
import PlatformTag from "./PlatformTag";
import File from "./File";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import { useLanguage } from "../i18n/LanguageContext";
import type { Platform, PlaylistItem, RowProgress, RowDownloadStatus } from "../types";

export interface BatchSummary {
  done: number;
  total: number;
  percent: number;
}

interface PlaylistItemsCardProps {
  title: string;
  platform: Platform;
  items: PlaylistItem[];
  truncated?: boolean;
  busy: boolean;
  rowStatus: Record<number, RowProgress>;
  batchSummary: BatchSummary | null;
  quality: string;
  onDownloadItems: (rowIndices: number[], quality: string) => void;
  onCancel?: () => void;
  onOpenFolder?: () => void;
}

const isAvailable = (item: PlaylistItem) => item.is_available !== false;
const statusOf = (rowStatus: Record<number, RowProgress>, i: number): RowDownloadStatus =>
  rowStatus[i]?.status ?? "idle";

const PlaylistItemsCard = ({
  title,
  platform,
  items = [],
  truncated,
  busy,
  rowStatus = {},
  batchSummary,
  quality,
  onDownloadItems,
  onCancel,
  onOpenFolder,
}: PlaylistItemsCardProps) => {
  const { t } = useLanguage();

  const [selected, setSelected] = useState<Set<number>>(() => new Set());
  const [showUnavailable, setShowUnavailable] = useState(false);

  const selectableIndices = useMemo(
    () =>
      (items || [])
        .map((_, i) => i)
        .filter((i) => items[i] && isAvailable(items[i]) && statusOf(rowStatus, i) !== "done"),
    [items, rowStatus]
  );

  const hasUnavailable = (items || []).some((it) => it && !isAvailable(it));

  const effectiveSelected = useMemo(
    () => selectableIndices.filter((i) => selected.has(i)),
    [selectableIndices, selected]
  );

  const doneCount = Object.values(rowStatus || {}).filter((r) => r && r.status === "done").length;
  const failedIndices = useMemo(
    () =>
      (items || [])
        .map((_, i) => i)
        .filter((i) => statusOf(rowStatus, i) === "error"),
    [items, rowStatus]
  );
  const failedCount = failedIndices.length;
  const anyDone = doneCount > 0;
  const numWidth = Math.max(2, String(items.length).length);

  const allSelected = selectableIndices.length > 0 && effectiveSelected.length === selectableIndices.length;

  const handleSelectAllChange = () => {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(selectableIndices));
    }
  };

  const toggleItem = (index: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const downloadRows = (rowIndices: number[]) => {
    if (rowIndices.length) onDownloadItems(rowIndices, quality);
  };

  if (items.length === 0) {
    return (
      <SectionCard>
        <p className="text-lg font-semibold text-slate-900 m-0">{title}</p>
        <p className="text-sm text-slate-500 m-0">{t.playlist.empty}</p>
      </SectionCard>
    );
  }

  return (
    <>
      <SectionCard>
        {/* Header Tag */}
        <PlatformTag platform={platform} />

        {/* Playlist Title */}
        <p className="text-lg font-semibold text-slate-900 m-0 select-none">{title}</p>

        {/* Total Items & Download All button */}
        <div className="flex justify-between items-center gap-3 flex-wrap select-none">
          <span className="text-sm text-slate-600">
            {t.playlist.totalItems} <strong className="text-slate-900 font-semibold">{items.length}</strong>
          </span>
          <Button
            onClick={() => downloadRows(selectableIndices)}
            disabled={busy || selectableIndices.length === 0}
            className="bg-[#0d9585] text-white hover:bg-[#0d9585]/90 gap-1.5 shadow-sm rounded-lg"
          >
            <Download className="h-4 w-4" />
            {t.playlist.downloadAll}
          </Button>
        </div>

        {/* Select section */}
        <div className="flex justify-between items-center gap-2 flex-wrap border-t border-neutral-100 pt-3 select-none">
          <span className="text-xs text-slate-400 font-medium">{t.playlist.orSelect}</span>
          {hasUnavailable && (
            <div className="inline-flex items-center gap-2 text-xs text-slate-600 font-medium">
              <span>{t.playlist.showUnavailable}</span>
              <Switch checked={showUnavailable} onCheckedChange={setShowUnavailable} disabled={busy} />
            </div>
          )}
        </div>

        {/* Select All */}
        <div className="flex items-center gap-2 p-1 select-none">
          <Checkbox
            checked={allSelected}
            disabled={busy || selectableIndices.length === 0}
            onCheckedChange={handleSelectAllChange}
            id="select-all-checkbox"
          />
          <label 
            htmlFor="select-all-checkbox" 
            className="text-xs font-semibold text-slate-700 cursor-pointer disabled:opacity-50"
          >
            {t.playlist.selectAll}
          </label>
        </div>

        {/* Truncated notice */}
        {truncated && (
          <p className="text-xs text-amber-600 font-medium m-0">
            {t.playlist.truncated.replace("{n}", String(items.length))}
          </p>
        )}

        {/* Item Rows */}
        <div className="flex flex-col gap-1 w-full border-t border-neutral-100/50 pt-2">
          {items.map((item, index) => {
            const available = isAvailable(item);
            if (!available && !showUnavailable) return null;
            const status = statusOf(rowStatus, index);
            const isDone = status === "done";
            
            // Map row status string to FileState variant
            let fileState: "Default" | "Downloading" | "Completed" | "Fail" = "Default";
            if (status === "downloading" || status === "pending") {
              fileState = "Downloading";
            } else if (status === "done") {
              fileState = "Completed";
            } else if (status === "error") {
              fileState = "Fail";
            }

            return (
              <File
                key={item.id ?? index}
                title={item.title}
                uploader={item.uploader ?? undefined}
                thumbnail={item.thumbnail ?? undefined}
                duration={item.duration ?? undefined}
                kind={item.kind}
                position={item.position ?? index + 1}
                numWidth={numWidth}
                state={fileState}
                percent={rowStatus[index]?.percent ?? 0}
                checked={selected.has(index) && !isDone}
                onToggle={() => toggleItem(index)}
                onAction={() => downloadRows([index])}
                busy={busy}
                available={available}
              />
            );
          })}
        </div>

        {/* Selected download bulk button */}
        {!busy && effectiveSelected.length > 0 && (
          <Button 
            onClick={() => downloadRows(effectiveSelected)} 
            className="w-full bg-white hover:bg-neutral-50 text-[#0d9585] border border-[#0d9585] gap-1.5 shadow-none rounded-lg font-semibold py-2 mt-2"
          >
            <Download className="h-4 w-4" />
            {t.playlist.downloadItemsSelected}
          </Button>
        )}
        {/* Status and Action Buttons (Retry / Open Folder) */}
        {!busy && anyDone && (
          <div className="flex flex-col gap-3 w-full border-t border-neutral-100/50 pt-3 mt-2 select-none">
            {/* Status Row */}
            <div className="flex justify-between items-center w-full">
              {/* Failed Count */}
              <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${failedCount > 0 ? "text-red-500" : "text-slate-400"}`}>
                <FolderX className="h-4 w-4 shrink-0" />
                {t.playlist.failedItems.replace("{n}", String(failedCount))}
              </span>
              
              {/* Saved Count */}
              <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#0d9585]">
                <FolderCheck className="h-4 w-4 shrink-0" />
                {t.playlist.savedItems.replace("{n}", String(doneCount))}
              </span>
            </div>

            {/* Action Buttons */}
            <div className={`w-full ${failedCount > 0 && onOpenFolder ? "grid grid-cols-2 gap-3" : "flex"}`}>
              {failedCount > 0 && (
                <Button
                  onClick={() => downloadRows(failedIndices)}
                  className="w-full bg-red-50 hover:bg-red-100 text-red-600 border-none shadow-none gap-1.5 rounded-lg font-semibold py-2"
                >
                  <RefreshCw className="h-4 w-4" />
                  {t.playlist.retry}
                </Button>
              )}
              {onOpenFolder && (
                <Button
                  onClick={onOpenFolder}
                  className="w-full bg-[#0d9585] text-white hover:bg-[#0d9585]/90 gap-1.5 shadow-sm rounded-lg font-semibold py-2"
                >
                  <FolderOpen className="h-4 w-4" />
                  {t.downloadSuccess.openFolder}
                </Button>
              )}
            </div>
          </div>
        )}

        {/* Global running batch progress + Cancel */}
        {busy && batchSummary && (
          <div className="flex flex-col gap-3 w-full border-t border-neutral-100/50 pt-3 mt-2 select-none">
            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-semibold text-slate-800">
                {t.playlist.downloadedProgress
                  .replace("{done}", String(batchSummary.done))
                  .replace("{total}", String(batchSummary.total))}
              </span>
              <Progress value={batchSummary.percent} className="h-1.5 w-full bg-neutral-100 [&>[data-slot=progress-indicator]]:bg-[#0d9585]" />
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
      </SectionCard>
    </>
  );
};

export default PlaylistItemsCard;
