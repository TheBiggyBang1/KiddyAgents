import { evolvePath, getLength, getPointAtLength } from "@remotion/paths";
import React from "react";
import { colors, fontFamily } from "./theme";

// Letters live on a grid: x 0-100; y 0 top line, 50 middle line, 100 baseline, 140 descender.
const VIEW = { x: -35, y: -25, width: 170, height: 190 };
const STROKE = 10;

type BoardProps = {
  strokes: string[];
  progress: number[]; // 0..1 per stroke: how much of it has been drawn
  color: string;
  height: number;
  showStart?: boolean; // the green numbered dot where the next stroke begins
  inkOpacity?: number;
};

export const Board: React.FC<BoardProps> = ({
  strokes, progress, color, height, showStart = true, inkOpacity = 1,
}) => {
  const active = progress.findIndex((p) => p < 1);
  const width = (height * VIEW.width) / VIEW.height;
  return (
    <svg
      width={width}
      height={height}
      viewBox={`${VIEW.x} ${VIEW.y} ${VIEW.width} ${VIEW.height}`}
      style={{ background: colors.card, borderRadius: 48, boxShadow: "0 24px 60px #3d355322" }}
    >
      <WritingLines />
      {strokes.map((d) => (
        // A dotted guide: zero-length dashes with round caps draw as dots.
        <path key={`guide-${d}`} d={d} fill="none" stroke={colors.guide} strokeWidth={STROKE}
          strokeLinecap="round" strokeDasharray="0.1 7" />
      ))}
      {strokes.map((d, i) => {
        if (progress[i] <= 0) return null;
        const { strokeDasharray, strokeDashoffset } = evolvePath(progress[i], d);
        return (
          <path key={`ink-${d}`} d={d} fill="none" stroke={color} strokeWidth={STROKE}
            strokeLinecap="round" strokeLinejoin="round" opacity={inkOpacity}
            strokeDasharray={progress[i] < 1 ? strokeDasharray : undefined}
            strokeDashoffset={progress[i] < 1 ? strokeDashoffset : undefined} />
        );
      })}
      {active >= 0 && showStart && <StartDot d={strokes[active]} number={active + 1} />}
      {active >= 0 && progress[active] > 0 && (
        <Crayon d={strokes[active]} progress={progress[active]} color={color} />
      )}
    </svg>
  );
};

const WritingLines: React.FC = () => (
  <g strokeWidth={1.6}>
    <line x1={-30} x2={130} y1={0} y2={0} stroke={colors.topLine} />
    <line x1={-30} x2={130} y1={50} y2={50} stroke={colors.midLine} strokeDasharray="5 4" />
    <line x1={-30} x2={130} y1={100} y2={100} stroke={colors.topLine} />
    <line x1={-30} x2={130} y1={140} y2={140} stroke={colors.guide} strokeDasharray="2 4" />
  </g>
);

const StartDot: React.FC<{ d: string; number: number }> = ({ d, number }) => {
  const point = getPointAtLength(d, 0);
  if (!point) return null;
  const { x, y } = point;
  return (
    <g>
      <circle cx={x} cy={y} r={8} fill={colors.start} stroke="#fff" strokeWidth={2} />
      <text x={x} y={y + 3.6} fontSize={10} fontWeight={700} textAnchor="middle" fill="#fff"
        fontFamily={fontFamily}>
        {number}
      </text>
    </g>
  );
};

const Crayon: React.FC<{ d: string; progress: number; color: string }> = ({ d, progress, color }) => {
  const point = getPointAtLength(d, getLength(d) * Math.min(progress, 1));
  if (!point) return null;
  return <circle cx={point.x} cy={point.y} r={7.5} fill={color} stroke="#fff" strokeWidth={2.5} />;
};
