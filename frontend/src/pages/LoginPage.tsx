import { useState } from "react";
import { Eye, EyeOff, Loader2, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Logo from "../components/Logo";
import LanguageSwitcher from "../components/LanguageSwitcher";
import { useLanguage } from "../i18n/LanguageContext";

type UnlockError = "wrong" | "locked" | "network";

// The server owns the trust cookie: we POST the token to /unlock asking for
// JSON, and on success it has already set the cookie, so a plain navigation to
// "/" is all that's left. The token never goes into a URL.
const LoginPage = () => {
  const { t } = useLanguage();
  const [token, setToken] = useState("");
  const [visible, setVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<UnlockError | null>(null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch("/unlock", {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ token }),
        credentials: "include",
      });
      if (response.ok) {
        window.location.assign("/");
        return;
      }
      setError(response.status === 429 ? "locked" : "wrong");
    } catch {
      setError("network");
    } finally {
      setSubmitting(false);
    }
  };

  const toggleVisible = () => setVisible((v) => !v);

  return (
    <div className="flex min-h-svh w-full flex-col items-center justify-center bg-background p-6 md:p-10">
      <div className="w-full max-w-sm md:max-w-4xl">
        <Card className="overflow-hidden bg-white p-0 ">
          <CardContent className="grid p-0 md:grid-cols-2">
            <div className="flex flex-col gap-6 p-6 md:p-8">
              <div className="flex items-center justify-between">
                <Logo />
                <LanguageSwitcher />
              </div>
              <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
                <div className="flex flex-col items-start gap-1.5 text-left">
                  <h1 className="m-0 text-2xl font-bold text-ink">{t.login.title}</h1>
                  <p className="m-0 text-base text-ink-muted">{t.login.subtitle}</p>
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="token">{t.login.label}</Label>
                  <div className="relative">
                    <Input
                      id="token"
                      name="token"
                      type={visible ? "text" : "password"}
                      value={token}
                      onChange={(e) => setToken(e.target.value)}
                      placeholder={t.login.placeholder}
                      autoComplete="current-password"
                      autoCapitalize="none"
                      autoCorrect="off"
                      spellCheck={false}
                      autoFocus
                      aria-invalid={error === "wrong" || undefined}
                      className="pr-10"
                    />
                    <button
                      type="button"
                      onClick={toggleVisible}
                      aria-label={visible ? t.login.hide : t.login.show}
                      className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-ink-muted hover:text-ink"
                    >
                      {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  {error && (
                    <p role="alert" className="m-0 rounded-none border border-destructive bg-invalid px-3 py-2 text-base font-medium text-destructive">
                      {t.login[error]}
                    </p>
                  )}
                </div>
                <Button
                  type="submit"
                  disabled={!token || submitting}
                  className="w-full gap-1.5 rounded-none bg-ink text-on-ink  hover:bg-ink-hover"
                >
                  {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
                  {submitting ? t.login.submitting : t.login.submit}
                </Button>
              </form>
            </div>
            {/* Visual side (login-04's cover image): a brand panel, desktop only. */}
            <div className="relative hidden flex-col justify-end gap-3 overflow-hidden bg-ink p-8 text-on-ink md:flex">
              <div className="absolute -right-16 -top-16 h-64 w-64 rounded-full bg-white/10" />
              <div className="absolute -bottom-20 -left-10 h-56 w-56 rounded-full bg-white/5" />
              <Lock className="relative h-10 w-10 text-on-ink/90" />
              <p className="relative m-0 text-xl font-semibold leading-snug">{t.login.tagline}</p>
              <p className="relative m-0 text-base leading-relaxed text-on-ink/75">{t.login.platforms}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default LoginPage;
