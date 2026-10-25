import React from "react";
import { AbsoluteFill } from "remotion";
import letters from "../../src/kiddy/tracing/letters.json";
import { Board } from "./Board";
import { colors } from "./theme";

type Library = Record<string, { d: string; say: string }[] | string>;

// A still of every letter fully traced: the quick way to eyeball the stroke library.
export const LetterSheet: React.FC = () => {
  const glyphs = Object.entries(letters as Library).filter(
    (entry): entry is [string, { d: string; say: string }[]] => typeof entry[1] !== "string",
  );
  return (
    <AbsoluteFill style={{ background: colors.sky[0], flexDirection: "row", flexWrap: "wrap",
      alignContent: "flex-start", gap: 12, padding: 12 }}>
      {glyphs.map(([char, strokes]) => (
        <Board key={char} strokes={strokes.map((s) => s.d)} progress={strokes.map(() => 1)}
          color={char === char.toUpperCase() ? colors.upper : colors.lower} height={240}
          showStart={false} />
      ))}
    </AbsoluteFill>
  );
};
