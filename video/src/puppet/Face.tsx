import React from "react";
import type { Emotion } from "./types";

const INK = "#2E2433";

export type FaceProps = {
  mouth: number; // 0 closed .. 1 wide open
  blink: number; // 0 open .. 1 closed
  emotion: Emotion;
  look: number; // -1 left .. 1 right
  eyeGap?: number;
  eyeY?: number;
  mouthY?: number;
  size?: number;
};

/** Eyes, brows and mouth, drawn around (0, 0): shared by every puppet. */
export const Face: React.FC<FaceProps> = ({
  mouth, blink, emotion, look, eyeGap = 30, eyeY = -8, mouthY = 34, size = 1,
}) => {
  const eyeHeight = 15 * (1 - 0.9 * blink);
  const pupil = look * 4;
  const brow = {
    happy: [0, 0], excited: [-6, -6], curious: [-8, 0], surprised: [-10, -10],
    sad: [4, 4], calm: [0, 0],
  }[emotion];
  const browTilt = emotion === "sad" ? 14 : emotion === "excited" ? -6 : 0;
  // A closed mouth still shows the mood; talking opens it from there.
  const open = Math.max(mouth, emotion === "excited" ? 0.25 : emotion === "surprised" ? 0.35 : 0);
  return (
    <g transform={`scale(${size})`}>
      {[-1, 1].map((side) => (
        <g key={side} transform={`translate(${side * eyeGap}, ${eyeY})`}>
          <ellipse rx={11} ry={eyeHeight} fill={INK} />
          {blink < 0.5 && <circle cx={pupil + 3} cy={-5} r={3.6} fill="#fff" />}
          <line
            x1={-10} x2={10} y1={-26 + brow[side < 0 ? 0 : 1]}
            y2={-26 + brow[side < 0 ? 0 : 1] + side * browTilt * -0.3}
            stroke={INK} strokeWidth={4} strokeLinecap="round"
            transform={`rotate(${side * browTilt}, 0, -26)`}
          />
        </g>
      ))}
      <g transform={`translate(0, ${mouthY})`}>
        {open > 0.06 ? (
          <g>
            <ellipse rx={10 + 4 * open} ry={3 + 15 * open} fill="#7A2633" />
            <ellipse cy={2 + 9 * open} rx={6 + 2 * open} ry={2 + 5 * open} fill="#F28B9B" />
          </g>
        ) : emotion === "sad" ? (
          <path d="M-13 6 Q0 -4 13 6" stroke={INK} strokeWidth={4} fill="none" strokeLinecap="round" />
        ) : (
          <path d="M-14 0 Q0 11 14 0" stroke={INK} strokeWidth={4} fill="none" strokeLinecap="round" />
        )}
      </g>
    </g>
  );
};
