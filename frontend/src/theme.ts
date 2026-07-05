import type { ThemeConfig } from "antd";

export const HEADER_BG = "#13493c";
export const BRAND_TEXT = "#207661";

export const theme: ThemeConfig = {
  token: {
    colorPrimary: "#0d9585",
    borderRadius: 8,
    fontFamily:
      "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  },
  components: {
    Button: {
      borderRadius: 8,
    },
    Input: {
      borderRadius: 8,
    },
    Radio: {
      colorPrimary: "#1677ff",
    },
  },
};
