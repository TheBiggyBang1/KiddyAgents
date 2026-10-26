import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { colors, fontFamily } from "../theme";
import { StageBackground } from "./backgrounds";
import { Puppet, type Pose } from "./characters";
import type { PuppetThumbnailProps } from "./types";

const HAPPY: Pose = {
  mouth: 0.45, blink: 0, emotion: "excited", look: 0, armL: 20, armR: 150, lift: 0, tilt: 0,
  headTilt: 4, squash: 1, facing: 1, t: 0.6,
};

export const PuppetThumbnail: React.FC<PuppetThumbnailProps> = ({ headline, background, cast, image }) => (
  <AbsoluteFill>
    <svg width={1280} height={720} viewBox="160 90 1600 900">
      <StageBackground kind={background} t={0} />
      {cast.slice(0, 3).map((id, i) => (
        <Puppet key={id} id={id} x={image ? 420 + i * 270 : 560 + i * 400} ground={980}
          pose={{ ...HAPPY, t: i }} scale={1.3} />
      ))}
    </svg>
    {image && (
      <div style={{ position: "absolute", right: 60, top: 160, width: 400, height: 400, borderRadius: 40,
        background: "#fff", border: "14px solid #FFC93C", overflow: "hidden" }}>
        <Img src={staticFile(image)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </div>
    )}
    <div style={{ position: "absolute", top: 26, left: 30, right: 30, textAlign: "center", fontFamily,
      fontWeight: 700, fontSize: 86, lineHeight: 1.05, color: "#fff", WebkitTextStroke: `14px ${colors.ink}`,
      paintOrder: "stroke" }}>
      {headline}
    </div>
  </AbsoluteFill>
);
