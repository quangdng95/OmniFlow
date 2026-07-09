import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
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
import { isLocal } from "../isLocal";

import youtube from "../assets/tags/Youtube.svg";
import tiktok from "../assets/tags/Tiktok.svg";
import instagram from "../assets/tags/Instagram.svg";
import facebook from "../assets/tags/Facebook.svg";
import rednote from "../assets/tags/Rednote.svg";
import threads from "../assets/tags/Threads.svg";
import linkedin from "../assets/tags/LinkedIn.svg";
import x from "../assets/tags/X.svg";

type DownloadState = "idle" | "downloading" | "done" | "fail";

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

const HomePage = ({ onNavigate: _onNavigate }: HomePageProps) => {
  const { t } = useLanguage();
  const [url, setUrl] = useState("");
  const [checking, setChecking] = useState(false);
  const [checkSeconds, setCheckSeconds] = useState(0);
  const [checkResult, setCheckResult] = useState<CheckResult | null>(null);
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

  const checkTokenRef = useRef(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const busy = batchJobId !== null;

  const resetDownloadState = () => {
    setDownloadState("idle");
    setRowStatus({});
    setActiveRows([]);
    setBatchJobId(null);
    setBatchSummary(null);
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
      toast.error(`${(e as Error).message} ${t.urlInput.checkFailedRetryHint}`);
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
    <div className="w-full select-none">
      <div className="w-full flex flex-col gap-4">
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

          {checking && (
            <CheckingStatusCard
              seconds={checkSeconds}
              onCancel={handleCancelCheck}
              showKeychainHint={isLocal() && /instagram|instagr\.am|threads\.(com|net)/i.test(url)}
            />
          )}

          {!checking && !checkResult && (
            <AnimatedSection className="flex flex-col gap-8 text-[#1f2937] w-full">
              {/* Introduction */}
              <div className="text-center max-w-[600px] mx-auto flex flex-col gap-3">
                <p className="text-sm font-medium text-slate-600 m-0">
                  {t.home.introLines[0]}
                </p>
                <p className="text-xs text-slate-400 m-0">
                  {t.home.introLines[1]} • {t.home.introLines[2]}
                </p>
              </div>

              {/* Supported Platforms */}
              <div className="flex flex-col items-center gap-3 select-none">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Supported Platforms
                </span>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 w-full">
                  {platforms.map((p) => (
                    <div
                      key={p.name}
                      className="flex flex-col items-center gap-2 p-3 bg-white border border-slate-200/50 rounded-xl cursor-default transition-all duration-200 hover:translate-y-[-1.5px] hover:shadow-sm hover:border-[#0d9585]"
                    >
                      <img src={p.icon} alt={p.name} className="h-6 w-auto object-contain" />
                      <span className="text-[10px] font-bold text-slate-500">{p.name}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Steps */}
              <div className="flex flex-col gap-4">
                <h3 className="text-base font-bold text-slate-800 text-center m-0">
                  {t.home.howToHeading}
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 w-full">
                  {t.home.steps.map((step, index) => (
                    <div
                      key={step.label}
                      className="flex flex-col gap-3 p-4 bg-white border border-slate-200/50 rounded-xl shadow-[0_2px_8px_rgba(0,0,0,0.01)]"
                    >
                      <div className="w-7 h-7 rounded-full bg-[#0d9585]/10 text-[#0d9585] flex items-center justify-center text-xs font-bold">
                        {index + 1}
                      </div>
                      <div className="flex flex-col gap-1">
                        <h4 className="text-xs font-bold text-slate-800 m-0">
                          {step.label}
                        </h4>
                        <p className="text-[11px] text-slate-500 leading-relaxed m-0">
                          {step.body}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Features */}
              <div className="flex flex-col gap-4">
                <h3 className="text-base font-bold text-slate-800 text-center m-0">
                  {t.home.featuresHeading}
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 w-full">
                  {t.home.features.map((feat) => (
                    <div
                      key={feat.title}
                      className="flex flex-col gap-1 p-4 bg-white border border-slate-200/50 rounded-xl"
                    >
                      <span className="text-xs font-bold text-[#0d9585]">{feat.title}</span>
                      <span className="text-[11px] text-slate-500 leading-relaxed">{feat.desc}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* FAQs */}
              <div className="flex flex-col gap-4 select-none">
                <h3 className="text-base font-bold text-slate-800 text-center m-0">
                  {t.home.faqHeading}
                </h3>
                <Accordion className="w-full bg-white border border-slate-200/60 rounded-xl p-2 px-4 shadow-sm">
                  {t.home.faqs.map((faq, index) => (
                    <AccordionItem key={index} value={String(index)} className="border-b border-neutral-100 last:border-0">
                      <AccordionTrigger className="text-xs font-semibold text-slate-800 hover:no-underline py-3">
                        {faq.q}
                      </AccordionTrigger>
                      <AccordionContent className="text-xs text-slate-500 leading-relaxed pb-3">
                        {faq.a}
                      </AccordionContent>
                    </AccordionItem>
                  ))}
                </Accordion>
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
            <VideoInfoCard
              info={selectedItem}
              actionState={downloadState}
              percent={progressPercent}
              filename={progressFilename}
              onDownload={handleStartDownload}
              onCancel={handleCancelDownload}
              onOpenFolder={isLocal() ? handleOpenFolder : undefined}
              downloadUrl={isLocal() || !jobId ? undefined : `/api/download-file/${jobId}`}
            />
          )}

      </div>
    </div>
  );
};

export default HomePage;
