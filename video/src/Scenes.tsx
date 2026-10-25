import React from "react";
import {
  AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig,
} from "remotion";
import { Board } from "./Board";
import { colors, fontFamily } from "./theme";
import type { Segment } from "./types";

type Of<K extends Segment["kind"]> = Extract<Segment, { kind: K }>;

const text: React.CSSProperties = { fontFamily, color: colors.ink, fontWeight: 700 };

/** Pops in with a spring, starting `delay` frames into the scene. */
const usePop = (delay = 0) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - delay, fps, config: { damping: 12, stiffness: 120 } });
};

export const TitleCard: React.FC<{ segment: Of<"title"> }> = ({ segment }) => {
  const pop = usePop();
  const sub = usePop(12);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", gap: 20 }}>
      <div style={{ ...text, fontSize: 420, lineHeight: 1, transform: `scale(${pop})` }}>
        <span style={{ color: colors.upper }}>{segment.upper}</span>
        <span style={{ color: colors.lower, marginLeft: 40 }}>{segment.lower}</span>
      </div>
      <div style={{ ...text, fontSize: 84, opacity: sub, transform: `translateY(${(1 - sub) * 40}px)` }}>
        Let's trace the letter {segment.upper}!
      </div>
    </AbsoluteFill>
  );
};

export const TraceScene: React.FC<{ segment: Of<"trace"> }> = ({ segment }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const now = segment.start + frame / fps;
  const progress = segment.strokes.map((s) =>
    interpolate(now, [s.start, s.start + s.duration], [0, 1], {
      extrapolateLeft: "clamp", extrapolateRight: "clamp",
    }),
  );
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Board strokes={segment.strokes.map((s) => s.d)} progress={progress} color={segment.color}
        height={880} />
    </AbsoluteFill>
  );
};

export const PracticeScene: React.FC<{ segment: Of<"practice"> }> = ({ segment }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // A see-through crayon keeps tracing the letter, for kids to follow with a finger.
  const loop = (frame / fps) % 3;
  const count = segment.strokes.length;
  const progress = segment.strokes.map((_, i) =>
    interpolate(loop, [(i * 2.4) / count, ((i + 1) * 2.4) / count], [0, 1], {
      extrapolateLeft: "clamp", extrapolateRight: "clamp",
    }),
  );
  const pulse = 1 + 0.06 * Math.sin((frame / fps) * Math.PI * 2);
  return (
    <AbsoluteFill style={{ flexDirection: "row", justifyContent: "center", alignItems: "center", gap: 90 }}>
      <Board strokes={segment.strokes.map((s) => s.d)} progress={progress} color={segment.color}
        height={880} showStart={false} inkOpacity={0.35} />
      <div style={{ ...text, fontSize: 110, textAlign: "center", transform: `scale(${pulse})` }}>
        Your
        <br />
        turn!
      </div>
    </AbsoluteFill>
  );
};

export const WordCard: React.FC<{ segment: Of<"word"> }> = ({ segment }) => {
  const pop = usePop();
  const word = usePop(10);
  const [first, rest] = [segment.word.slice(0, 1), segment.word.slice(1)];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", gap: 30 }}>
      <div style={{
        width: 720, height: 620, borderRadius: 64, background: colors.card, transform: `scale(${pop})`,
        boxShadow: "0 24px 60px #3d355322", display: "flex", justifyContent: "center", alignItems: "center",
      }}>
        {segment.image ? (
          <Img src={staticFile(segment.image)} style={{ width: 620, height: 520, objectFit: "contain" }} />
        ) : (
          <div style={{ width: 360, height: 360, borderRadius: 180, background: colors.sky[1] }} />
        )}
      </div>
      <div style={{ ...text, fontSize: 150, lineHeight: 1, transform: `scale(${word})` }}>
        <span style={{ color: colors.upper }}>{first}</span>
        {rest}
      </div>
    </AbsoluteFill>
  );
};

export const Outro: React.FC<{ segment: Of<"outro"> }> = ({ segment }) => {
  const frame = useCurrentFrame();
  const pop = usePop();
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", gap: 10 }}>
      {Array.from({ length: 14 }, (_, i) => {
        const angle = (i / 14) * Math.PI * 2;
        const distance = interpolate(frame, [0, 40], [0, 560], { extrapolateRight: "clamp" });
        return (
          <div key={i} style={{
            position: "absolute", fontSize: 80, color: i % 2 ? colors.upper : "#FFC93C",
            transform: `translate(${Math.cos(angle) * distance}px, ${Math.sin(angle) * distance * 0.6}px) rotate(${frame * 4}deg)`,
          }}>
            ★
          </div>
        );
      })}
      <div style={{ ...text, fontSize: 190, transform: `scale(${pop})` }}>Great job!</div>
      <div style={{ ...text, fontSize: 160, opacity: pop }}>
        <span style={{ color: colors.upper }}>{segment.upper}</span>
        <span style={{ color: colors.lower, marginLeft: 30 }}>{segment.lower}</span>
      </div>
    </AbsoluteFill>
  );
};
