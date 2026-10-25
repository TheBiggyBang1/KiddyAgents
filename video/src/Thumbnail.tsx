import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { colors, fontFamily } from "./theme";
import type { ThumbnailProps } from "./types";

export const Thumbnail: React.FC<ThumbnailProps> = ({ upper, lower, headline, image }) => (
  <AbsoluteFill style={{
    background: `linear-gradient(150deg, ${colors.sky[0]}, ${colors.sky[1]})`,
    flexDirection: "row", alignItems: "center", justifyContent: "space-around", padding: 40,
  }}>
    <div style={{ fontFamily, fontWeight: 700, fontSize: 330, lineHeight: 1, letterSpacing: -10 }}>
      <span style={{ color: colors.upper, WebkitTextStroke: "10px #fff", paintOrder: "stroke" }}>
        {upper}
      </span>
      <span style={{ color: colors.lower, WebkitTextStroke: "10px #fff", paintOrder: "stroke" }}>
        {lower}
      </span>
    </div>
    {image && (
      <div style={{
        width: 470, height: 470, borderRadius: 235, background: colors.card, overflow: "hidden",
        border: "12px solid #fff", boxShadow: "0 18px 40px #3d355333",
      }}>
        <Img src={staticFile(image)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </div>
    )}
    <div style={{
      position: "absolute", top: 34, left: 0, right: 0, textAlign: "center", fontFamily,
      fontWeight: 700, fontSize: 84, color: "#fff", WebkitTextStroke: `14px ${colors.ink}`,
      paintOrder: "stroke",
    }}>
      {headline}
    </div>
  </AbsoluteFill>
);
