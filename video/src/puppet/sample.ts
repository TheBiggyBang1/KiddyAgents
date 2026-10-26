import type { PuppetProps, PuppetThumbnailProps } from "./types";

// What `remotion studio` shows before any props.json exists: every puppet talking and acting.
const chatter = (seconds: number) =>
  Array.from({ length: Math.round(seconds * 30) }, (_, i) => Math.abs(Math.sin(i / 2.3)) * 0.9);

export const samplePuppetShow: PuppetProps = {
  title: "Why Do We Brush Our Teeth?",
  intro: 2.5,
  stages: [
    {
      start: 2.5, duration: 9, background: "meadow",
      actors: [
        { id: "fennel", x: 520, talks: [{ start: 3, duration: 2.5, mouth: chatter(2.5) }],
          acts: [{ start: 3, duration: 1.4, action: "wave" }], moves: [], moods: [{ start: 2.5, emotion: "excited" }] },
        { id: "olo", x: 960, talks: [{ start: 6, duration: 2.5, mouth: chatter(2.5) }],
          acts: [{ start: 8.8, duration: 1.2, action: "nod" }], moves: [], moods: [{ start: 2.5, emotion: "calm" }] },
        { id: "glim", x: 1400, talks: [], acts: [{ start: 9, duration: 1.4, action: "jump" }],
          moves: [], moods: [{ start: 2.5, emotion: "curious" }] },
      ],
      cards: [],
      words: [{ start: 9, end: 11, text: "Brush!" }],
    },
  ],
  audio: [],
  captions: [{ text: "Good morning, friends!", start: 3, end: 5.5 }],
};

export const samplePuppetThumbnail: PuppetThumbnailProps = {
  headline: "Why Do We Brush Our Teeth?", background: "home", cast: ["fennel", "olo", "glim"], image: "",
};
