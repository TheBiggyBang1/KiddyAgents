import React from "react";
import { Composition, Still } from "remotion";
import { AlphabetTracing } from "./AlphabetTracing";
import { LetterSheet } from "./LetterSheet";
import { PuppetShow } from "./puppet/PuppetShow";
import { PuppetThumbnail } from "./puppet/PuppetThumbnail";
import { samplePuppetShow, samplePuppetThumbnail } from "./puppet/sample";
import { puppetSeconds } from "./puppet/types";
import { Thumbnail } from "./Thumbnail";
import { FPS, frames, totalSeconds, type ThumbnailProps, type TracingProps } from "./types";

// What `remotion studio` shows before any props.json exists: letter A, no sound or pictures.
const sample: TracingProps = {
  letter: "A",
  title: "Trace the Letter A",
  segments: [
    { kind: "title", start: 0, duration: 3, upper: "A", lower: "a" },
    {
      kind: "trace", start: 3, duration: 8, glyph: "A", color: "#FF6B6B",
      strokes: [
        { d: "M50 0 L15 100", start: 4, duration: 1.5 },
        { d: "M50 0 L85 100", start: 6, duration: 1.5 },
        { d: "M30 60 L70 60", start: 8.2, duration: 1.2 },
      ],
    },
    {
      kind: "practice", start: 11, duration: 5, glyph: "A", color: "#FF6B6B",
      strokes: [{ d: "M50 0 L15 100" }, { d: "M50 0 L85 100" }, { d: "M30 60 L70 60" }],
    },
    { kind: "word", start: 16, duration: 3, word: "Apple", image: "", letter: "A" },
    { kind: "outro", start: 19, duration: 3, upper: "A", lower: "a" },
  ],
  audio: [],
  captions: [{ text: "Slant down to the left.", start: 4, end: 5.5 }],
};

const sampleThumbnail: ThumbnailProps = { upper: "A", lower: "a", headline: "Trace the Letter A!", image: "" };

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="AlphabetTracing"
      component={AlphabetTracing}
      fps={FPS}
      width={1920}
      height={1080}
      durationInFrames={frames(totalSeconds(sample))}
      defaultProps={sample}
      calculateMetadata={({ props }) => ({ durationInFrames: frames(totalSeconds(props)) })}
    />
    <Still id="Thumbnail" component={Thumbnail} width={1280} height={720}
      defaultProps={sampleThumbnail} />
    <Still id="LetterSheet" component={LetterSheet} width={2216} height={1530} />
    <Composition
      id="PuppetShow"
      component={PuppetShow}
      fps={FPS}
      width={1920}
      height={1080}
      durationInFrames={frames(puppetSeconds(samplePuppetShow))}
      defaultProps={samplePuppetShow}
      calculateMetadata={({ props }) => ({ durationInFrames: frames(puppetSeconds(props)) })}
    />
    <Still id="PuppetThumbnail" component={PuppetThumbnail} width={1280} height={720}
      defaultProps={samplePuppetThumbnail} />
  </>
);
