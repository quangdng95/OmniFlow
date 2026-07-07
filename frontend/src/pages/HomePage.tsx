import { useEffect, useRef, useState } from "react";
import { message, type InputRef, Collapse } from "antd";
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

import youtube from "../assets/tags/Youtube.svg";
import tiktok from "../assets/tags/Tiktok.svg";
import instagram from "../assets/tags/Instagram.svg";
import facebook from "../assets/tags/Facebook.svg";
import rednote from "../assets/tags/Rednote.svg";
import threads from "../assets/tags/Threads.svg";
import linkedin from "../assets/tags/LinkedIn.svg";
import x from "../assets/tags/X.svg";

type DownloadState = "idle" | "downloading" | "done";

const platforms = [
  { name: "YouTube", icon: youtube },
  { name: "TikTok", icon: tiktok },
  { name: "Instagram", icon: instagram },
  { name: "Facebook", icon: facebook },
  { name: "RedNote", icon: rednote },
  { name: "Threads", icon: threads },
  { name: "LinkedIn", icon: linkedin },
  { name: "X (Twitter)", icon: x },
];

interface HomePageProps {
  onNavigate: (page: Page) => void;
}

const HomePage = ({ onNavigate }: HomePageProps) => {
  const { t } = useLanguage();
  const [url, setUrl] = useState("");
  const [checking, setChecking] = useState(false);
  const [checkSeconds, setCheckSeconds] = useState(0);
  const [checkResult, setCheckResult] = useState<CheckResult | null>(null);
  // "Best" is the fallback for a batch whose items have no shared quality
  // ladder (e.g. an Instagram carousel, where each slide only ever carries
  // its own single-option ["Image"]/["Video"]) - PlaylistItemsCard used to
  // default its own local state this way; preserved here now that the value
  // is lifted so per-item downloads still pass a sane quality.
  const [selectedQuality, setSelectedQuality] = useState<string>("Best");
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
    // Each new check starts fresh, same as when PlaylistItemsCard used to
    // remount per-check with its own local default - runCheck's seeding
    // overwrites this once the new result's real qualities are known.
    setSelectedQuality("Best");
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
      } else if (result.type === "playlist" && result.items.length > 1) {
        // Flat playlist items share one quality ladder - seed it from whichever
        // item actually carries it (see currentQualities below).
        const shared = result.items.find((it) => it && it.qualities && it.qualities.length > 1)?.qualities;
        if (shared) setSelectedQuality(shared[0]);
      }
    } catch (e) {
      if (checkTokenRef.current !== token) return;
      message.error(`${(e as Error).message} ${t.urlInput.checkFailedRetryHint}`);
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

  // Shared quality ladder for the selector in UrlInputCard - covers a single
  // video, a 1-item playlist (via selectedItem), or a multi-item playlist's
  // one common ladder (flat items can't have their own per-item formats).
  const currentQualities: string[] =
    selectedItem?.qualities ??
    (checkResult?.type === "playlist"
      ? checkResult.items.find((it) => it && it.qualities && it.qualities.length > 1)?.qualities ?? []
      : []);

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
            qualities={currentQualities}
            qualityValue={selectedQuality}
            onQualityChange={setSelectedQuality}
            qualityDisabled={checking || downloadState === "downloading" || busy}
          />

          {checking && <CheckingStatusCard seconds={checkSeconds} onCancel={handleCancelCheck} />}

          {!checking && !checkResult && (
            <AnimatedSection style={{ display: "flex", flexDirection: "column", gap: 32, color: "#1f2937", width: "100%" }}>
              {/* Introduction */}
              <div style={{ textAlign: "center", maxWidth: 600, margin: "0 auto", display: "flex", flexDirection: "column", gap: 12 }}>
                <p style={{ fontSize: 15, lineHeight: "22px", margin: 0, color: "#4b5563", fontWeight: 500 }}>
                  {t.home.introLines[0]}
                </p>
                <p style={{ fontSize: 13, lineHeight: "18px", margin: 0, color: "#9ca3af" }}>
                  {t.home.introLines[1]} • {t.home.introLines[2]}
                </p>
              </div>

              {/* Supported Platforms Grid */}
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
                <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "1.5px", color: "#9ca3af" }}>
                  Supported Platforms
                </span>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(100px, 1fr))", gap: 12, width: "100%" }}>
                  {platforms.map((p) => (
                    <div
                      key={p.name}
                      className="omniflow-platform-card"
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        gap: 8,
                        padding: "12px 8px",
                        background: "#ffffff",
                        border: "1px solid #f0f0f0",
                        borderRadius: 12,
                        cursor: "default",
                        transition: "all 0.2s ease-in-out",
                      }}
                    >
                      <img src={p.icon} alt={p.name} style={{ height: 24, width: "auto", objectFit: "contain" }} />
                      <span style={{ fontSize: 11, fontWeight: 600, color: "#4b5563" }}>{p.name}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* How to Download Steps */}
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <p style={{ fontSize: 18, fontWeight: 700, margin: 0, color: "#1f2937", textAlign: "center" }}>
                  {t.home.howToHeading}
                </p>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16, width: "100%" }}>
                  {t.home.steps.map((step, index) => (
                    <div
                      key={step.label}
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 12,
                        padding: 16,
                        background: "#ffffff",
                        border: "1px solid #f0f0f0",
                        borderRadius: 12,
                        boxShadow: "0 2px 8px rgba(0,0,0,0.01)",
                      }}
                    >
                      <div
                        style={{
                          width: 28,
                          height: 28,
                          borderRadius: "50%",
                          background: "rgba(13, 149, 133, 0.1)",
                          color: "#0d9585",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: 14,
                          fontWeight: 700,
                        }}
                      >
                        {index + 1}
                      </div>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: "#1f2937", marginBottom: 4 }}>
                          {step.label}
                        </div>
                        <div style={{ fontSize: 12, color: "#6b7280", lineHeight: "18px" }}>
                          {step.body}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Features / Benefits Grid */}
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <p style={{ fontSize: 18, fontWeight: 700, margin: 0, color: "#1f2937", textAlign: "center" }}>
                  {t.home.featuresHeading}
                </p>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16, width: "100%" }}>
                  {t.home.features.map((feat) => (
                    <div
                      key={feat.title}
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 4,
                        padding: 16,
                        background: "#ffffff",
                        border: "1px solid #f0f0f0",
                        borderRadius: 12,
                      }}
                    >
                      <span style={{ fontSize: 13, fontWeight: 700, color: "#0d9585" }}>{feat.title}</span>
                      <span style={{ fontSize: 12, color: "#6b7280", lineHeight: "16px" }}>{feat.desc}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* FAQ Section */}
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <p style={{ fontSize: 18, fontWeight: 700, margin: 0, color: "#1f2937", textAlign: "center" }}>
                  {t.home.faqHeading}
                </p>
                <Collapse
                  ghost
                  accordion
                  expandIconPlacement="end"
                  style={{ background: "#ffffff", border: "1px solid #f0f0f0", borderRadius: 12, padding: "4px 8px" }}
                  items={t.home.faqs.map((faq, index) => ({
                    key: String(index),
                    label: <span style={{ fontSize: 13, fontWeight: 600, color: "#1f2937" }}>{faq.q}</span>,
                    children: <p style={{ fontSize: 12, color: "#4b5563", margin: 0, lineHeight: "18px" }}>{faq.a}</p>,
                  }))}
                />
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
              quality={selectedQuality}
              onDownloadItems={handleDownloadItems}
              onCancel={handleCancelBatch}
              onOpenFolder={isLocal() ? handleOpenFolder : undefined}
            />
          )}

          {selectedItem && (
            <>
              <VideoInfoCard info={selectedItem} />
              <QualityActionCard actionState={downloadState} onAction={handleStartDownload} />
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
