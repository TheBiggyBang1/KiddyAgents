import React from "react";
import type { Background } from "./types";

// Every stage is 1920x1080 with the ground at y = 960 (see GROUND in types.ts).

const Sky: React.FC<{ id: string; top: string; bottom: string }> = ({ id, top, bottom }) => (
  <>
    <defs>
      <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor={top} />
        <stop offset="1" stopColor={bottom} />
      </linearGradient>
    </defs>
    <rect width={1920} height={1080} fill={`url(#${id})`} />
  </>
);

const Cloud: React.FC<{ x: number; y: number; s: number }> = ({ x, y, s }) => (
  <g transform={`translate(${x}, ${y}) scale(${s})`} fill="#fff" opacity={0.92}>
    <circle cx={0} cy={0} r={46} /><circle cx={50} cy={-20} r={58} /><circle cx={110} cy={0} r={44} />
    <rect x={0} y={0} width={110} height={44} />
  </g>
);

const Hills: React.FC<{ back: string; front: string }> = ({ back, front }) => (
  <>
    <path d="M0 760 C300 620 600 700 900 650 C1200 600 1500 700 1920 620 L1920 1080 L0 1080 Z" fill={back} />
    <path d="M0 860 C400 780 800 860 1200 820 C1500 790 1700 830 1920 800 L1920 1080 L0 1080 Z" fill={front} />
  </>
);

const Flowers: React.FC<{ y: number }> = ({ y }) => (
  <>
    {Array.from({ length: 22 }, (_, i) => {
      const x = (i * 263) % 1920;
      const color = ["#FF8FAB", "#FFD166", "#FFFFFF", "#C9B6F2"][i % 4];
      return (
        <g key={i} transform={`translate(${x}, ${y + ((i * 37) % 90)})`}>
          <line y1={0} y2={22} stroke="#4C8B3A" strokeWidth={3} />
          {[0, 72, 144, 216, 288].map((a) => (
            <circle key={a} r={7} fill={color} transform={`rotate(${a}) translate(0, -8)`} />
          ))}
          <circle r={5} fill="#FFB703" />
        </g>
      );
    })}
  </>
);

const Tree: React.FC<{ x: number; s: number; color: string }> = ({ x, s, color }) => (
  <g transform={`translate(${x}, 960) scale(${s})`}>
    <rect x={-22} y={-260} width={44} height={260} rx={14} fill="#8A5A3B" />
    <circle cx={0} cy={-300} r={120} fill={color} />
    <circle cx={-80} cy={-240} r={80} fill={color} />
    <circle cx={80} cy={-240} r={80} fill={color} />
  </g>
);

export const StageBackground: React.FC<{ kind: Background; t: number }> = ({ kind, t }) => {
  const drift = (t * 18) % 2400;
  switch (kind) {
    case "meadow":
      return (
        <g>
          <Sky id="sky-meadow" top="#8FD3FF" bottom="#E4F6FF" />
          <circle cx={1620} cy={180} r={150} fill="#FFF6C2" opacity={0.6} />
          <circle cx={1620} cy={180} r={90} fill="#FFD84D" />
          <Cloud x={((200 + drift) % 2400) - 300} y={170} s={1.1} />
          <Cloud x={((1100 + drift * 0.7) % 2400) - 300} y={280} s={0.8} />
          <Hills back="#9ED676" front="#7CC45A" />
          <Flowers y={880} />
        </g>
      );
    case "forest":
      return (
        <g>
          <Sky id="sky-forest" top="#BDE6D0" bottom="#EAF8EF" />
          {[120, 520, 1400, 1800].map((x, i) => (
            <Tree key={x} x={x} s={0.9 + (i % 2) * 0.25} color={i % 2 ? "#4E9A4B" : "#3E8A42"} />
          ))}
          <Hills back="#6DB35E" front="#5AA24D" />
          {[300, 1600].map((x) => (
            <g key={x} transform={`translate(${x}, 930)`}>
              <rect x={-8} y={-30} width={16} height={30} fill="#FFF3E0" />
              <path d="M-36 -26 Q0 -70 36 -26 Z" fill="#E4572E" />
              <circle cx={-10} cy={-40} r={5} fill="#fff" /><circle cx={12} cy={-34} r={4} fill="#fff" />
            </g>
          ))}
        </g>
      );
    case "pond":
      return (
        <g>
          <Sky id="sky-pond" top="#A8E0FF" bottom="#F0FAFF" />
          <Cloud x={((600 + drift) % 2400) - 300} y={200} s={1} />
          <Hills back="#A5D98A" front="#86C96B" />
          <ellipse cx={1500} cy={985} rx={420} ry={70} fill="#5BB8E8" />
          {[0, 1, 2].map((i) => (
            <ellipse key={i} cx={1500} cy={985} rx={140 + i * 110 + ((t * 30) % 110)} ry={20 + i * 16}
              fill="none" stroke="#D6F1FF" strokeWidth={3} opacity={0.6 - i * 0.18} />
          ))}
          <ellipse cx={1330} cy={990} rx={46} ry={14} fill="#4CAF50" />
          <ellipse cx={1680} cy={975} rx={38} ry={12} fill="#4CAF50" />
          {[1120, 1150, 1880].map((x) => (
            <path key={x} d={`M${x} 960 Q${x - 10} 860 ${x + 6} 820`} stroke="#5E8C31" strokeWidth={8}
              fill="none" />
          ))}
        </g>
      );
    case "night":
      return (
        <g>
          <Sky id="sky-night" top="#1B2350" bottom="#4A4E8C" />
          {Array.from({ length: 40 }, (_, i) => (
            <circle key={i} cx={(i * 197) % 1920} cy={(i * 89) % 600} r={2 + (i % 3)} fill="#FFF7D6"
              opacity={0.5 + 0.5 * Math.abs(Math.sin(t * 1.5 + i))} />
          ))}
          <circle cx={1550} cy={190} r={90} fill="#FFF3C4" />
          <circle cx={1585} cy={170} r={80} fill="#1B2350" opacity={0.0} />
          <Hills back="#2F3B6B" front="#26325C" />
        </g>
      );
    case "garden":
      return (
        <g>
          <Sky id="sky-garden" top="#9EDCFF" bottom="#FFF6E5" />
          <circle cx={300} cy={170} r={80} fill="#FFD84D" />
          <Hills back="#B5E08C" front="#97CF72" />
          {Array.from({ length: 16 }, (_, i) => (
            <rect key={i} x={i * 124} y={760} width={22} height={180} rx={6} fill="#F4E1C1" />
          ))}
          <rect x={0} y={800} width={1920} height={18} fill="#E8CFA6" />
          <rect x={0} y={880} width={1920} height={18} fill="#E8CFA6" />
          <Flowers y={900} />
        </g>
      );
    case "home":
      return (
        <g>
          <rect width={1920} height={1080} fill="#FFE9D2" />
          <rect y={960} width={1920} height={120} fill="#D9A86C" />
          <rect x={1300} y={160} width={420} height={330} rx={24} fill="#9EDCFF" stroke="#fff" strokeWidth={22} />
          <line x1={1510} x2={1510} y1={160} y2={490} stroke="#fff" strokeWidth={14} />
          <rect x={160} y={300} width={360} height={24} rx={8} fill="#B07A4A" />
          {["#FF8FAB", "#4D96FF", "#FFD166", "#7CC45A"].map((c, i) => (
            <rect key={c} x={190 + i * 70} y={210} width={46} height={90} rx={6} fill={c} />
          ))}
          <ellipse cx={960} cy={1010} rx={520} ry={50} fill="#F28B9B" opacity={0.6} />
        </g>
      );
  }
};
