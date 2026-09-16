import { useState } from "react";
import { toast } from "sonner";
import { Copy, Check, TriangleAlert } from "lucide-react";
import { type Page } from "../components/Header";
import SectionCard from "../components/SectionCard";
import { useLanguage } from "../i18n/LanguageContext";

interface ShortcutSetupPageProps {
  onNavigate: (page: Page) => void;
}

// Apple's own Shortcuts-app action names - kept verbatim (never translated)
// so the guide's wording matches what actually appears on screen while
// building the shortcut. Longest-first so "Get Contents of URL" wins over
// a shorter prefix that could otherwise match first.
const ACTION_PREFIXES = [
  "Get Contents of URL",
  "Get Dictionary Value",
  "Stop This Shortcut",
  "Set Variable",
  "Get Clipboard",
  "End Repeat",
  "Show Alert",
  "Quick Look",
  "Open URLs",
  "Dictionary",
  "Otherwise",
  "End If",
  "Repeat",
  "Wait",
  "If",
].sort((a, b) => b.length - a.length);

const renderStepText = (raw: string, origin: string) => {
  const text = raw.replace(/\{origin\}/g, origin);
  const prefix = ACTION_PREFIXES.find(
    (p) => text === p || text.startsWith(`${p} `) || text.startsWith(`${p}—`)
  );
  if (!prefix) return <span>{text}</span>;
  return (
    <>
      <span className="inline-flex items-center rounded-md border border-[#0d9585]/30 bg-[#0d9585]/10 px-1.5 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wide text-[#0d9585] mr-1.5 align-middle">
        {prefix}
      </span>
      <span className="align-middle text-slate-700">{text.slice(prefix.length)}</span>
    </>
  );
};

const copyText = async (value: string, message: string) => {
  try {
    await navigator.clipboard.writeText(value);
  } catch {
    const ta = document.createElement("textarea");
    ta.value = value;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
  }
  toast.success(message);
};

const ShortcutSetupPage = ({ onNavigate: _onNavigate }: ShortcutSetupPageProps) => {
  const { t } = useLanguage();
  const [copied, setCopied] = useState(false);
  const origin = window.location.origin;

  const handleCopyUrl = async () => {
    await copyText(origin, "Đã copy");
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };

  return (
    <div className="w-full select-none flex flex-col gap-4">
      <SectionCard className="p-6 bg-white border border-slate-200/50 shadow-sm rounded-xl flex flex-col gap-2">
        <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-[#0d9585]">
          {t.shortcutSetup.eyebrow}
        </span>
        <h3 className="text-lg font-bold text-slate-900 m-0">{t.shortcutSetup.heading}</h3>
        <p className="text-sm text-slate-600 leading-relaxed m-0">{t.shortcutSetup.intro}</p>
      </SectionCard>

      <SectionCard className="p-5 bg-amber-50 border border-amber-200 shadow-sm rounded-xl flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <TriangleAlert className="h-4 w-4 text-amber-700 shrink-0" />
          <h4 className="text-sm font-bold text-amber-900 m-0">{t.shortcutSetup.warningTitle}</h4>
        </div>
        <p className="text-xs text-amber-800/90 leading-relaxed m-0">{t.shortcutSetup.warningBody}</p>
      </SectionCard>

      <SectionCard className="p-5 bg-white border border-slate-200/50 shadow-sm rounded-xl flex flex-col gap-3">
        <h4 className="text-sm font-bold text-slate-900 m-0">{t.shortcutSetup.valuesTitle}</h4>
        <div className="flex flex-col gap-1.5">
          <span className="text-xs text-slate-500">{t.shortcutSetup.valuesUrlLabel}</span>
          <button
            onClick={handleCopyUrl}
            className="inline-flex items-center gap-2 self-start rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-800 hover:border-[#0d9585] transition-colors max-w-full overflow-x-auto"
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-[#0d9585] shrink-0" />
            ) : (
              <Copy className="h-3.5 w-3.5 text-slate-400 shrink-0" />
            )}
            {origin}
          </button>
        </div>
        <p className="text-xs text-slate-600 leading-relaxed m-0">{t.shortcutSetup.valuesTokenNote}</p>
      </SectionCard>

      {t.shortcutSetup.phases.map((phase) => (
        <SectionCard
          key={phase.num}
          className="p-0 bg-white border border-slate-200/50 shadow-sm rounded-xl overflow-hidden flex flex-col gap-0"
        >
          <div className="flex items-baseline gap-3 px-5 py-4 bg-slate-50 border-b border-slate-100">
            <span className="font-mono text-xs font-bold text-[#0d9585] shrink-0">{phase.num}</span>
            <div className="flex flex-col gap-0.5 min-w-0">
              <span className="text-sm font-extrabold text-slate-900">{phase.title}</span>
              <span className="text-xs text-slate-500">{phase.desc}</span>
            </div>
          </div>
          <ol className="flex flex-col px-5 py-2 list-none pl-0">
            {phase.steps.map((step, i) => (
              <li
                key={i}
                className={`text-sm leading-relaxed py-2.5 border-t border-dashed border-slate-100 first:border-t-0 ${
                  step.nested ? "ml-5 pl-3 border-l-2 border-l-[#0d9585]/20" : ""
                }`}
              >
                {renderStepText(step.text, origin)}
              </li>
            ))}
          </ol>
        </SectionCard>
      ))}

      <p className="text-xs text-slate-400 leading-relaxed px-2">{t.shortcutSetup.footerNote}</p>
    </div>
  );
};

export default ShortcutSetupPage;
