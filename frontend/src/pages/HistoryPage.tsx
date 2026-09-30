import { useState } from "react";
import { toast } from "sonner";
import { Copy, Download, Trash2 } from "lucide-react";
import { type Page } from "../components/Header";
import AnimatedSection from "../components/AnimatedSection";
import PlatformTag from "../components/PlatformTag";
import SectionCard from "../components/SectionCard";
import { Button } from "@/components/ui/button";
import { useLanguage } from "../i18n/LanguageContext";
import { clearHistory, loadHistory, removeHistoryEntry, type HistoryEntry } from "../lib/history";

interface HistoryPageProps {
  onNavigate: (page: Page) => void;
  onOpenUrl: (url: string) => void;
}

const HistoryPage = ({ onNavigate: _onNavigate, onOpenUrl }: HistoryPageProps) => {
  const { t, language } = useLanguage();
  const [entries, setEntries] = useState<HistoryEntry[]>(loadHistory);

  const formatTime = (timestamp: number): string =>
    new Intl.DateTimeFormat(language, { dateStyle: "medium", timeStyle: "short" }).format(new Date(timestamp));

  const handleCopy = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      toast.success(t.history.linkCopied);
    } catch {
      toast.error(t.history.copyFailed);
    }
  };

  const handleRemove = (url: string) => setEntries(removeHistoryEntry(url));

  const handleClearAll = () => {
    clearHistory();
    setEntries([]);
  };

  return (
    <div className="w-full select-none flex flex-col gap-4">
      <AnimatedSection>
        <SectionCard className="p-6 bg-white border border-slate-200/50 shadow-sm rounded-xl flex flex-col gap-2">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <h3 className="text-lg font-bold text-slate-900 m-0">{t.history.heading}</h3>
            {entries.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleClearAll}
                className="text-red-600 hover:bg-red-50 hover:text-red-700 gap-1.5"
              >
                <Trash2 className="h-4 w-4" />
                {t.history.clearAll}
              </Button>
            )}
          </div>
          <p className="text-sm text-slate-600 leading-relaxed m-0">{t.history.intro}</p>
        </SectionCard>
      </AnimatedSection>

      {entries.length === 0 && (
        <AnimatedSection delay={0.05}>
          <SectionCard className="p-6 bg-white border border-slate-200/50 shadow-sm rounded-xl">
            <p className="text-sm text-slate-500 m-0 text-center">{t.history.empty}</p>
          </SectionCard>
        </AnimatedSection>
      )}

      {entries.map((entry, index) => (
        <AnimatedSection key={entry.url} delay={Math.min(index, 5) * 0.05}>
          <SectionCard className="p-4 bg-white border border-slate-200/50 shadow-sm rounded-xl flex flex-col gap-3">
            <div className="flex items-start gap-3 min-w-0">
              <div className="h-12 w-12 rounded-lg bg-neutral-100 shrink-0 border border-neutral-200/50 overflow-hidden">
                {entry.thumbnail && (
                  <img
                    src={entry.thumbnail}
                    referrerPolicy="no-referrer"
                    alt=""
                    className="h-full w-full object-cover"
                    onError={(event) => {
                      // Signed CDN thumbnails expire; fall back to the plain tile.
                      event.currentTarget.style.display = "none";
                    }}
                  />
                )}
              </div>
              <div className="flex-1 min-w-0 flex flex-col gap-1">
                <h4 className="text-sm font-semibold text-slate-900 leading-snug line-clamp-2 break-words m-0">
                  {entry.title || t.history.untitled}
                </h4>
                <p className="text-xs text-slate-400 leading-snug truncate m-0" title={entry.url}>
                  {entry.url}
                </p>
                <div className="flex items-center gap-2 flex-wrap">
                  <PlatformTag platform={entry.platform} />
                  <span className="text-[11px] text-slate-400">{formatTime(entry.downloadedAt)}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              <Button
                size="sm"
                onClick={() => onOpenUrl(entry.url)}
                className="bg-[#0d9585] text-white hover:bg-[#0d9585]/90 gap-1.5 shadow-sm rounded-lg"
              >
                <Download className="h-4 w-4" />
                {t.history.downloadAgain}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void handleCopy(entry.url)}
                aria-label={`${t.history.copyLink}: ${entry.title || entry.url}`}
                className="gap-1.5 rounded-lg border-neutral-200 text-slate-700 shadow-none"
              >
                <Copy className="h-4 w-4" />
                {t.history.copyLink}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleRemove(entry.url)}
                aria-label={`${t.history.remove}: ${entry.title || entry.url}`}
                className="text-slate-500 hover:bg-red-50 hover:text-red-600 ml-auto"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </SectionCard>
        </AnimatedSection>
      ))}
    </div>
  );
};

export default HistoryPage;
