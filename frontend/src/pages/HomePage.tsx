import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { AlertCircle } from "lucide-react";
import PlatformBlock from "../components/PlatformBlock";
import { bigStatus, ctaSignal } from "../lib/blockStyles";
import { blockToneClass } from "../lib/platform";
import { type Page } from "../components/Header";
import AnimatedSection from "../components/AnimatedSection";
import UrlInputCard, { type UrlInputStatus } from "../components/UrlInputCard";
import CheckingStatusCard from "../components/CheckingStatusCard";
import VideoInfoCard from "../components/VideoInfoCard";
import PlaylistItemsCard, { type BatchSummary } from "../components/PlaylistItemsCard";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { api } from "../api";
import type { CheckResult, Platform, PlaylistItem, RowProgress, VideoInfo } from "../types";
import { useLanguage } from "../i18n/LanguageContext";
import { isLocal, isMobileRemote } from "../isLocal";
import { recordDownload } from "../lib/history";
import { notifyIfHidden, requestNotifyPermission, truncateMiddle } from "../lib/notify";


// V3 accordion rows: hard rules between items, big display-type triggers.
const ACCORDION_ITEM = "border-b-[3px] border-ink not-last:border-b-[3px]";
const ACCORDION_TRIGGER =
  "min-h-16 items-center rounded-none border-0 px-0 py-3 font-display text-[1.375rem] font-bold tracking-[-0.02em] hover:no-underline";
const ACCORDION_CONTENT = "text-lg pb-5";

type DownloadState = "idle" | "downloading" | "done" | "fail";

// Order of the tile grid (4 x 2 on desktop).
const PLATFORM_TILES: Platform[] = ["YouTube", "TikTok", "Instagram", "Facebook", "Threads", "X", "LinkedIn", "RedNote"];

interface HomePageProps {
  onNavigate: (page: Page) => void;
  // A link chosen on the History page, to fill in and check.
  pendingUrl?: string | null;
  onPendingUrlConsumed?: () => void;
}

const HomePage = ({ onNavigate: _onNavigate, pendingUrl = null, onPendingUrlConsumed }: HomePageProps) => {
  const { t } = useLanguage();
  const [url, setUrl] = useState("");
  const [checking, setChecking] = useState(false);
  const [checkSeconds, setCheckSeconds] = useState(0);
  const [checkResult, setCheckResult] = useState<CheckResult | null>(null);
  // The friendly message of the last failed check, shown as an error block under the URL bar.
  const [checkError, setCheckError] = useState<string | null>(null);
  const [selectedQuality, setSelectedQuality] = useState<string>("Best");
  
  // Single-video flow
  const [downloadState, setDownloadState] = useState<DownloadState>("idle");
  const [progressPercent, setProgressPercent] = useState(0);
  const [progressFilename, setProgressFilename] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [pasting, setPasting] = useState(false);

  // Playlist flow
  const [rowStatus, setRowStatus] = useState<Record<number, RowProgress>>({});
  const [activeRows, setActiveRows] = useState<number[]>([]);
  const [batchJobId, setBatchJobId] = useState<string | null>(null);
  const [batchSummary, setBatchSummary] = useState<BatchSummary | null>(null);
  const [finishedBatchJobId, setFinishedBatchJobId] = useState<string | null>(null);

  const checkTokenRef = useRef(0);
  const titleRef = useRef("");
  const inputRef = useRef<HTMLInputElement>(null);
  const busy = batchJobId !== null;

  const resetDownloadState = () => {
    setDownloadState("idle");
    setRowStatus({});
    setActiveRows([]);
    setBatchJobId(null);
    setBatchSummary(null);
    setFinishedBatchJobId(null);
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
    setCheckError(null);
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

  // Single-video job poll
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
          setDownloadState(progress.status === "error" ? "fail" : "idle");
          toast.error(
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

  // Playlist batch job poll
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
          const total = ips.length;
          const done = ips.filter((ip) => ip.status === "done").length;
          const percent = total
            ? ips.reduce((sum, ip) => sum + (ip.status === "done" ? 100 : ip.percent), 0) / total
            : 0;
          setBatchSummary({ done, total, percent });
        }
        if (progress.status !== "running") {
          if (progress.status === "done") {
            setFinishedBatchJobId(batchJobId);
            const ips = progress.items_progress ?? [];
            announceBatchRef.current(
              ips.filter((ip) => ip.status === "done").length,
              ips.filter((ip) => ip.status === "error").length,
              titleRef.current
            );
          }
          setBatchJobId(null);
          setBatchSummary(null);
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
        setSelectedQuality(result.items[0].qualities[0]);
      } else if (result.type === "playlist" && result.items.length > 1) {
        const shared = result.items.find((it) => it && it.qualities && it.qualities.length > 1)?.qualities;
        if (shared) setSelectedQuality(shared[0]);
      }
    } catch (e) {
      if (checkTokenRef.current !== token) return;
      setCheckError((e as Error).message);
      setDownloadState("fail");
    } finally {
      if (checkTokenRef.current === token) setChecking(false);
    }
  };

  const handlePaste = async () => {
    setPasting(true);
    try {
      if (isLocal()) {
        const { text } = await api.getClipboard();
        setUrl(text.trim());
      } else {
        const text = await navigator.clipboard.readText();
        setUrl(text.trim());
      }
    } catch (e) {
      toast.error((e as Error).message);
      inputRef.current?.focus();
    } finally {
      setPasting(false);
    }
  };

  const handleRetryCheck = () => {
    const token = ++checkTokenRef.current;
    setCheckError(null);
    void runCheck(url.trim(), token);
  };

  const handleClear = () => {
    checkTokenRef.current += 1;
    setCheckError(null);
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

  const playlistSingle: PlaylistItem | null =
    checkResult?.type === "playlist" && checkResult.items.length === 1 ? checkResult.items[0] : null;

  titleRef.current = checkResult?.type === "playlist" ? checkResult.title || "" : "";

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

  const currentQualities: string[] =
    selectedItem?.qualities ??
    (checkResult?.type === "playlist"
      ? checkResult.items.find((it) => it && it.qualities && it.qualities.length > 1)?.qualities ?? []
      : []);

  // A link picked on the History page: fill it in, which re-runs the check.
  useEffect(() => {
    if (pendingUrl === null) return;
    setUrl(pendingUrl);
    onPendingUrlConsumed?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingUrl]);

  // "Saved" feedback. On the local app a finished job IS a saved file, so it
  // gets an in-page toast. On a remote deployment the file is only ready on the
  // server until the user taps Save (which has its own toast), so there is no
  // toast at "done" - only the system notification below, for a hidden tab.
  const announceSingle = (name: string) => {
    const label = truncateMiddle(name);
    if (isLocal()) toast.success(t.downloadSuccess.savedToDevice, { description: label });
    notifyIfHidden(isLocal() ? t.downloadSuccess.savedToDevice : t.downloadSuccess.ready, label);
  };
  // One message for a whole batch, never one per item.
  const announceBatch = (saved: number, failed: number, listTitle: string) => {
    if (saved <= 0) return;
    const head = (isLocal() ? t.downloadSuccess.batchSaved : t.downloadSuccess.batchReady).replace("{saved}", String(saved));
    const message = failed > 0 ? head + t.downloadSuccess.failedSuffix.replace("{failed}", String(failed)) : head;
    const label = truncateMiddle(listTitle);
    if (isLocal()) toast.success(message, { description: label });
    notifyIfHidden(message, label);
  };
  const announceBatchRef = useRef(announceBatch);
  announceBatchRef.current = announceBatch;

  useEffect(() => {
    if (downloadState !== "done" || !selectedItem) return;
    announceSingle(progressFilename || selectedItem.title);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [downloadState]);

  // Remember what this device downloaded (the History page lists the last 10).
  // Keyed on the transition to "done" / a newly finished batch job, so a
  // re-render never records the same download twice.
  useEffect(() => {
    if (downloadState !== "done" || !selectedItem) return;
    recordDownload({
      url: url.trim(),
      title: selectedItem.title,
      platform: selectedItem.platform,
      thumbnail: selectedItem.thumbnail ?? null,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [downloadState]);

  useEffect(() => {
    if (!finishedBatchJobId || checkResult?.type !== "playlist") return;
    recordDownload({
      url: url.trim(),
      title: checkResult.title || "",
      platform: checkResult.platform,
      thumbnail: checkResult.items.find((item) => item?.thumbnail)?.thumbnail ?? null,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finishedBatchJobId]);

  // Best-effort auto-paste: when the app opens (or the tab regains focus) and
  // the clipboard holds a link we haven't pasted yet, fill the empty input.
  // Browsers may refuse the read without a user gesture (iOS Safari asks first);
  // that is silent - the Paste button stays the fallback.
  const lastAutoPastedRef = useRef<string>("");
  const urlRef = useRef(url);
  urlRef.current = url;
  useEffect(() => {
    const tryAutoPaste = async () => {
      if (urlRef.current.trim() || document.visibilityState !== "visible") return;
      try {
        const text = isLocal()
          ? (await api.getClipboard()).text
          : await navigator.clipboard.readText();
        const candidate = text.trim();
        if (!/^https?:\/\/\S+$/i.test(candidate) || candidate === lastAutoPastedRef.current) return;
        if (urlRef.current.trim()) return;
        lastAutoPastedRef.current = candidate;
        setUrl(candidate);
      } catch {
        // Permission denied / no gesture / empty clipboard: leave the input alone.
      }
    };
    void tryAutoPaste();
    window.addEventListener("focus", tryAutoPaste);
    document.addEventListener("visibilitychange", tryAutoPaste);
    return () => {
      window.removeEventListener("focus", tryAutoPaste);
      document.removeEventListener("visibilitychange", tryAutoPaste);
    };
  }, []);

  // Phone: skip the "Start Download" tap - the user's only job is "Save to device".
  const autoStartedRef = useRef<string | null>(null);
  useEffect(() => {
    if (!isMobileRemote() || !selectedItem || downloadState !== "idle" || checking) return;
    const key = `${url.trim()}|${selectedItem.title}`;
    if (autoStartedRef.current === key) return;
    autoStartedRef.current = key;
    void handleStartDownload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedItem, downloadState, checking]);

  const handleStartDownload = async () => {
    if (!selectedItem) return;
    setDownloadState("downloading");
    setProgressPercent(0);
    setProgressFilename(null);
    try {
      const dlUrl = playlistSingle?.url ?? url.trim();
      const dlEntry = playlistSingle?.url ? undefined : playlistSingle?.entry_index;
      const { job_id } = await api.startDownload(dlUrl, selectedItem.title, selectedQuality, dlEntry);
      setJobId(job_id);
    } catch (e) {
      toast.error((e as Error).message);
      setDownloadState("fail");
    }
  };

  // The buttons ask for notification permission (a user gesture is required);
  // the phone auto-start calls handleStartDownload directly and never asks.
  const handleStartClick = () => {
    requestNotifyPermission();
    void handleStartDownload();
  };

  const handleDownloadItemsClick = (rowIndices: number[], quality: string) => {
    requestNotifyPermission();
    return handleDownloadItems(rowIndices, quality);
  };

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
      setFinishedBatchJobId(null);
      setBatchJobId(job_id);
    } catch (e) {
      toast.error((e as Error).message);
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

  // Input states mapping
  let inputStatus: UrlInputStatus = "idle";
  if (checking) {
    inputStatus = "checking";
  } else if (downloadState === "fail") {
    inputStatus = "error";
  } else if (url.trim()) {
    inputStatus = "result";
  }

  return (
    <div className="w-full">
      <div className="w-full flex flex-col gap-6">
          {/* Hero: kept short so the URL bar sits inside the first mobile screen. */}
          <div className="page-container flex flex-col items-start gap-3 pt-2 text-left md:pt-6">
            <h1 className="m-0 font-display text-[clamp(2.75rem,14vw,10.5rem)] leading-[0.9] [:lang(vi)_&]:leading-[1.02] font-bold tracking-[-0.06em] text-ink uppercase">
              {t.header.home.taglineLines.map((line) => (
                <span key={line} className="block">
                  {line}
                </span>
              ))}
            </h1>
            <p className="m-0 max-w-[40em] text-[1.1875rem] leading-snug text-balance text-ink">{t.header.home.sub}</p>
          </div>
          <div className="page-container">
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
          </div>

          {checkError && !checking && (
            <PlatformBlock tone="ink" role="alert">
              <AlertCircle className="h-11 w-11 text-signal" aria-hidden />
              <p className={`${bigStatus} text-[clamp(2rem,9vw,5.5rem)] text-signal`}>{t.urlInput.checkFailedTitle}</p>
              <p className="m-0 max-w-[32em] text-xl leading-snug">{checkError}</p>
              <div>
                <button type="button" onClick={handleRetryCheck} className={ctaSignal}>
                  {t.playlist.retry}
                </button>
              </div>
            </PlatformBlock>
          )}

          {checking && (
            <CheckingStatusCard
              seconds={checkSeconds}
              onCancel={handleCancelCheck}
              showKeychainHint={isLocal() && /instagram|instagr\.am|threads\.(com|net)/i.test(url)}
            />
          )}

          {!checking && !checkResult && !checkError && (
            <AnimatedSection className="page-container flex flex-col gap-8">
              <section aria-labelledby="platforms-heading">
                <h2 id="platforms-heading" className="sr-only">
                  {t.home.supportedPlatformsHeading}
                </h2>
                <ul className="m-0 grid list-none grid-cols-2 border-t-[3px] border-ink p-0 md:grid-cols-4">
                  {PLATFORM_TILES.map((name, index) => (
                    <li
                      key={name}
                      className={`m-0 flex min-h-24 items-end border-b-[3px] border-ink p-4 font-display text-[clamp(1.5rem,6vw,2.5rem)] leading-none font-bold tracking-[-0.04em] md:min-h-44 md:p-5 ${blockToneClass(name)} ${
                        index % 2 === 0 ? "border-r-[3px]" : ""
                      } ${index % 4 !== 3 ? "md:border-r-[3px]" : "md:border-r-0"}`}
                    >
                      {name}
                    </li>
                  ))}
                </ul>
              </section>

              <section className="border-t-[3px] border-ink">
                <Accordion className="w-full">
                  <AccordionItem value="how" className={ACCORDION_ITEM}>
                    <AccordionTrigger className={ACCORDION_TRIGGER}>{t.home.howToHeading}</AccordionTrigger>
                    <AccordionContent className={ACCORDION_CONTENT}>
                      <ol className="m-0 flex max-w-[42em] list-decimal flex-col gap-2 pl-6">
                        {t.home.steps.map((step) => (
                          <li key={step} className="m-0 text-lg">
                            {step}
                          </li>
                        ))}
                      </ol>
                    </AccordionContent>
                  </AccordionItem>
                  <AccordionItem value="why" className={ACCORDION_ITEM}>
                    <AccordionTrigger className={ACCORDION_TRIGGER}>{t.home.whyHeading}</AccordionTrigger>
                    <AccordionContent className={ACCORDION_CONTENT}>
                      <p className="m-0 max-w-[42em] text-lg">{t.home.whyBody}</p>
                    </AccordionContent>
                  </AccordionItem>
                  <AccordionItem value="faq" className={ACCORDION_ITEM}>
                    <AccordionTrigger className={ACCORDION_TRIGGER}>{t.home.faqHeading}</AccordionTrigger>
                    <AccordionContent className={ACCORDION_CONTENT}>
                      <dl className="m-0 flex max-w-[42em] flex-col gap-4">
                        {t.home.faqs.map((faq) => (
                          <div key={faq.q}>
                            <dt className="font-bold text-lg">{faq.q}</dt>
                            <dd className="m-0 text-lg">{faq.a}</dd>
                          </div>
                        ))}
                      </dl>
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
              </section>
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
              onDownloadItems={handleDownloadItemsClick}
              onCancel={handleCancelBatch}
              onOpenFolder={isLocal() ? handleOpenFolder : undefined}
              downloadUrl={isLocal() || !finishedBatchJobId ? undefined : `/api/download-file/${finishedBatchJobId}`}
            />
          )}

          {selectedItem && (
            <VideoInfoCard
              info={selectedItem}
              actionState={downloadState}
              percent={progressPercent}
              filename={progressFilename}
              onDownload={handleStartClick}
              onCancel={handleCancelDownload}
              onOpenFolder={isLocal() ? handleOpenFolder : undefined}
              downloadUrl={isLocal() || !jobId ? undefined : `/api/download-file/${jobId}`}
              autoSave={isMobileRemote()}
            />
          )}

      </div>
    </div>
  );
};

export default HomePage;
