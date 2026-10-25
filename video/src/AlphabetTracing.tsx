import { Audio } from "@remotion/media";
import React from "react";
import { AbsoluteFill, interpolate, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Outro, PracticeScene, TitleCard, TraceScene, WordCard } from "./Scenes";
import { colors, fontFamily } from "./theme";
import { frames, type Segment, type TracingProps } from "./types";

const FADE = 0.3; // seconds each scene fades in and out

export const AlphabetTracing: React.FC<TracingProps> = ({ segments, audio, captions }) => (
  <AbsoluteFill style={{ background: `linear-gradient(160deg, ${colors.sky[0]}, ${colors.sky[1]})` }}>
    <Confetti />
    {segments.map((segment) => (
      <Sequence key={`${segment.kind}-${segment.start}`} from={frames(segment.start)}
        durationInFrames={Math.max(1, frames(segment.duration))}>
        <Fade seconds={segment.duration}>
          <Scene segment={segment} />
        </Fade>
      </Sequence>
    ))}
    {audio.map((clip) => (
      <Sequence key={`${clip.src}-${clip.start}`} from={frames(clip.start)} layout="none">
        <Audio src={staticFile(clip.src)} />
      </Sequence>
    ))}
    <Captions captions={captions} />
  </AbsoluteFill>
);

const Scene: React.FC<{ segment: Segment }> = ({ segment }) => {
  switch (segment.kind) {
    case "title":
      return <TitleCard segment={segment} />;
    case "trace":
      return <TraceScene segment={segment} />;
    case "practice":
      return <PracticeScene segment={segment} />;
    case "word":
      return <WordCard segment={segment} />;
    case "outro":
      return <Outro segment={segment} />;
  }
};

const Fade: React.FC<{ seconds: number; children: React.ReactNode }> = ({ seconds, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const opacity = Math.min(
    interpolate(t, [0, FADE], [0, 1], { extrapolateRight: "clamp" }),
    interpolate(t, [seconds - FADE, seconds], [1, 0], { extrapolateLeft: "clamp" }),
  );
  return <AbsoluteFill style={{ opacity }}>{children}</AbsoluteFill>;
};

const Captions: React.FC<{ captions: TracingProps["captions"] }> = ({ captions }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const now = frame / fps;
  const line = captions.find((c) => now >= c.start && now < c.end);
  if (!line) return null;
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 26 }}>
      <div style={{
        fontFamily, fontWeight: 500, fontSize: 46, color: colors.ink, background: "#ffffffd9",
        padding: "10px 34px", borderRadius: 40,
      }}>
        {line.text}
      </div>
    </AbsoluteFill>
  );
};

// Soft dots in fixed places: a little life in the background, identical in every frame.
const DOTS = Array.from({ length: 18 }, (_, i) => ({
  x: (i * 397) % 1920, y: (i * 211) % 1080, r: 14 + ((i * 7) % 26),
  color: [colors.upper, colors.lower, "#FFC93C", colors.start][i % 4],
}));

const Confetti: React.FC = () => (
  <AbsoluteFill>
    {DOTS.map((dot) => (
      <div key={`${dot.x}-${dot.y}`} style={{
        position: "absolute", left: dot.x, top: dot.y, width: dot.r * 2, height: dot.r * 2,
        borderRadius: dot.r, background: dot.color, opacity: 0.16,
      }} />
    ))}
  </AbsoluteFill>
);
