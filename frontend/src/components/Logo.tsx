import logoIcon from "../assets/logo-icon.svg";

interface LogoProps {
  size?: "compact" | "small";
}

const Logo = ({ size = "compact" }: LogoProps) => {
  if (size === "small") {
    return (
      <div className="flex items-center gap-[4.17px] shrink-0 select-none">
        <img src={logoIcon} alt="Logo" width={32} height={32} className="h-8 w-8 shrink-0" />
        <div className="text-slate-700 leading-none shrink-0 flex flex-col items-start">
          <div className="text-[16.7px] font-medium font-sans">Vidrop</div>
          <div className="text-[8.35px] font-normal font-sans">Video Downloader</div>
        </div>
      </div>
    );
  }

  // "compact": the header logo, half the old 46px "large" one. The old
  // "Video Downloader" tagline would be 6px at half size - unreadable - so it
  // is dropped here (the page's own heading already says what the app is).
  return (
    <div className="flex items-center gap-1.5 select-none">
      <img src={logoIcon} alt="Logo" width={23} height={23} className="h-[23px] w-[23px] shrink-0" />
      <span className="text-[#334155] leading-none text-[14px] font-medium font-sans tracking-wide">Vidrop</span>
    </div>
  );
};

export default Logo;
