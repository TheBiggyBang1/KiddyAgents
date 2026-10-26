// The contract with the Python puppet agents (src/kiddy/puppet/compose.py writes this shape).
// Times are seconds from the start of the video; x is pixels on the 1920-wide stage.

export type CharacterId = "fennel" | "olo" | "glim";
export type Emotion = "happy" | "excited" | "curious" | "surprised" | "sad" | "calm";
export type Action = "wave" | "jump" | "nod" | "point" | "dance" | "think" | "clap" | "spin";
export type Background = "meadow" | "forest" | "pond" | "night" | "garden" | "home";

export type Talk = { start: number; duration: number; mouth: number[] }; // mouth: 0-1 per frame
export type Act = { start: number; duration: number; action: Action };
export type Move = { start: number; duration: number; to: number };
export type Mood = { start: number; emotion: Emotion };

export type Actor = {
  id: CharacterId;
  x: number;
  talks: Talk[];
  acts: Act[];
  moves: Move[];
  moods: Mood[];
};

export type Stage = {
  start: number;
  duration: number;
  background: Background;
  actors: Actor[];
  cards: { start: number; end: number; image: string }[];
  words: { start: number; end: number; text: string }[];
};

export type PuppetProps = {
  title: string;
  intro: number; // seconds of title card before the first stage
  stages: Stage[];
  audio: { src: string; start: number }[];
  captions: { text: string; start: number; end: number }[];
};

export type PuppetThumbnailProps = {
  headline: string;
  background: Background;
  cast: CharacterId[];
  image: string;
};

export const GROUND = 960; // where the puppets' feet touch the stage

export const puppetSeconds = (props: PuppetProps) =>
  Math.max(props.intro, ...props.stages.map((s) => s.start + s.duration));
