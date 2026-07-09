import logoIcon from "../assets/logo-icon.svg";

interface LogoProps {
  size?: "large" | "small";
}

const Logo = ({ size = "large" }: LogoProps) => {
  if (size === "small") {
    return (
      <div className="flex items-center gap-[2px] shrink-0 select-none">
        <img src={logoIcon} alt="Logo" width={16} height={16} className="h-4 w-4 shrink-0" />
        <div className="text-[#0d9585] leading-none shrink-0">
          <div className="text-[8.35px] font-semibold">OmniFlow</div>
          <div className="text-[4.17px] text-muted-foreground">Video Downloader</div>
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
