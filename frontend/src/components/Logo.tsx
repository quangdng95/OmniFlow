import logoIcon from "../assets/logo-icon.svg";
import { BRAND_TEXT } from "../theme";

interface LogoProps {
  size?: "large" | "small";
}

const Logo = ({ size = "large" }: LogoProps) => {
  if (size === "small") {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 2 }}>
        <img src={logoIcon} alt="" width={16} height={16} />
        <div style={{ color: BRAND_TEXT, lineHeight: "normal" }}>
          <div style={{ fontSize: 8.35, fontWeight: 600 }}>OmniFlow</div>
          <div style={{ fontSize: 4.17 }}>Video Downloader</div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <img src={logoIcon} alt="" width={46} height={46} />
      <div style={{ color: "white", lineHeight: "normal" }}>
        <div style={{ fontSize: 24 }}>OmniFlow</div>
        <div style={{ fontSize: 12 }}>Video Downloader</div>
      </div>
    </div>
  );
};

export default Logo;
