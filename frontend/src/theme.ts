import { theme as antdTheme, type ThemeConfig } from "antd";

export const HEADER_BG = "linear-gradient(135deg, #090d16, #111827, #1e1b4b)";
export const BRAND_TEXT = "#0d9585";

export const theme: ThemeConfig = {
  algorithm: antdTheme.darkAlgorithm,
  token: {
    colorPrimary: "#0d9585",
    borderRadius: 12,
    fontFamily:
      "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    colorBgContainer: "#111827",
    colorBgLayout: "#090d16",
    colorTextBase: "#f3f4f6",
    colorBorder: "rgba(255, 255, 255, 0.08)",
  },
  components: {
    Button: {
      borderRadius: 10,
    },
    Input: {
      borderRadius: 10,
      colorBgContainer: "#1f2937",
    },
    Radio: {
      colorPrimary: "#0d9585",
    },
    Segmented: {
      colorBgContainer: "#1f2937",
      colorBgLayout: "#111827",
    },
  },
};
