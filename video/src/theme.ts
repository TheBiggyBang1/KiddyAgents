import { loadFont } from "@remotion/google-fonts/Fredoka";

export const { fontFamily } = loadFont("normal", { weights: ["500", "700"] });

export const colors = {
  ink: "#3D3553",
  upper: "#FF6B6B",
  lower: "#4D96FF",
  start: "#2EC27E",
  guide: "#C9C9D6",
  topLine: "#8EC5FF",
  midLine: "#FF9AA2",
  card: "#FFFFFF",
  sky: ["#FFF4D6", "#FFE3EC"] as const,
};
