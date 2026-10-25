// The contract with the Python agents: they write props.json in this shape, Remotion renders it.
// All times are in seconds from the start of the video; paths are relative to --public-dir.

export type TimedStroke = { d: string; start: number; duration: number };

export type Segment =
  | { kind: "title"; start: number; duration: number; upper: string; lower: string }
  | {
      kind: "trace";
      start: number;
      duration: number;
      glyph: string;
      color: string;
      strokes: TimedStroke[];
    }
  | {
      kind: "practice";
      start: number;
      duration: number;
      glyph: string;
      color: string;
      strokes: { d: string }[];
    }
  | { kind: "word"; start: number; duration: number; word: string; image: string; letter: string }
  | { kind: "outro"; start: number; duration: number; upper: string; lower: string };

export type TracingProps = {
  letter: string;
  title: string;
  segments: Segment[];
  audio: { src: string; start: number }[];
  captions: { text: string; start: number; end: number }[];
};

export type ThumbnailProps = { upper: string; lower: string; headline: string; image: string };

export const FPS = 30;
export const frames = (seconds: number) => Math.round(seconds * FPS);
export const totalSeconds = (props: TracingProps) =>
  Math.max(1, ...props.segments.map((s) => s.start + s.duration));
