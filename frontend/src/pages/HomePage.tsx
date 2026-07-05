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
import { api } from "../api";
import type { VideoInfo } from "../types";
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
  const [videoInfo, setVideoInfo] = useState<VideoInfo | null>(null);
  const [selectedQuality, setSelectedQuality] = useState<string>("");
  const [downloadState, setDownloadState] = useState<DownloadState>("idle");
  const [progressPercent, setProgressPercent] = useState(0);
  const [progressFilename, setProgressFilename] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [pasting, setPasting] = useState(false);

  const checkTokenRef = useRef(0);
  const inputRef = useRef<InputRef>(null);

  useEffect(() => {
    const trimmed = url.trim();
    if (!trimmed) {
      checkTokenRef.current += 1;
      setChecking(false);
      setVideoInfo(null);
      setDownloadState("idle");
      return;
    }

    setVideoInfo(null);
    setDownloadState("idle");
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
            progress.status === "error"
              ? progress.text || t.downloadStatus.failedFallback
              : t.downloadStatus.cancelled
          );
          clearInterval(id);
        }
      } catch {
        clearInterval(id);
      }
    }, 700);
    return () => clearInterval(id);
  }, [jobId, downloadState, t]);

  const runCheck = async (value: string, token: number) => {
    setChecking(true);
    setCheckSeconds(0);
    try {
      const info = await api.checkLink(value);
      if (checkTokenRef.current !== token) return;
      setVideoInfo(info);
      setSelectedQuality(info.qualities[0]);
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
    setVideoInfo(null);
    setDownloadState("idle");
    setJobId(null);
  };

  const handleCancelCheck = () => {
    checkTokenRef.current += 1;
    setChecking(false);
    setUrl("");
  };

  const handleStartDownload = async () => {
    if (!videoInfo) return;
    setDownloadState("downloading");
    setProgressPercent(0);
    setProgressFilename(null);
    try {
      const { job_id } = await api.startDownload(url.trim(), videoInfo.title, selectedQuality);
      setJobId(job_id);
    } catch (e) {
      message.error((e as Error).message);
      setDownloadState("idle");
    }
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
            clearDisabled={downloadState === "downloading"}
            pasting={pasting}
          />

          {checking && <CheckingStatusCard seconds={checkSeconds} onCancel={handleCancelCheck} />}

          {!checking && !videoInfo && (
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

          {videoInfo && (
            <>
              <VideoInfoCard info={videoInfo} />
              <QualityActionCard
                qualities={videoInfo.qualities}
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
