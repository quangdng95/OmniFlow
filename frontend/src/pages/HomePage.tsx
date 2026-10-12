import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { AlertCircle } from "lucide-react";
import PlatformBlock from "../components/PlatformBlock";
import { bigStatus, ctaSignal } from "../lib/blockStyles";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
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
import type { CheckResult, PlaylistItem, RowProgress, VideoInfo } from "../types";
import { useLanguage } from "../i18n/LanguageContext";
import { isLocal, isMobileRemote } from "../isLocal";
import { recordDownload } from "../lib/history";


type DownloadState = "idle" | "downloading" | "done" | "fail";

const platforms = [
  { name: "YouTube", color: "#ff0000" },
  { name: "TikTok", color: "#25f4ee" },
  { name: "Instagram", color: "#e1306c" },
  { name: "Facebook", color: "#1877f2" },
  { name: "RedNote", color: "#ff2442" },
  { name: "Threads", color: "#111111" },
  { name: "LinkedIn", color: "#0a66c2" },
  { name: "X", color: "#111111" },
];

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
          <div className="flex flex-col items-start gap-3 pt-2 text-left md:pt-6">
            <h1 className="m-0 font-display text-[clamp(2.75rem,14vw,10.5rem)] leading-[0.9] [:lang(vi)_&]:leading-[1.02] font-bold tracking-[-0.06em] text-ink uppercase">
              {t.header.home.taglineLines.map((line) => (
                <span key={line} className="block">
                  {line}
                </span>
              ))}
            </h1>
            <p className="m-0 max-w-[40em] text-[1.1875rem] leading-snug text-balance text-ink">{t.header.home.sub}</p>
          </div>
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

          {checkError && !checking && (
            <PlatformBlock tone="ink" role="alert">
              <AlertCircle className="h-11 w-11 text-signal" aria-hidden />
              <p className={`${bigStatus} text-[clamp(2rem,9vw,5.5rem)] text-signal`}>{t.urlInput.checkFailedTitle}</p>
              <p className="m-0 max-w-[32em] text-xl leading-snug">{checkError}</p>
              <p className="m-0 max-w-[32em] text-lg leading-snug">{t.urlInput.checkFailedRetryHint}</p>
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

          {!checking && !checkResult && (
            <AnimatedSection className="flex flex-col gap-10 pt-4 w-full">
              <section className="flex flex-col gap-3">
                <h2 className="m-0 text-xs font-medium uppercase tracking-wider text-muted-foreground">{t.home.supportedPlatformsHeading}</h2>
                <div className="flex flex-wrap gap-2">
                  {platforms.map((p) => (
                    <Badge key={p.name} variant="outline" className="h-6 gap-1.5 bg-card px-2.5 text-[13px] font-medium">
                      <span aria-hidden className="size-1.5 rounded-full" style={{ backgroundColor: p.color }} />
                      {p.name}
                    </Badge>
                  ))}
                </div>
              </section>

              <section className="flex flex-col gap-3">
                <h2 className="m-0 text-xs font-medium uppercase tracking-wider text-muted-foreground">{t.home.howToHeading}</h2>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  {t.home.steps.map((step, index) => (
                    <Card key={step.label}>
                      <CardHeader>
                        <Badge variant="secondary" className="mb-1 w-fit tabular-nums">
                          {String(index + 1).padStart(2, "0")}
                        </Badge>
                        <CardTitle className="text-sm font-semibold">{step.label}</CardTitle>
                        <CardDescription className="leading-relaxed">{step.body}</CardDescription>
                      </CardHeader>
                    </Card>
                  ))}
                </div>
              </section>

              <section className="flex flex-col gap-3">
                <h2 className="m-0 text-xs font-medium uppercase tracking-wider text-muted-foreground">{t.home.featuresHeading}</h2>
                <Card>
                  <CardContent className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
                    {t.home.features.map((feat, index) => (
                      <div key={feat.title} className="flex flex-col">
                        {index > 0 && <Separator className={index === 1 ? "sm:hidden" : undefined} />}
                        <div className="flex flex-col gap-1 py-3">
                          <h3 className="m-0 text-sm font-semibold">{feat.title}</h3>
                          <p className="m-0 text-[13px] leading-relaxed text-muted-foreground">{feat.desc}</p>
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </section>

              <section className="flex flex-col gap-3">
                <h2 className="m-0 text-xs font-medium uppercase tracking-wider text-muted-foreground">{t.home.faqHeading}</h2>
                <Card>
                  <CardContent>
                    <Accordion className="w-full">
                      {t.home.faqs.map((faq, index) => (
                        <AccordionItem key={index} value={String(index)}>
                          <AccordionTrigger className="py-3 text-sm font-medium hover:no-underline">
                            {faq.q}
                          </AccordionTrigger>
                          <AccordionContent className="pb-3 text-[13px] leading-relaxed text-muted-foreground">
                            {faq.a}
                          </AccordionContent>
                        </AccordionItem>
                      ))}
                    </Accordion>
                  </CardContent>
                </Card>
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
              onDownloadItems={handleDownloadItems}
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
              onDownload={handleStartDownload}
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
