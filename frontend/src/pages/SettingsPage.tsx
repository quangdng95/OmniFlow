import { useEffect, useState } from "react";
import { Folder, ScrollText } from "lucide-react";
import { toast } from "sonner";
import { type Page } from "../components/Header";
import SectionCard from "../components/SectionCard";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { api } from "../api";
import { useLanguage } from "../i18n/LanguageContext";
import type { Language } from "../i18n/translations";
import { isLocal } from "../isLocal";

interface SettingsPageProps {
  onNavigate: (page: Page) => void;
}

const SettingsPage = ({ onNavigate: _onNavigate }: SettingsPageProps) => {
  const { t, language, setLanguage } = useLanguage();
  const [path, setPath] = useState("");
  const [rememberPath, setRememberPath] = useState(true);
  const [playlistLimit, setPlaylistLimit] = useState(100);

  useEffect(() => {
    void api.getSettings().then((settings) => {
      setPath(settings.path);
      setPlaylistLimit(settings.playlist_limit ?? 100);
    });
  }, []);

  const handlePlaylistLimitChange = async (newVal: number) => {
    setPlaylistLimit(newVal);
    await api.updateSettings({ playlist_limit: newVal });
  };

  const handleBrowse = async () => {
    try {
      const { path: chosen } = await api.browseFolder();
      setPath(chosen);
      await api.updateSettings({ path: chosen });
    } catch {
      // user cancelled the folder picker
    }
  };

  const handlePathChange = async (newVal: string) => {
    setPath(newVal);
    await api.updateSettings({ path: newVal });
  };

  const handleOpenLogs = async () => {
    try {
      const { has_logs } = await api.openLogs();
      toast.success(has_logs ? t.settingsPage.exportLogs.opened : t.settingsPage.exportLogs.noLogsYet);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <div className="w-full select-none">
      <div className="w-full flex flex-col gap-4">
          {/* Title */}
          <h2 className="text-xl font-bold text-slate-800 text-center py-2">
            {t.header.settings.title}
          </h2>

          {isLocal() && (
            <SectionCard className="p-5 bg-white border border-slate-200/50 shadow-sm rounded-xl flex flex-col gap-4">
              <p className="text-base font-semibold text-slate-800 m-0">
                {t.settingsPage.targetPath.heading}
              </p>
              
              <div className="flex flex-col gap-2.5 w-full">
                <p className="text-xs text-slate-500 font-normal m-0 leading-relaxed">
                  <span className="text-red-500 font-bold mr-1">*</span>
                  {t.settingsPage.targetPath.description}
                </p>

                <div className="flex items-center gap-2 border border-slate-200 bg-white rounded-lg pl-3 pr-2 py-1.5 focus-within:border-slate-400 focus-within:ring-2 focus-within:ring-slate-100 transition-all w-full">
                  <Folder className="h-4 w-4 text-slate-400 shrink-0" />
                  <input
                    value={path}
                    onChange={(e) => handlePathChange(e.target.value)}
                    className="flex-1 bg-transparent border-0 outline-none text-sm text-slate-900 placeholder:text-muted-foreground min-w-0"
                  />
                  <button
                    onClick={handleBrowse}
                    type="button"
                    className="text-xs font-bold text-[#0d9585] hover:text-[#0b7e70] transition-colors px-2 py-1 focus:outline-none cursor-pointer shrink-0"
                  >
                    {t.settingsPage.targetPath.browse}
                  </button>
                </div>
              </div>

              <div className="flex items-center gap-2 p-1 select-none">
                <Checkbox
                  checked={rememberPath}
                  onCheckedChange={(checked) => setRememberPath(!!checked)}
                  id="remember-path-checkbox"
                />
                <label
                  htmlFor="remember-path-checkbox"
                  className="text-xs font-semibold text-slate-700 cursor-pointer"
                >
                  {t.settingsPage.targetPath.rememberPath}
                </label>
              </div>
            </SectionCard>
          )}

          {isLocal() && (
            <SectionCard className="p-5 bg-white border border-slate-200/50 shadow-sm rounded-xl flex flex-col gap-4">
              <p className="text-base font-semibold text-slate-800 m-0">
                {t.settingsPage.exportLogs.heading}
              </p>
              <p className="text-xs text-slate-500 font-normal m-0 leading-relaxed">
                {t.settingsPage.exportLogs.description}
              </p>
              <Button
                onClick={handleOpenLogs}
                variant="outline"
                className="w-fit border-[#0d9585] text-[#0d9585] hover:bg-[#0d9585]/5 hover:text-[#0d9585]"
              >
                <ScrollText className="h-4 w-4" />
                {t.settingsPage.exportLogs.button}
              </Button>
            </SectionCard>
          )}

          <SectionCard className="p-5 bg-white border border-slate-200/50 shadow-sm rounded-xl flex flex-col gap-4">
            <p className="text-base font-semibold text-slate-800 m-0">
              {t.settingsPage.language.heading}
            </p>
            <p className="text-xs text-slate-500 m-0">
              {t.settingsPage.language.description}
            </p>
            
            <RadioGroup
              value={language}
              onValueChange={(val) => setLanguage(val as Language)}
              className="flex flex-col gap-3 mt-2"
            >
              <div className="flex items-center gap-2">
                <RadioGroupItem value="en" id="lang-en" />
                <Label htmlFor="lang-en" className="text-sm font-semibold text-slate-700 cursor-pointer">
                  {t.settingsPage.language.english}
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="vi" id="lang-vi" />
                <Label htmlFor="lang-vi" className="text-sm font-semibold text-slate-700 cursor-pointer">
                  {t.settingsPage.language.vietnamese}
                </Label>
              </div>
            </RadioGroup>
          </SectionCard>

          <SectionCard className="p-5 bg-white border border-slate-200/50 shadow-sm rounded-xl flex flex-col gap-4">
            <p className="text-base font-semibold text-slate-800 m-0">
              {t.settingsPage.playlistLimit.heading}
            </p>
            <p className="text-xs text-slate-500 m-0">
              {t.settingsPage.playlistLimit.description}
            </p>
            
            <RadioGroup
              value={playlistLimit.toString()}
              onValueChange={(val) => handlePlaylistLimitChange(parseInt(val, 10))}
              className="flex flex-col gap-3 mt-2"
            >
              <div className="flex items-center gap-2">
                <RadioGroupItem value="30" id="limit-30" />
                <Label htmlFor="limit-30" className="text-sm font-semibold text-slate-700 cursor-pointer">
                  {t.settingsPage.playlistLimit.option30}
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="50" id="limit-50" />
                <Label htmlFor="limit-50" className="text-sm font-semibold text-slate-700 cursor-pointer">
                  {t.settingsPage.playlistLimit.option50}
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="100" id="limit-100" />
                <Label htmlFor="limit-100" className="text-sm font-semibold text-slate-700 cursor-pointer">
                  {t.settingsPage.playlistLimit.option100}
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="200" id="limit-200" />
                <Label htmlFor="limit-200" className="text-sm font-semibold text-slate-700 cursor-pointer">
                  {t.settingsPage.playlistLimit.option200}
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="500" id="limit-500" />
                <Label htmlFor="limit-500" className="text-sm font-semibold text-slate-700 cursor-pointer">
                  {t.settingsPage.playlistLimit.option500}
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="0" id="limit-all" />
                <Label htmlFor="limit-all" className="text-sm font-semibold text-slate-700 cursor-pointer">
                  {t.settingsPage.playlistLimit.optionAll}
                </Label>
              </div>
            </RadioGroup>
          </SectionCard>

      </div>
    </div>
  );
};

export default SettingsPage;
