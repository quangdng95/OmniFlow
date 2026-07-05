import { useEffect, useState } from "react";
import { Button, Checkbox, Input, Radio } from "antd";
import { FolderOutlined } from "@ant-design/icons";
import Header, { type Page } from "../components/Header";
import Footer from "../components/Footer";
import SectionCard from "../components/SectionCard";
import { api } from "../api";
import { useLanguage } from "../i18n/LanguageContext";
import type { Language } from "../i18n/translations";
import type { CookiesStatus } from "../types";
import { isLocal } from "../isLocal";

interface SettingsPageProps {
  onNavigate: (page: Page) => void;
}

const SettingsPage = ({ onNavigate }: SettingsPageProps) => {
  const { t, language, setLanguage } = useLanguage();
  const [path, setPath] = useState("");
  const [rememberPath, setRememberPath] = useState(true);
  const [cookiesPath, setCookiesPath] = useState("");
  const [cookiesStatus, setCookiesStatus] = useState<CookiesStatus>("none");

  useEffect(() => {
    void api.getSettings().then((settings) => {
      setPath(settings.path);
      setCookiesPath(settings.cookies_path);
      setCookiesStatus(settings.cookies_status);
    });
  }, []);

  const handleBrowse = async () => {
    try {
      const { path: chosen } = await api.browseFolder();
      setPath(chosen);
      await api.updateSettings({ path: chosen });
    } catch {
      // user cancelled the folder picker
    }
  };

  const handleBrowseCookiesFile = async () => {
    try {
      const { path: chosen, cookies_status } = await api.browseFile();
      setCookiesPath(chosen);
      setCookiesStatus(cookies_status);
      await api.updateSettings({ cookies_path: chosen });
    } catch {
      // user cancelled the file picker
    }
  };

  const handleClearCookiesFile = async () => {
    setCookiesPath("");
    setCookiesStatus("none");
    await api.updateSettings({ cookies_path: "" });
  };

  return (
    <>
      <Header active="settings" onNavigate={onNavigate} />
      <div className="omniflow-content">
        <div className="omniflow-content-inner">
          {isLocal() && (
            <SectionCard>
              <p style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>{t.settingsPage.targetPath.heading}</p>
              <div style={{ width: "100%" }}>
                <div style={{ fontSize: 14, marginBottom: 4 }}>
                  <span style={{ color: "#ff4d4f" }}>*</span> {t.settingsPage.targetPath.description}
                </div>
                <Input
                  value={path}
                  onChange={(e) => setPath(e.target.value)}
                  onBlur={() => void api.updateSettings({ path })}
                  suffix={
                    <Button type="primary" size="small" icon={<FolderOutlined />} onClick={handleBrowse}>
                      {t.settingsPage.targetPath.browse}
                    </Button>
                  }
                />
              </div>
              <Checkbox checked={rememberPath} onChange={(e) => setRememberPath(e.target.checked)}>
                {t.settingsPage.targetPath.rememberPath}
              </Checkbox>
            </SectionCard>
          )}

          {isLocal() && (
            <SectionCard>
              <p style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>{t.settingsPage.cookies.heading}</p>
              <p style={{ fontSize: 14, margin: 0 }}>{t.settingsPage.cookies.description}</p>
              <div style={{ width: "100%" }}>
                <Input
                  value={cookiesPath}
                  placeholder={t.settingsPage.cookies.noneSelected}
                  readOnly
                  suffix={
                    <Button type="primary" size="small" icon={<FolderOutlined />} onClick={handleBrowseCookiesFile}>
                      {t.settingsPage.cookies.browse}
                    </Button>
                  }
                />
              </div>
              {cookiesStatus === "valid" && (
                <p style={{ fontSize: 13, margin: 0, color: "#52c41a" }}>{t.settingsPage.cookies.statusValid}</p>
              )}
              {cookiesStatus === "no_session" && (
                <p style={{ fontSize: 13, margin: 0, color: "#faad14" }}>{t.settingsPage.cookies.statusNoSession}</p>
              )}
              {cookiesPath && (
                <Button size="small" onClick={handleClearCookiesFile}>
                  {t.settingsPage.cookies.clear}
                </Button>
              )}
            </SectionCard>
          )}

          <SectionCard>
            <p style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>{t.settingsPage.language.heading}</p>
            <p style={{ fontSize: 14, margin: 0 }}>{t.settingsPage.language.description}</p>
            <Radio.Group value={language} onChange={(e) => setLanguage(e.target.value as Language)}>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <Radio value="en">{t.settingsPage.language.english}</Radio>
                <Radio value="vi">{t.settingsPage.language.vietnamese}</Radio>
              </div>
            </Radio.Group>
          </SectionCard>

          <Footer />
        </div>
      </div>
    </>
  );
};

export default SettingsPage;
