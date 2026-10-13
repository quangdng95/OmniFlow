import logoIcon from "../assets/logo-icon.svg";

interface LogoProps {
  size?: "compact" | "small";
}

const Logo = ({ size = "compact" }: LogoProps) => {
  if (size === "small") {
    return (
      <div className="flex items-center gap-2 shrink-0">
        <img src={logoIcon} alt="ViDrop" width={32} height={32} className="h-8 w-8 shrink-0" />
        <span className="font-display text-xl leading-none font-bold tracking-[-0.04em] text-ink uppercase">ViDrop</span>
      </div>
    );
  }

  // "compact": the header logo, half the old 46px "large" one. The old
  // "Video Downloader" tagline would be 6px at half size - unreadable - so it
  // is dropped here (the page's own heading already says what the app is).
  return (
    <div className="flex items-center gap-2">
      <img src={logoIcon} alt="ViDrop" width={23} height={23} className="h-[23px] w-[23px] shrink-0" />
      <span className="font-display text-[1.625rem] leading-none font-bold tracking-[-0.04em] text-ink uppercase">
        Vi
        <span className="ml-0.5 bg-ink px-1.5 text-signal">drop</span>
      </span>
    </div>
  );
};

export default Logo;
