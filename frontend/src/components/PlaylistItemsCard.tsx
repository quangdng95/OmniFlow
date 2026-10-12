import { useCallback, useMemo, useState } from "react";
import { Download, Save, FolderOpen, Loader2, XCircle, FolderCheck, FolderX, RefreshCw } from "lucide-react";
import PlatformBlock from "./PlatformBlock";
import PlatformTag from "./PlatformTag";
import File from "./File";
import ThumbnailPreviewDialog, { type PreviewEntry } from "./ThumbnailPreviewDialog";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import { blockCheckbox, blockSwitch, bigStatus, ctaGhost, ctaLight, progressSlab } from "../lib/blockStyles";
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
    (url: string) => prepareZipFiles(url, `${title || "Vidrop"}.zip`),
    [title]
  );
  const { saving: savingZip, failed: zipFailed, save: handleSaveZip } = usePreparedSave(downloadUrl, prepareBatchZip);

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
  const renderSaveButton = () =>
    downloadUrl ? (
      <button type="button" onClick={handleSaveZip} disabled={savingZip} className={ctaLight}>
        {savingZip ? (
          <Loader2 className="h-6 w-6 animate-spin" aria-hidden />
        ) : zipFailed ? (
          <RefreshCw className="h-6 w-6" aria-hidden />
        ) : (
          <Save className="h-6 w-6" aria-hidden />
        )}
        {zipFailed ? t.downloadSuccess.tryAgain : t.downloadSuccess.save}
      </button>
    ) : onOpenFolder ? (
      <button type="button" onClick={onOpenFolder} className={ctaLight}>
        <FolderOpen className="h-6 w-6" aria-hidden />
        {t.downloadSuccess.openFolder}
      </button>
    ) : null;

  if (items.length === 0) {
    return (
      <PlatformBlock tone="ink">
        <p className="m-0 font-display text-2xl font-bold">{title}</p>
        <p className="m-0 text-lg">{t.playlist.empty}</p>
      </PlatformBlock>
    );
  }

  return (
    <>
      <PlatformBlock tone={platform}>
        <PlatformTag platform={platform} />

        {/* Playlist title + the main action */}
        <div className="grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
          <div className="flex min-w-0 flex-col gap-2">
            <h2 className={`${bigStatus} text-[clamp(1.75rem,4.5vw,3rem)] break-words`}>{title}</h2>
            <p className="m-0 text-lg">
              {t.playlist.totalItems} <strong className="font-bold tabular-nums">{items.length}</strong>
            </p>
          </div>
          {canSave ? (
            renderSaveButton()
          ) : (
            <button
              type="button"
              onClick={handleDownloadAll}
              disabled={busy || downloadAllIndices.length === 0}
              className={ctaLight}
            >
              <Download className="h-6 w-6" aria-hidden />
              {t.playlist.downloadAll}
            </button>
          )}
        </div>

        {/* Select section */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-lg font-medium text-balance">{t.playlist.orSelect}</span>
          {hasUnavailable && (
            <label className="inline-flex min-h-11 cursor-pointer items-center gap-3 text-base font-medium">
              <span>{t.playlist.showUnavailable}</span>
              <Switch
                checked={showUnavailable}
                onCheckedChange={setShowUnavailable}
                disabled={busy}
                className={blockSwitch}
              />
            </label>
          )}
        </div>

        {/* Select All */}
        <div className="flex min-h-11 items-center gap-3">
          <Checkbox
            checked={allSelected}
            disabled={busy || selectableIndices.length === 0}
            onCheckedChange={handleSelectAllChange}
            id="select-all-checkbox"
            className={blockCheckbox}
          />
          <label htmlFor="select-all-checkbox" className="cursor-pointer font-display text-lg font-bold">
            {t.playlist.selectAll}
          </label>
        </div>

        {truncated && (
          <p className="m-0 text-lg font-bold text-signal">
            {t.playlist.truncated.replace("{n}", String(items.length))}
          </p>
        )}

        {/* Item Rows */}
        <ul className="m-0 flex w-full list-none flex-col p-0">
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
                hideRedownload
              />
            );
          })}
        </ul>

        {/* Selected download bulk button */}
        {!busy && effectiveSelected.length > 0 && (
          <div>
            <button type="button" onClick={() => downloadRows(effectiveSelected)} className={ctaGhost}>
              <Download className="h-6 w-6" aria-hidden />
              {t.playlist.downloadItemsSelected}
            </button>
          </div>
        )}

        {/* Status and Action Buttons (Retry / Open Folder) */}
        {!busy && anyDone && (
          <div className="flex w-full flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-3 font-display text-lg font-bold">
              <span className="inline-flex items-center gap-2">
                <FolderX className="h-5 w-5 shrink-0" aria-hidden />
                {t.playlist.failedItems.replace("{n}", String(failedCount))}
              </span>
              <span className="inline-flex items-center gap-2">
                <FolderCheck className="h-5 w-5 shrink-0" aria-hidden />
                {t.playlist.savedItems.replace("{n}", String(doneCount))}
              </span>
            </div>

            <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap">
              {failedCount > 0 && (
                <button type="button" onClick={() => downloadRows(failedIndices)} className={ctaGhost}>
                  <RefreshCw className="h-5 w-5" aria-hidden />
                  {t.playlist.retry}
                </button>
              )}
              {renderSaveButton()}
            </div>
          </div>
        )}

        {/* Global running batch progress + Cancel */}
        {busy && batchSummary && (
          <div role="status" className="flex w-full flex-col gap-4">
            <p className="m-0 font-display text-xl font-bold">
              {t.playlist.downloadedProgress
                .replace("{done}", String(batchSummary.done))
                .replace("{total}", String(batchSummary.total))}
            </p>
            <Progress value={batchSummary.percent} aria-label={t.playlist.downloading} className={progressSlab} />
            <div>
              <button type="button" onClick={onCancel} className={ctaGhost}>
                <XCircle className="h-5 w-5" aria-hidden />
                {t.downloadProgress.cancelDownload}
              </button>
            </div>
          </div>
        )}
      </PlatformBlock>
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
