import { theme as antdTheme, type ThemeConfig } from "antd";

export const HEADER_BG = "#ffffff";
export const BRAND_TEXT = "#0d9585";

export const theme: ThemeConfig = {
  algorithm: antdTheme.defaultAlgorithm,
  token: {
    colorPrimary: "#0d9585",
    borderRadius: 12,
    fontFamily:
      "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    colorBgContainer: "#ffffff",
    colorBgLayout: "#f9fafb",
    colorTextBase: "#1f2937",
    colorBorder: "#f0f0f0",
  },
  components: {
    Button: {
      borderRadius: 10,
    },
    Input: {
      borderRadius: 10,
      colorBgContainer: "#ffffff",
    },
    Radio: {
      colorPrimary: "#0d9585",
    },
    Segmented: {
      colorBgContainer: "#f3f4f6",
      colorBgLayout: "#ffffff",
    },
  },
};
