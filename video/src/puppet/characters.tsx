import React from "react";
import { Face } from "./Face";
import type { CharacterId, Emotion } from "./types";

/** Everything a puppet needs to draw one frame. Origin: between the feet; up is negative y. */
export type Pose = {
  mouth: number;
  blink: number;
  emotion: Emotion;
  look: number;
  armL: number; // degrees the arm is raised away from the body: 0 hangs down, 180 points up
  armR: number;
  lift: number; // pixels off the ground (jumps, walking bounce)
  tilt: number; // whole-body sway, degrees
  headTilt: number;
  squash: number; // 1 normal; below 1 squashes before a jump
  facing: 1 | -1;
  t: number; // seconds, for idle cycles (tail sway, wing flaps)
};

const Arm: React.FC<{ x: number; y: number; angle: number; side: -1 | 1; color: string;
  paw: string; length: number; width: number }> = ({ x, y, angle, side, color, paw, length, width }) => (
  <g transform={`translate(${x}, ${y}) rotate(${side === -1 ? angle : -angle})`}>
    <rect x={-width / 2} y={-6} width={width} height={length} rx={width / 2} fill={color} />
    <circle cy={length - 6} r={width / 2 + 3} fill={paw} />
  </g>
);

export const Fennel: React.FC<{ pose: Pose }> = ({ pose }) => {
  const sway = Math.sin(pose.t * 2.2) * 9;
  return (
    <g>
      <g transform={`rotate(${sway}, 40, -70)`}>
        <path d="M40 -70 C120 -60 170 -140 140 -220 C120 -170 90 -150 60 -130 Z" fill="#F28C38" />
        <path d="M140 -220 C150 -190 145 -165 128 -150 C120 -175 125 -200 140 -220 Z" fill="#FFF3E0" />
      </g>
      <ellipse cx={-30} cy={-12} rx={24} ry={14} fill="#5B3A29" />
      <ellipse cx={30} cy={-12} rx={24} ry={14} fill="#5B3A29" />
      <ellipse cx={0} cy={-105} rx={74} ry={90} fill="#F28C38" />
      <ellipse cx={0} cy={-92} rx={46} ry={62} fill="#FFE8C7" />
      <path d="M-44 -170 L-50 -60" stroke="#43A047" strokeWidth={13} strokeLinecap="round" />
      <path d="M44 -170 L50 -60" stroke="#43A047" strokeWidth={13} strokeLinecap="round" />
      <Arm x={-62} y={-165} angle={pose.armL} side={-1} color="#F28C38" paw="#5B3A29" length={78} width={24} />
      <Arm x={62} y={-165} angle={pose.armR} side={1} color="#F28C38" paw="#5B3A29" length={78} width={24} />
      <g transform={`translate(0, -232) rotate(${pose.headTilt})`}>
        <path d="M-70 -30 L-52 -112 L-14 -66 Z" fill="#F28C38" />
        <path d="M-60 -44 L-50 -92 L-26 -64 Z" fill="#FFB6A3" />
        <path d="M-56 -98 L-52 -112 L-44 -100 Z" fill="#3E2A20" />
        <path d="M70 -30 L52 -112 L14 -66 Z" fill="#F28C38" />
        <path d="M60 -44 L50 -92 L26 -64 Z" fill="#FFB6A3" />
        <path d="M56 -98 L52 -112 L44 -100 Z" fill="#3E2A20" />
        <circle r={80} fill="#F28C38" />
        <path d="M-78 10 C-60 70 60 70 78 10 C50 30 -50 30 -78 10 Z" fill="#FFF3E0" />
        <ellipse cy={26} rx={42} ry={30} fill="#FFF3E0" />
        <ellipse cy={12} rx={11} ry={8} fill="#3E2A20" />
        <Face mouth={pose.mouth} blink={pose.blink} emotion={pose.emotion} look={pose.look}
          eyeGap={32} eyeY={-14} mouthY={34} />
      </g>
    </g>
  );
};

export const Olo: React.FC<{ pose: Pose }> = ({ pose }) => (
  <g>
    <ellipse cx={-48} cy={-12} rx={28} ry={16} fill="#6FAE4F" />
    <ellipse cx={48} cy={-12} rx={28} ry={16} fill="#6FAE4F" />
    <ellipse cx={0} cy={-108} rx={108} ry={92} fill="#3F7A30" />
    {[[-58, -130], [0, -165], [58, -130], [-50, -70], [50, -70]].map(([x, y]) => (
      <path key={`${x},${y}`} transform={`translate(${x}, ${y})`}
        d="M-20 -12 L0 -24 L20 -12 L20 12 L0 24 L-20 12 Z" fill="#5C9E43" />
    ))}
    <ellipse cx={0} cy={-98} rx={62} ry={74} fill="#E8D99A" />
    {[-130, -100, -70].map((y) => (
      <line key={y} x1={-48} x2={48} y1={y} y2={y} stroke="#CDBB72" strokeWidth={4} />
    ))}
    <Arm x={-82} y={-150} angle={pose.armL} side={-1} color="#8CC66A" paw="#7AB55A" length={58} width={28} />
    <Arm x={82} y={-150} angle={pose.armR} side={1} color="#8CC66A" paw="#7AB55A" length={58} width={28} />
    <g transform={`translate(0, -232) rotate(${pose.headTilt})`}>
      <rect x={-26} y={40} width={52} height={50} fill="#8CC66A" />
      <circle r={66} fill="#8CC66A" />
      <g transform="translate(36, -58)">
        {[0, 60, 120, 180, 240, 300].map((a) => (
          <ellipse key={a} rx={9} ry={17} fill="#fff" transform={`rotate(${a}) translate(0, -14)`} />
        ))}
        <circle r={10} fill="#FFC93C" />
      </g>
      <Face mouth={pose.mouth} blink={pose.blink} emotion={pose.emotion} look={pose.look}
        eyeGap={26} eyeY={-6} mouthY={30} />
      <ellipse cx={-42} cy={18} rx={10} ry={6} fill="#F7A8B8" opacity={0.6} />
      <ellipse cx={42} cy={18} rx={10} ry={6} fill="#F7A8B8" opacity={0.6} />
    </g>
    <path d="M-60 -168 Q0 -140 60 -168 L56 -146 Q0 -120 -56 -146 Z" fill="#F7C948" />
    <path d="M30 -150 L52 -96 L34 -92 L18 -146 Z" fill="#F2B632" />
  </g>
);

export const Glim: React.FC<{ pose: Pose }> = ({ pose }) => {
  const hover = -150 + Math.sin(pose.t * 3) * 12;
  const flap = 0.55 + 0.45 * Math.abs(Math.sin(pose.t * 16));
  const glow = 0.55 + 0.25 * Math.sin(pose.t * 4);
  return (
    <g>
      <ellipse cx={0} cy={-4} rx={44} ry={9} fill="#000" opacity={0.08} />
      <g transform={`translate(0, ${hover})`}>
        <circle cx={0} cy={-34} r={80} fill="#FFE066" opacity={glow * 0.35} />
        <circle cx={0} cy={-34} r={28} fill="#FFE066" />
        {[-1, 1].map((side) => (
          <ellipse key={side} cx={side * 44} cy={-118} rx={46} ry={28} fill="#C9B6F2" opacity={0.85}
            transform={`rotate(${side * -28}, ${side * 20}, -110) scale(1, ${flap})`}
            style={{ transformBox: "fill-box", transformOrigin: "center" }} />
        ))}
        <circle cx={0} cy={-84} r={46} fill="#FFCFB3" />
        <Arm x={-36} y={-90} angle={pose.armL} side={-1} color="#FFCFB3" paw="#F7B798" length={30} width={14} />
        <Arm x={36} y={-90} angle={pose.armR} side={1} color="#FFCFB3" paw="#F7B798" length={30} width={14} />
        <g transform={`translate(0, -160) rotate(${pose.headTilt})`}>
          <path d="M-16 -36 Q-30 -70 -40 -78" stroke="#5B4A6B" strokeWidth={4} fill="none" />
          <path d="M16 -36 Q30 -70 40 -78" stroke="#5B4A6B" strokeWidth={4} fill="none" />
          <circle cx={-40} cy={-80} r={7} fill="#FFE066" />
          <circle cx={40} cy={-80} r={7} fill="#FFE066" />
          <circle r={46} fill="#FFCFB3" />
          <Face mouth={pose.mouth} blink={pose.blink} emotion={pose.emotion} look={pose.look}
            eyeGap={18} eyeY={-4} mouthY={20} size={0.8} />
          <ellipse cx={-28} cy={12} rx={8} ry={5} fill="#F7A8B8" opacity={0.7} />
          <ellipse cx={28} cy={12} rx={8} ry={5} fill="#F7A8B8" opacity={0.7} />
        </g>
      </g>
    </g>
  );
};

export const PUPPETS: Record<CharacterId, React.FC<{ pose: Pose }>> = { fennel: Fennel, olo: Olo, glim: Glim };

/** Draws a puppet at stage position x with its pose applied around the feet. */
export const Puppet: React.FC<{ id: CharacterId; x: number; ground: number; pose: Pose; scale?: number }> = ({
  id, x, ground, pose, scale = 1,
}) => {
  const Body = PUPPETS[id];
  return (
    <g transform={`translate(${x}, ${ground - pose.lift}) rotate(${pose.tilt}) scale(${pose.facing * scale}, ${pose.squash * scale})`}>
      <Body pose={pose} />
    </g>
  );
};
