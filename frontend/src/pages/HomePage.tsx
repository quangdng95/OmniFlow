import { useEffect, useRef, useState } from "react";
import { message, type InputRef } from "antd";
import Header, { type Page } from "../components/Header";
import Footer from "../components/Footer";
import AnimatedSection from "../components/AnimatedSection";
import UrlInputCard from "../components/UrlInputCard";
import CheckingStatusCard from "../components/CheckingStatusCard";
import VideoInfoCard from "../components/VideoInfoCard";
import QualityActionCard from "../components/QualityActionCard";
import DownloadProgressCard from "../components/DownloadProgressCard";
import DownloadSuccessCard from "../components/DownloadSuccessCard";
import PlaylistItemsCard, { type BatchSummary } from "../components/PlaylistItemsCard";
import { api } from "../api";
import type { CheckResult, PlaylistItem, RowProgress, VideoInfo } from "../types";
import { useLanguage } from "../i18n/LanguageContext";
import { isLocal } from "../isLocal";

type DownloadState = "idle" | "downloading" | "done";

interface HomePageProps {
  onNavigate: (page: Page) => void;
}

const HomePage = ({ onNavigate }: HomePageProps) => {
  const { t } = useLanguage();
  const [url, setUrl] = useState("");
  const [checking, setChecking] = useState(false);
  const [checkSeconds, setCheckSeconds] = useState(0);
  const [checkResult, setCheckResult] = useState<CheckResult | null>(null);
  const [selectedQuality, setSelectedQuality] = useState<string>("");
  // Single-video flow.
  const [downloadState, setDownloadState] = useState<DownloadState>("idle");
  const [progressPercent, setProgressPercent] = useState(0);
  const [progressFilename, setProgressFilename] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  // Playlist flow: per-row download status + the currently-running batch job.
  const [rowStatus, setRowStatus] = useState<Record<number, RowProgress>>({});
  const [activeRows, setActiveRows] = useState<number[]>([]);
  const [batchJobId, setBatchJobId] = useState<string | null>(null);
  const [batchSummary, setBatchSummary] = useState<BatchSummary | null>(null);
  const [pasting, setPasting] = useState(false);

  const checkTokenRef = useRef(0);
  const inputRef = useRef<InputRef>(null);
  const busy = batchJobId !== null;

  const resetDownloadState = () => {
    setDownloadState("idle");
    setRowStatus({});
    setActiveRows([]);
    setBatchJobId(null);
    setBatchSummary(null);
  };

  useEffect(() => {
    const trimmed = url.trim();
    if (!trimmed) {
      checkTokenRef.current += 1;
      setChecking(false);
      setCheckResult(null);
      resetDownloadState();
      return;
    }

    setCheckResult(null);
    resetDownloadState();
    const token = ++checkTokenRef.current;
    const handle = setTimeout(() => {
      void runCheck(trimmed, token);
    }, 500);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  useEffect(() => {
    if (!checking) return;
    const id = setInterval(() => setCheckSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [checking]);

  // Single-video job poll.
  useEffect(() => {
    if (!jobId || downloadState !== "downloading") return;
    const id = setInterval(async () => {
      try {
        const progress = await api.getProgress(jobId);
        setProgressPercent(progress.percent);
        if (progress.status === "done") {
          setDownloadState("done");
          setProgressFilename(progress.filename);
          clearInterval(id);
        } else if (progress.status === "error" || progress.status === "cancelled") {
          setDownloadState("idle");
          message.error(
            progress.status === "error" ? progress.text || t.downloadStatus.failedFallback : t.downloadStatus.cancelled
          );
          clearInterval(id);
        }
      } catch {
        clearInterval(id);
      }
    }, 700);
    return () => clearInterval(id);
  }, [jobId, downloadState, t]);

  // Playlist batch job poll -> maps each item's progress back to its row.
  useEffect(() => {
    if (!batchJobId) return;
    const id = setInterval(async () => {
      try {
        const progress = await api.getProgress(batchJobId);
        if (progress.items_progress) {
          const ips = progress.items_progress;
          setRowStatus((prev) => {
            const next = { ...prev };
            ips.forEach((ip, k) => {
              const row = activeRows[k];
              if (row !== undefined) next[row] = { status: ip.status, percent: ip.percent };
            });
            return next;
          });
          // Overall bar for the global footer: a done item counts as 100%.
          const total = ips.length;
          const done = ips.filter((ip) => ip.status === "done").length;
          const percent = total
            ? ips.reduce((sum, ip) => sum + (ip.status === "done" ? 100 : ip.percent), 0) / total
            : 0;
          setBatchSummary({ done, total, percent });
        }
        if (progress.status !== "running") {
          setBatchJobId(null); // batch finished; rowStatus holds the final per-row state
          setBatchSummary(null); // footer switches to the "Saved: N items" summary
          clearInterval(id);
        }
      } catch {
        clearInterval(id);
      }
    }, 700);
    return () => clearInterval(id);
  }, [batchJobId, activeRows]);

  const runCheck = async (value: string, token: number) => {
    setChecking(true);
    setCheckSeconds(0);
    try {
      const result = await api.checkLink(value);
      if (checkTokenRef.current !== token) return;
      setCheckResult(result);
      if (result.type === "video") {
        setSelectedQuality(result.qualities[0]);
      } else if (result.type === "playlist" && result.items.length === 1) {
        // A 1-item playlist renders as a single video, so seed its quality too.
        setSelectedQuality(result.items[0].qualities[0]);
      }
    } catch (e) {
      if (checkTokenRef.current !== token) return;
      message.error((e as Error).message);
    } finally {
      if (checkTokenRef.current === token) setChecking(false);
    }
  };

  const handlePaste = async () => {
    setPasting(true);
    try {
      if (isLocal()) {
        // Reads via the server (pbpaste) instead of the browser's
        // navigator.clipboard API - that API is unreliable in this app's
        // actual runtime contexts (permission prompts that never resolve in
        // some browsers, and no support at all inside the desktop app's
        // embedded webview window). Only correct when browser and server
        // share a machine - pbpaste would read the wrong clipboard for a
        // remote visitor, which is why this branch only runs locally.
        const { text } = await api.getClipboard();
        setUrl(text.trim());
      } else {
        // A remote visitor's clipboard can only be read from their own
        // browser - the server has no access to it at all.
        const text = await navigator.clipboard.readText();
        setUrl(text.trim());
      }
    } catch (e) {
      message.error((e as Error).message);
      inputRef.current?.focus();
    } finally {
      setPasting(false);
    }
  };

  const handleClear = () => {
    checkTokenRef.current += 1;
    setUrl("");
    setCheckResult(null);
    resetDownloadState();
    setJobId(null);
  };

  const handleCancelCheck = () => {
    checkTokenRef.current += 1;
    setChecking(false);
    setUrl("");
  };

  // A 1-video "playlist" (e.g. a channel with one upload) is rendered as a plain
  // single video, not the multi-select list.
  const playlistSingle: PlaylistItem | null =
    checkResult?.type === "playlist" && checkResult.items.length === 1 ? checkResult.items[0] : null;

  const selectedItem: VideoInfo | null =
    checkResult?.type === "video"
      ? checkResult
      : playlistSingle && checkResult?.type === "playlist"
      ? {
          type: "video",
          title: playlistSingle.title,
          uploader: "",
          thumbnail: playlistSingle.thumbnail,
          platform: checkResult.platform,
          qualities: playlistSingle.qualities,
          duration: playlistSingle.duration,
          kind: playlistSingle.kind,
        }
      : null;

  const handleStartDownload = async () => {
    if (!selectedItem) return;
    setDownloadState("downloading");
    setProgressPercent(0);
    setProgressFilename(null);
    try {
      // For a 1-item playlist, download that item's own URL (or its entry_index
      // into the original URL for an Instagram Story); otherwise the pasted URL.
      const dlUrl = playlistSingle?.url ?? url.trim();
      const dlEntry = playlistSingle?.url ? undefined : playlistSingle?.entry_index;
      const { job_id } = await api.startDownload(dlUrl, selectedItem.title, selectedQuality, dlEntry);
      setJobId(job_id);
    } catch (e) {
      message.error((e as Error).message);
      setDownloadState("idle");
    }
  };

  // Download a set of playlist rows (a single item, a retry, or a bulk selection)
  // as one batch job, mapping its per-item progress back onto those rows.
  const handleDownloadItems = async (rowIndices: number[], quality: string) => {
    if (batchJobId || rowIndices.length === 0 || checkResult?.type !== "playlist") return;
    const playlist = checkResult;
    const items = rowIndices.map((i) => {
      const it = playlist.items[i];
      return { title: it.title, url: it.url, entryIndex: it.entry_index };
    });
    setActiveRows(rowIndices);
    setRowStatus((prev) => {
      const next = { ...prev };
      rowIndices.forEach((i) => (next[i] = { status: "pending", percent: 0 }));
      return next;
    });
    try {
      const { job_id } = await api.startBatchDownload(url.trim(), quality, items);
      setBatchJobId(job_id);
    } catch (e) {
      message.error((e as Error).message);
      setRowStatus((prev) => {
        const next = { ...prev };
        rowIndices.forEach((i) => (next[i] = { status: "error", percent: 0 }));
        return next;
      });
    }
  };

  const handleCancelBatch = async () => {
    if (batchJobId) await api.cancelJob(batchJobId);
  };

  const handleCancelDownload = async () => {
    if (!jobId) return;
    await api.cancelJob(jobId);
  };

  const handleOpenFolder = () => {
    void api.openFolder();
  };

  // "result" also covers a failed check: as long as there's text in the field,
  // offer Clear URL instead of reverting to Paste (which implies an empty field).
  const inputStatus = checking ? "checking" : url.trim() ? "result" : "idle";

  return (
    <>
      <Header active="home" onNavigate={onNavigate} />
      <div className="omniflow-content">
        <div className="omniflow-content-inner">
          <UrlInputCard
            ref={inputRef}
            value={url}
            onChange={setUrl}
            status={inputStatus}
            onPaste={handlePaste}
            onClear={handleClear}
            clearDisabled={downloadState === "downloading" || busy}
            pasting={pasting}
          />

          {checking && <CheckingStatusCard seconds={checkSeconds} onCancel={handleCancelCheck} />}

          {!checking && !checkResult && (
            <AnimatedSection style={{ display: "flex", flexDirection: "column", gap: 24, color: "rgba(26,26,26,0.92)" }}>
              <p style={{ fontSize: 14, lineHeight: "20px", margin: 0 }}>
                {t.home.introLines.map((line, index) => (
                  <span key={line}>
                    {line}
                    {index < t.home.introLines.length - 1 && <br />}
                  </span>
                ))}
              </p>
              <div>
                <p style={{ fontSize: 20, fontWeight: 600, margin: "0 0 16px" }}>{t.home.howToHeading}</p>
                <ol style={{ fontSize: 14, lineHeight: "20px" }}>
                  {t.home.steps.map((step) => (
                    <li key={step.label}>
                      <strong>{step.label}</strong> {step.body}
                    </li>
                  ))}
                </ol>
              </div>
            </AnimatedSection>
          )}

          {checkResult?.type === "playlist" && checkResult.items && checkResult.items.length !== 1 && (
            <PlaylistItemsCard
              title={checkResult.title || ""}
              platform={checkResult.platform}
              items={checkResult.items}
              truncated={checkResult.truncated}
              busy={busy}
              rowStatus={rowStatus}
              batchSummary={batchSummary}
              onDownloadItems={handleDownloadItems}
              onCancel={handleCancelBatch}
              onOpenFolder={isLocal() ? handleOpenFolder : undefined}
            />
          )}

          {selectedItem && (
            <>
              <VideoInfoCard info={selectedItem} />
              <QualityActionCard
                qualities={selectedItem.qualities}
                value={selectedQuality}
                onChange={setSelectedQuality}
                actionState={downloadState}
                onAction={handleStartDownload}
              />
              {downloadState === "downloading" && (
                <DownloadProgressCard percent={progressPercent} onCancel={handleCancelDownload} />
              )}
              {downloadState === "done" && progressFilename && (
                <DownloadSuccessCard
                  filename={progressFilename}
                  onOpenFolder={isLocal() ? handleOpenFolder : undefined}
                  downloadUrl={isLocal() || !jobId ? undefined : `/api/download-file/${jobId}`}
                />
              )}
            </>
          )}

          <Footer />
        </div>
      </div>
    </>
  );
};

export default HomePage;
