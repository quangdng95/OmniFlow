import logoIcon from "../assets/logo-icon.svg";

interface LogoProps {
  size?: "large" | "small";
}

const Logo = ({ size = "large" }: LogoProps) => {
  if (size === "small") {
    return (
      <div className="flex items-center gap-[4.17px] shrink-0 select-none">
        <img src={logoIcon} alt="Logo" width={32} height={32} className="h-8 w-8 shrink-0" />
        <div className="text-slate-700 leading-none shrink-0 flex flex-col items-start">
          <div className="text-[16.7px] font-medium font-sans">OmniFlow</div>
          <div className="text-[8.35px] font-normal font-sans">Video Downloader</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-[6px] justify-center select-none">
      <img src={logoIcon} alt="Logo" width={46} height={46} className="h-[46px] w-[46px] shrink-0" />
      <div className="text-[#334155] leading-none flex flex-col items-start">
        <div className="text-[24px] font-medium font-sans tracking-wide">OmniFlow</div>
        <div className="text-[12px] font-normal text-muted-foreground mt-0.5">Video Downloader</div>
      </div>
    </div>
  );
};

export default Logo;
