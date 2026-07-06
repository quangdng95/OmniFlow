import { useMemo, useState } from "react";
import { Button, Checkbox, Progress, Segmented, Switch, Tag } from "antd";
import {
  DownloadOutlined,
  RedoOutlined,
  FolderOpenOutlined,
  CloseCircleOutlined,
  CheckCircleFilled,
} from "@ant-design/icons";
import SectionCard from "./SectionCard";
import PlatformTag from "./PlatformTag";
import { useLanguage } from "../i18n/LanguageContext";
import type { Platform, PlaylistItem, RowProgress, RowDownloadStatus } from "../types";

// Overall progress of the currently-running batch, for the global footer bar.
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
  busy: boolean; // a batch is currently running
  rowStatus: Record<number, RowProgress>;
  batchSummary: BatchSummary | null;
  onDownloadItems: (rowIndices: number[], quality: string) => void;
  onCancel?: () => void;
  onOpenFolder?: () => void;
}

const GREEN = "#0d9585"; // primary / outline-green
const GREEN_TEXT = "#389e0d"; // success text
const RED = "#cf1322";
const ORANGE = "#d46b08";

const outlineGreen = { color: GREEN, borderColor: GREEN };
const outlineOrange = { color: ORANGE, borderColor: ORANGE };

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
  onDownloadItems,
  onCancel,
  onOpenFolder,
}: PlaylistItemsCardProps) => {
  const { t } = useLanguage();

  const qualityOptions = useMemo(
    () => (items || []).find((it) => it && it.qualities && it.qualities.length > 1)?.qualities ?? [],
    [items]
  );
  const [quality, setQuality] = useState<string>(qualityOptions[0] ?? "Best");
  const [selected, setSelected] = useState<Set<number>>(() => new Set());
  const [showUnavailable, setShowUnavailable] = useState(false);

  // A row is selectable/downloadable only if available AND not already done.
  const selectableIndices = useMemo(
    () =>
      (items || [])
        .map((_, i) => i)
        .filter((i) => items[i] && isAvailable(items[i]) && statusOf(rowStatus, i) !== "done"),
    [items, rowStatus]
  );
  const hasUnavailable = (items || []).some((it) => it && !isAvailable(it));
  // A downloaded row is auto-dropped from the selection everywhere.
  const effectiveSelected = useMemo(
    () => selectableIndices.filter((i) => selected.has(i)),
    [selectableIndices, selected]
  );
  const doneCount = Object.values(rowStatus || {}).filter((r) => r && r.status === "done").length;
  const anyDone = doneCount > 0;
  // Numbering width scales to the list size (01. / 001.). UI-only — never in the file.
  const numWidth = Math.max(2, String(items.length).length);

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
        <p style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>{title}</p>
        <p style={{ fontSize: 14, margin: 0 }}>{t.playlist.empty}</p>
      </SectionCard>
    );
  }

  // The far-right cluster of a row: its live status + its action button.
  const renderRightContent = (index: number, status: RowDownloadStatus, percent: number) => {
    const trigger = (e: React.MouseEvent) => {
      e.stopPropagation(); // don't also toggle the row's checkbox
      downloadRows([index]);
    };
    if (status === "downloading" || status === "pending") {
      const shown = status === "downloading" ? percent : 0;
      return (
        <div style={{ width: 132, display: "flex", flexDirection: "column", gap: 2 }}>
          <span style={{ fontSize: 12, color: GREEN }}>
            {status === "downloading"
              ? t.playlist.percentDownloading.replace("{p}", String(Math.round(shown)))
              : `⏳ ${t.playlist.queued}`}
          </span>
          <Progress percent={Math.round(shown)} showInfo={false} strokeColor={GREEN} size="small" />
        </div>
      );
    }
    if (status === "done") {
      return (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
          <span style={{ fontSize: 12, color: GREEN_TEXT }}>✅ {t.playlist.downloaded}</span>
          <Button size="small" icon={<RedoOutlined />} onClick={trigger} disabled={busy} style={outlineOrange}>
            {t.playlist.downloadAgain}
          </Button>
        </div>
      );
    }
    if (status === "error") {
      return (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
          <span style={{ fontSize: 12, color: RED }}>❌ {t.playlist.failed}</span>
          <Button size="small" danger icon={<RedoOutlined />} onClick={trigger} disabled={busy}>
            {t.playlist.retry}
          </Button>
        </div>
      );
    }
    // idle -> outline-green Download button for just this row
    return (
      <Button
        size="small"
        icon={<DownloadOutlined />}
        onClick={trigger}
        disabled={busy}
        style={busy ? undefined : outlineGreen}
        aria-label="download-item"
      >
        {t.playlist.download}
      </Button>
    );
  };

  return (
    <>
      <SectionCard>
        <PlatformTag platform={platform} />
        <p style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>{title}</p>

        {/* Overview row: Total Items + Download All (State 1 header). */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <span style={{ fontSize: 14 }}>
            {t.playlist.totalItems} <strong>{items.length}</strong>
          </span>
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            onClick={() => downloadRows(selectableIndices)}
            disabled={busy || selectableIndices.length === 0}
          >
            {t.playlist.downloadAll}
          </Button>
        </div>

        {qualityOptions.length > 1 && (
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <span style={{ fontSize: 12 }}>{t.qualityAction.videoQuality}</span>
            <Segmented options={qualityOptions} value={quality} onChange={(v) => setQuality(v as string)} disabled={busy} />
          </div>
        )}

        {/* Hint + unavailable filter. */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontSize: 13, color: "rgba(0,0,0,0.55)" }}>{t.playlist.orSelect}</span>
          {hasUnavailable && (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, color: "rgba(0,0,0,0.65)" }}>
              {t.playlist.showUnavailable}
              <Switch size="small" checked={showUnavailable} onChange={setShowUnavailable} disabled={busy} />
            </span>
          )}
        </div>
        {truncated && (
          <p style={{ fontSize: 12, margin: 0, color: ORANGE }}>{t.playlist.truncated.replace("{n}", String(items.length))}</p>
        )}

        {/* Item rows. */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "100%" }}>
          {items.map((item, index) => {
            const available = isAvailable(item);
            if (!available && !showUnavailable) return null;
            const status = statusOf(rowStatus, index);
            const isDone = status === "done";
            const selectable = available && !isDone;
            const position = item.position ?? index + 1;
            return (
              <div
                key={item.id ?? index}
                onClick={() => !busy && selectable && toggleItem(index)}
                role="checkbox"
                aria-checked={selected.has(index) && !isDone}
                aria-disabled={!selectable}
                style={{
                  display: "flex",
                  gap: 12,
                  alignItems: "center",
                  width: "100%",
                  padding: 4,
                  opacity: available ? 1 : 0.45,
                  cursor: busy || !selectable ? "default" : "pointer",
                }}
              >
                <Checkbox checked={selected.has(index) && !isDone} disabled={busy || !selectable} style={{ pointerEvents: "none" }} />
                <span style={{ fontSize: 13, fontWeight: 600, color: "rgba(0,0,0,0.55)", minWidth: 28, flexShrink: 0 }}>
                  {String(position).padStart(numWidth, "0")}.
                </span>
                {item.thumbnail && (
                  <img
                    src={item.thumbnail}
                    referrerPolicy="no-referrer"
                    alt={item.title}
                    style={{ width: 56, height: 56, borderRadius: 6, objectFit: "cover", flexShrink: 0, background: "#e5e7eb" }}
                  />
                )}
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, wordBreak: "break-word", whiteSpace: "normal" }}>{item.title}</div>
                  {item.uploader && (
                    <div style={{ fontSize: 12, color: "rgba(0,0,0,0.55)", marginTop: 2 }}>{item.uploader}</div>
                  )}
                  <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 2 }}>
                    {item.kind && (
                      <Tag color={item.kind === "image" ? "blue" : "green"} style={{ margin: 0 }}>
                        {item.kind === "image" ? t.playlist.photo : t.playlist.video}
                      </Tag>
                    )}
                    {!available && (
                      <Tag color="default" style={{ margin: 0 }}>
                        {t.playlist.unavailable}
                      </Tag>
                    )}
                    {item.duration && <span style={{ fontSize: 12, color: "rgba(0,0,0,0.45)" }}>{item.duration}</span>}
                  </div>
                </div>
                {/* Right: per-item status + action (real videos only). */}
                {available && (
                  <div style={{ display: "flex", justifyContent: "flex-end", flexShrink: 0, minWidth: 132 }}>
                    {renderRightContent(index, status, rowStatus[index]?.percent ?? 0)}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* State 4: a manual selection exists -> outline-green bulk button below the list. */}
        {!busy && effectiveSelected.length > 0 && (
          <Button block icon={<DownloadOutlined />} onClick={() => downloadRows(effectiveSelected)} style={outlineGreen}>
            {t.playlist.downloadItemsSelected}
          </Button>
        )}
      </SectionCard>

      {/* Global footer: running batch progress + Cancel, OR the saved summary + Open Folder. */}
      {busy && batchSummary && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12, width: "100%" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span style={{ fontSize: 14, fontWeight: 500 }}>
              {t.playlist.downloadedProgress
                .replace("{done}", String(batchSummary.done))
                .replace("{total}", String(batchSummary.total))}
            </span>
            <Progress percent={Math.round(batchSummary.percent)} showInfo={false} strokeColor={GREEN} />
          </div>
          <Button block danger type="primary" icon={<CloseCircleOutlined />} onClick={onCancel}>
            {t.downloadProgress.cancelDownload}
          </Button>
        </div>
      )}
      {!busy && anyDone && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12, width: "100%" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 500, color: GREEN_TEXT }}>
            <CheckCircleFilled />
            {t.playlist.savedItems.replace("{n}", String(doneCount))}
          </span>
          {onOpenFolder && (
            <Button block type="primary" icon={<FolderOpenOutlined />} onClick={onOpenFolder}>
              {t.downloadSuccess.openFolder}
            </Button>
          )}
        </div>
      )}
    </>
  );
};

export default PlaylistItemsCard;
