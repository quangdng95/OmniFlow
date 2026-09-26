import { useCallback, useMemo, useState } from "react";
import { Download, FolderOpen, Loader2, XCircle, FolderCheck, FolderX, RefreshCw } from "lucide-react";
import SectionCard from "./SectionCard";
import PlatformTag from "./PlatformTag";
import File from "./File";
import ThumbnailPreviewDialog, { type PreviewEntry } from "./ThumbnailPreviewDialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import { useLanguage } from "../i18n/LanguageContext";
import { prepareZipFiles } from "../lib/saveFile";
import { usePreparedSave } from "../hooks/usePreparedSave";
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
  downloadUrl?: string;
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
  downloadUrl,
}: PlaylistItemsCardProps) => {
  const { t } = useLanguage();

  const [selected, setSelected] = useState<Set<number>>(() => new Set());
  const [showUnavailable, setShowUnavailable] = useState(false);
  // Row index (into `items`) of the thumbnail currently enlarged, or null.
  const [previewRow, setPreviewRow] = useState<number | null>(null);

  const prepareBatchZip = useCallback(
    (url: string) => prepareZipFiles(url, `${title || "OmniFlow"}.zip`),
    [title]
  );
  const { saving: savingZip, save: handleSaveZip } = usePreparedSave(downloadUrl, prepareBatchZip);

  // Every available row stays selectable - including already-downloaded ones,
  // so a user can tick several finished rows and grab them again in one go
  // instead of tapping "Download again" row by row.
  const selectableIndices = useMemo(
    () => (items || []).map((_, i) => i).filter((i) => items[i] && isAvailable(items[i])),
    [items]
  );
  // "Download All" grabs what's still missing; once everything is saved it
  // re-downloads the whole list rather than going dead.
  const downloadAllIndices = useMemo(() => {
    const notDone = selectableIndices.filter((i) => statusOf(rowStatus, i) !== "done");
    return notDone.length > 0 ? notDone : selectableIndices;
  }, [selectableIndices, rowStatus]);

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

  // Rows the preview can step through: the ones on screen that have a thumbnail,
  // in list order.
  const previewRows = useMemo(
    () =>
      (items || [])
        .map((_, i) => i)
        .filter((i) => items[i]?.thumbnail && (isAvailable(items[i]) || showUnavailable)),
    [items, showUnavailable]
  );
  const previewEntries: PreviewEntry[] = previewRows.map((i) => ({
    thumbnail: items[i].thumbnail as string,
    title: items[i].title,
    label: String(items[i].position ?? i + 1).padStart(numWidth, "0"),
  }));
  const previewIndex = previewRow === null ? null : previewRows.indexOf(previewRow);

  const handlePreviewIndexChange = (index: number) => setPreviewRow(previewRows[index] ?? null);
  const handlePreviewClose = () => setPreviewRow(null);

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
    if (!rowIndices.length) return;
    setSelected(new Set());
    onDownloadItems(rowIndices, quality);
  };

  const handleDownloadAll = () => downloadRows(downloadAllIndices);

  // Shown both next to "Download All" and in the footer, so after tapping the
  // top button the user can save without scrolling to the end of a long list.
  const canSave = !busy && anyDone && (Boolean(downloadUrl) || Boolean(onOpenFolder));
  const renderSaveButton = (className: string) =>
    downloadUrl ? (
      <Button
        onClick={handleSaveZip}
        disabled={savingZip}
        className={cn("bg-[#0d9585] text-white hover:bg-[#0d9585]/90 gap-1.5 shadow-sm rounded-lg font-semibold", className)}
      >
        {savingZip ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
        {t.downloadSuccess.download}
      </Button>
    ) : onOpenFolder ? (
      <Button
        onClick={onOpenFolder}
        className={cn("bg-[#0d9585] text-white hover:bg-[#0d9585]/90 gap-1.5 shadow-sm rounded-lg font-semibold", className)}
      >
        <FolderOpen className="h-4 w-4" />
        {t.downloadSuccess.openFolder}
      </Button>
    ) : null;

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
          <div className="flex items-center gap-2 flex-wrap justify-end">
            {canSave && renderSaveButton("")}
            <Button
              onClick={handleDownloadAll}
              disabled={busy || downloadAllIndices.length === 0}
              className={cn(
                "gap-1.5 rounded-lg",
                canSave
                  ? "bg-white hover:bg-neutral-50 text-[#0d9585] border border-[#0d9585] shadow-none"
                  : "bg-[#0d9585] text-white hover:bg-[#0d9585]/90 shadow-sm"
              )}
            >
              <Download className="h-4 w-4" />
              {t.playlist.downloadAll}
            </Button>
          </div>
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
                checked={selected.has(index)}
                onToggle={() => toggleItem(index)}
                onAction={() => downloadRows([index])}
                onPreview={() => setPreviewRow(index)}
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
            <div
              className={
                downloadUrl
                  ? "flex flex-col sm:flex-row gap-3 w-full"
                  : `w-full ${failedCount > 0 && onOpenFolder ? "grid grid-cols-2 gap-3" : "flex"}`
              }
            >
              {failedCount > 0 && (
                <Button
                  onClick={() => downloadRows(failedIndices)}
                  className="flex-1 w-full bg-red-50 hover:bg-red-100 text-red-600 border-none shadow-none gap-1.5 rounded-lg font-semibold py-2"
                >
                  <RefreshCw className="h-4 w-4" />
                  {t.playlist.retry}
                </Button>
              )}
              {renderSaveButton("flex-1 w-full py-2")}
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
      <ThumbnailPreviewDialog
        entries={previewEntries}
        index={previewIndex === -1 ? null : previewIndex}
        onIndexChange={handlePreviewIndexChange}
        onClose={handlePreviewClose}
      />
    </>
  );
};

export default PlaylistItemsCard;
