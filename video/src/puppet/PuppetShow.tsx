import { Audio } from "@remotion/media";
import React from "react";
import {
  AbsoluteFill, Easing, Img, interpolate, Sequence, spring, staticFile, useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { colors, fontFamily } from "../theme";
import { frames } from "../types";
import { StageBackground } from "./backgrounds";
import { Puppet, type Pose } from "./characters";
import { type Actor, GROUND, type PuppetProps, type Stage } from "./types";

const FADE = 0.35;
const SCALE = 1.3; // puppets fill the lower half of the stage
const IDLE: Omit<Pose, "t"> = {
  mouth: 0, blink: 0, emotion: "happy", look: 0, armL: 12, armR: 12, lift: 0, tilt: 0,
  headTilt: 0, squash: 1, facing: 1,
};

export const PuppetShow: React.FC<PuppetProps> = ({ title, intro, stages, audio, captions }) => (
  <AbsoluteFill style={{ background: colors.sky[0] }}>
    <Sequence durationInFrames={Math.max(1, frames(intro))}>
      <TitleCard title={title} seconds={intro} />
    </Sequence>
    {stages.map((stage) => (
      <Sequence key={stage.start} from={frames(stage.start)}
        durationInFrames={Math.max(1, frames(stage.duration))}>
        <StageView stage={stage} />
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

const StageView: React.FC<{ stage: Stage }> = ({ stage }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const local = frame / fps;
  const now = stage.start + local;
  const opacity = Math.min(
    interpolate(local, [0, FADE], [0, 1], { extrapolateRight: "clamp" }),
    interpolate(local, [stage.duration - FADE, stage.duration], [1, 0], { extrapolateLeft: "clamp" }),
  );
  const speaker = stage.actors.find((a) => a.talks.some((t) => now >= t.start && now < t.start + t.duration));
  const card = stage.cards.find((c) => now >= c.start && now < c.end);
  const word = stage.words.find((w) => now >= w.start && now < w.end);
  return (
    <AbsoluteFill style={{ opacity }}>
      <svg width={1920} height={1080} viewBox="0 0 1920 1080">
        <StageBackground kind={stage.background} t={now} />
        {stage.actors.map((actor, i) => {
          const { x, pose } = perform(actor, now, fps, i, speaker);
          return <Puppet key={actor.id} id={actor.id} x={x} ground={GROUND} pose={pose} scale={SCALE} />;
        })}
      </svg>
      {card && <CardFrame image={card.image} since={now - card.start} />}
      {word && <BigWord text={word.text} since={now - word.start} />}
    </AbsoluteFill>
  );
};

/** Where an actor stands and how it moves at time `now`: walks, talks, acts, blinks, breathes. */
export const perform = (actor: Actor, now: number, fps: number, index: number, speaker?: Actor) => {
  let x = actor.x;
  let walking = 0;
  let facing: 1 | -1 = 1;
  for (const move of actor.moves) {
    if (now < move.start) break;
    const p = Math.min(1, (now - move.start) / move.duration);
    const from = x;
    x = interpolate(p, [0, 1], [from, move.to], { easing: Easing.inOut(Easing.quad) });
    if (p < 1) {
      walking = p;
      facing = move.to < from ? -1 : 1;
    }
  }
  const talk = actor.talks.find((t) => now >= t.start && now < t.start + t.duration);
  const mouth = talk ? (talk.mouth[Math.floor((now - talk.start) * fps)] ?? 0) : 0;
  const mood = [...actor.moods].reverse().find((m) => now >= m.start);
  const phase = (now + index * 1.3) % 3.7; // each puppet blinks on its own rhythm
  const blink = phase < 0.14 ? 1 - Math.abs(phase - 0.07) / 0.07 : 0;
  const look = speaker && speaker !== actor
    ? Math.max(-1, Math.min(1, (speaker.x - actor.x) / 500)) : 0;

  const pose: Pose = {
    ...IDLE, t: now + index, mouth, blink, look, facing,
    emotion: mood?.emotion ?? "happy",
    lift: walking > 0 ? Math.abs(Math.sin(walking * Math.PI * 6)) * 16 : 0,
    tilt: Math.sin((now + index) * 1.7) * 1.5 + (talk ? Math.sin(now * 9) * mouth * 2 : 0),
    headTilt: talk ? Math.sin(now * 5) * 4 * mouth : Math.sin((now + index) * 0.9) * 2,
  };
  const act = actor.acts.find((a) => now >= a.start && now < a.start + a.duration);
  if (act) Object.assign(pose, gesture(act.action, (now - act.start) / act.duration, now));
  return { x, pose };
};

/** The pose changes for one action at progress p (0 to 1). */
const gesture = (action: string, p: number, now: number): Partial<Pose> => {
  const wave = Math.sin(now * 14);
  switch (action) {
    case "wave":
      return { armR: 150 + wave * 22 };
    case "jump":
      return p < 0.15 ? { squash: 0.88 } : { lift: Math.sin(((p - 0.15) / 0.85) * Math.PI) * 130, armL: 140, armR: 140 };
    case "nod":
      return { headTilt: 0, lift: 0, tilt: Math.sin(p * Math.PI * 4) * 3 };
    case "point":
      return { armR: 100 };
    case "dance":
      return { tilt: Math.sin(p * Math.PI * 6) * 10, lift: Math.abs(Math.sin(p * Math.PI * 6)) * 24, armL: 120 + wave * 20, armR: 120 - wave * 20 };
    case "think":
      return { armR: 150, headTilt: 10, look: 0.6 };
    case "clap":
      return { armL: 70 + Math.abs(wave) * 30, armR: 70 + Math.abs(wave) * 30 };
    case "spin":
      return { facing: Math.cos(p * Math.PI * 2) >= 0 ? 1 : -1, lift: Math.sin(p * Math.PI) * 30 };
    default:
      return {};
  }
};

const CardFrame: React.FC<{ image: string; since: number }> = ({ image, since }) => {
  const { fps } = useVideoConfig();
  const pop = spring({ frame: Math.round(since * fps), fps, config: { damping: 13, stiffness: 140 } });
  return (
    <AbsoluteFill style={{ alignItems: "center", paddingTop: 50 }}>
      <div style={{
        width: 620, height: 470, borderRadius: 36, background: "#fff", border: "16px solid #FFC93C",
        boxShadow: "0 18px 40px #2e243333", transform: `scale(${pop}) rotate(${(1 - pop) * -6}deg)`,
        overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <Img src={staticFile(image)} style={{ width: "100%", height: "100%", objectFit: "contain" }} />
      </div>
    </AbsoluteFill>
  );
};

const BigWord: React.FC<{ text: string; since: number }> = ({ text, since }) => {
  const { fps } = useVideoConfig();
  const pop = spring({ frame: Math.round(since * fps), fps, config: { damping: 10, stiffness: 150 } });
  const palette = [colors.upper, colors.lower, "#FFB703", colors.start];
  return (
    <AbsoluteFill style={{ alignItems: "center", paddingTop: 150 }}>
      <div style={{ fontFamily, fontWeight: 700, fontSize: 190, transform: `scale(${pop})`,
        WebkitTextStroke: "14px #fff", paintOrder: "stroke" }}>
        {[...text].map((ch, i) => (
          <span key={`${ch}-${i}`} style={{ color: palette[i % palette.length] }}>{ch}</span>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const TitleCard: React.FC<{ title: string; seconds: number }> = ({ title, seconds }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame, fps, config: { damping: 12, stiffness: 110 } });
  const out = interpolate(frame / fps, [seconds - FADE, seconds], [1, 0], { extrapolateLeft: "clamp" });
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <svg width={1920} height={1080}><StageBackground kind="meadow" t={frame / fps} /></svg>
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div style={{ fontFamily, fontWeight: 700, fontSize: 120, color: colors.ink, textAlign: "center",
          maxWidth: 1500, lineHeight: 1.1, transform: `scale(${pop})`, WebkitTextStroke: "16px #fff",
          paintOrder: "stroke" }}>
          {title}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const Captions: React.FC<{ captions: PuppetProps["captions"] }> = ({ captions }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const now = frame / fps;
  const line = captions.find((c) => now >= c.start && now < c.end);
  if (!line) return null;
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 22 }}>
      <div style={{ fontFamily, fontWeight: 500, fontSize: 42, color: colors.ink, background: "#ffffffd9",
        padding: "8px 30px", borderRadius: 36, maxWidth: 1600, textAlign: "center" }}>
        {line.text}
      </div>
    </AbsoluteFill>
  );
};
