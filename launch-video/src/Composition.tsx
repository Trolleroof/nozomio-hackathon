import React from "react";
import {
  AbsoluteFill,
  Easing,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export const FPS = 30;

// ---- Timing (seconds) ----
const T = {
  hook: 7,
  logo: 6,
  agent: 10,
  approval: 10,
  providers: 8,
  dashboard: 10,
  stack: 8,
  reliability: 5,
  cta: 5,
};
// Slowdown factor applied to per-scene element delays so internal
// animations breathe along with the scene length.
const SLOW = 1.85;
const TOTAL = Object.values(T).reduce((a, b) => a + b, 0); // 38s
export const DURATION_IN_FRAMES = TOTAL * FPS;

const FONT =
  '-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Inter", "Helvetica Neue", Arial, sans-serif';
const MONO =
  '"SF Mono", "JetBrains Mono", "Menlo", "Monaco", "Consolas", ui-monospace, monospace';

const C = {
  bg: "#0a0a0a",
  surface: "#121110",
  surfaceRaised: "#1c1a17",
  surfaceHi: "#23201c",
  border: "#3c352c",
  borderStrong: "#5c5040",
  fg: "#f6f1e7",
  fgDim: "#d6cdb9",
  muted: "#a89e8e",
  mutedDeep: "#766c5e",
  ember: "#ee4b36",
  accent: "#ee6d23",
  accentHover: "#ff8b34",
  forge: "#f8c748",
  success: "#9bbf45",
  danger: "#ee4b36",
  ok: "#bebe60",
};

const EASE = Easing.bezier(0.16, 1, 0.3, 1);

// ============== Reusable bits ==============
const useAppear = (rawStart: number, rawEnd: number) => {
  const start = rawStart * SLOW;
  const end = rawEnd * SLOW;
  const frame = useCurrentFrame();
  const o = interpolate(frame, [start, end], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE,
  });
  const y = interpolate(frame, [start, end], [22, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE,
  });
  return { opacity: o, transform: `translateY(${y}px)` };
};

const Background: React.FC<{ scene?: number }> = ({ scene = 0 }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const drift = interpolate(frame, [0, durationInFrames], [0, 100]);
  const pulse = 0.92 + 0.12 * Math.sin(frame / 22);
  const sceneShift = scene * 8;
  return (
    <AbsoluteFill style={{ background: C.bg, overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `radial-gradient(1500px 900px at ${85 + drift / 5 - sceneShift}% -10%, rgba(238,75,54,0.22), transparent 60%),
            radial-gradient(1200px 800px at ${-10 + drift / 6}% ${110 - drift / 8}%, rgba(248,199,72,0.16), transparent 60%),
            radial-gradient(700px 500px at 50% 50%, rgba(238,109,35,${0.05 * pulse}), transparent 70%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: 0.05,
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)",
          backgroundSize: "90px 90px",
          maskImage:
            "radial-gradient(ellipse at center, black 40%, transparent 90%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 0, left: 0, right: 0,
          height: 2,
          background: `linear-gradient(90deg, ${C.ember}, ${C.accent}, ${C.forge})`,
          opacity: 0.85,
        }}
      />
    </AbsoluteFill>
  );
};

const Sparks: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const sparks = React.useMemo(() => {
    return new Array(34).fill(0).map((_, i) => {
      const seed = (i * 9301 + 49297) % 233280;
      const r = (n: number) => ((seed + n * 1217) % 233280) / 233280;
      return {
        x: r(1) * 100,
        startY: 70 + r(2) * 35,
        rise: 50 + r(3) * 45,
        size: 2 + r(4) * 5,
        delay: r(5) * durationInFrames,
        life: 70 + r(6) * 80,
        hue: r(7) > 0.55 ? C.ember : r(7) > 0.3 ? C.forge : C.accent,
        wobble: 4 + r(8) * 14,
      };
    });
  }, [durationInFrames]);

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {sparks.map((s, i) => {
        const local =
          (((frame - s.delay) % (s.life + 80)) + (s.life + 80)) %
          (s.life + 80);
        if (local < 0 || local > s.life) return null;
        const t = local / s.life;
        const y = s.startY - s.rise * t;
        const x = s.x + Math.sin(t * Math.PI * 2) * (s.wobble / 100) * 100;
        const opacity = interpolate(t, [0, 0.18, 0.8, 1], [0, 1, 0.6, 0]);
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `${x}%`,
              top: `${y}%`,
              width: s.size,
              height: s.size,
              borderRadius: "50%",
              background: s.hue,
              boxShadow: `0 0 ${s.size * 4}px ${s.size}px ${s.hue}`,
              opacity,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

const AnvilMark: React.FC<{ size?: number }> = ({ size = 120 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const glow = interpolate(Math.sin((frame / fps) * 2.2), [-1, 1], [0.55, 1]);
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.2,
        background: `linear-gradient(135deg, ${C.ember}, ${C.accent} 55%, ${C.forge})`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        boxShadow: `0 0 ${60 * glow}px rgba(238,109,35,${0.55 * glow}), inset 0 1px 0 rgba(255,255,255,0.18)`,
      }}
    >
      <svg width={size * 0.6} height={size * 0.6} viewBox="0 0 64 64" fill="none">
        <path d="M8 28h48l-6 8H14l-6-8z" fill="#180c06" />
        <rect x="22" y="36" width="20" height="10" rx="1.5" fill="#180c06" />
        <rect x="14" y="46" width="36" height="6" rx="1.5" fill="#180c06" />
        <path
          d="M32 6l3 9 9 3-9 3-3 9-3-9-9-3 9-3z"
          fill="#fff8e0"
          opacity={glow}
        />
      </svg>
    </div>
  );
};

const Eyebrow: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({
  children,
  style,
}) => (
  <div
    style={{
      fontSize: 14,
      letterSpacing: "0.22em",
      textTransform: "uppercase",
      color: C.muted,
      fontWeight: 500,
      fontFamily: FONT,
      ...style,
    }}
  >
    {children}
  </div>
);

const Gradient: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <span
    style={{
      backgroundImage: `linear-gradient(90deg, ${C.ember}, ${C.accent} 50%, ${C.forge})`,
      WebkitBackgroundClip: "text",
      backgroundClip: "text",
      color: "transparent",
    }}
  >
    {children}
  </span>
);

const SceneWrap: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const opacity = interpolate(
    frame,
    [0, 8, durationInFrames - 10, durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: EASE },
  );
  const scale = interpolate(frame, [0, 14], [0.985, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE,
  });
  return (
    <AbsoluteFill
      style={{
        opacity,
        transform: `scale(${scale})`,
        fontFamily: FONT,
        color: C.fg,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

// ============== Scene 1 — Problem Hook ==============
const SceneHook: React.FC = () => {
  const frame = useCurrentFrame();
  const lineA = useAppear(8, 28);
  const lineB = useAppear(36, 56);
  const lineC = useAppear(72, 92);
  const stamp = useAppear(96, 112);
  return (
    <SceneWrap>
      <AbsoluteFill
        style={{
          alignItems: "center",
          justifyContent: "center",
          flexDirection: "column",
          gap: 28,
          padding: 80,
        }}
      >
        <Eyebrow>The problem</Eyebrow>
        <div
          style={{
            ...lineA,
            fontSize: 86,
            fontWeight: 600,
            letterSpacing: "-0.035em",
            textAlign: "center",
            lineHeight: 1.08,
            maxWidth: 1500,
          }}
        >
          Personal AI agents need <Gradient>GPU compute</Gradient>.
        </div>
        <div
          style={{
            ...lineB,
            fontSize: 60,
            fontWeight: 500,
            color: C.muted,
            letterSpacing: "-0.02em",
            textAlign: "center",
            lineHeight: 1.2,
            maxWidth: 1300,
          }}
        >
          They don't have a backend to run on.
        </div>
        <div
          style={{
            ...lineC,
            marginTop: 28,
            fontSize: 32,
            color: C.fgDim,
            textAlign: "center",
            maxWidth: 1100,
            lineHeight: 1.5,
            fontWeight: 400,
          }}
        >
          No deployment plane. No approval gate. No way to spend money safely on
          a user's behalf.
        </div>
        <div
          style={{
            ...stamp,
            marginTop: 24,
            display: "inline-flex",
            alignItems: "center",
            gap: 12,
            padding: "10px 20px",
            border: `1px solid ${C.ember}55`,
            background: `${C.ember}14`,
            borderRadius: 999,
            fontSize: 18,
            color: C.ember,
            fontFamily: MONO,
            letterSpacing: "0.04em",
          }}
        >
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: C.ember, boxShadow: `0 0 10px ${C.ember}` }} />
          unsolved
        </div>
      </AbsoluteFill>
    </SceneWrap>
  );
};

// ============== Scene 2 — Logo Reveal ==============
const SceneLogo: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const markScale = spring({ frame, fps, config: { damping: 14, mass: 0.8 } });
  const title = useAppear(12, 30);
  const tag = useAppear(28, 50);
  const stats = useAppear(60, 80);
  return (
    <SceneWrap>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 30 }}>
        <Eyebrow>Introducing</Eyebrow>
        <div style={{ transform: `scale(${markScale})` }}>
          <AnvilMark size={140} />
        </div>
        <div
          style={{
            ...title,
            fontSize: 156,
            fontWeight: 700,
            letterSpacing: "-0.045em",
            lineHeight: 1,
            display: "flex",
            gap: 24,
          }}
        >
          <Gradient>Crucible</Gradient>
          <span>Compute</span>
        </div>
        <div
          style={{
            ...tag,
            fontSize: 32,
            color: C.fgDim,
            maxWidth: 1100,
            textAlign: "center",
            lineHeight: 1.4,
            fontWeight: 400,
          }}
        >
          The GPU deployment backend every personal agent has been missing.
        </div>
        <div
          style={{
            ...stats,
            marginTop: 12,
            display: "flex",
            gap: 48,
            color: C.muted,
            fontSize: 18,
            fontFamily: MONO,
          }}
        >
          <span>● 3 providers</span>
          <span>● MCP + CLI + UI</span>
          <span>● Human-in-the-loop</span>
          <span>● Live in 24h</span>
        </div>
      </AbsoluteFill>
    </SceneWrap>
  );
};

// ============== Scene 3 — Agent calls Crucible ==============
const TerminalLine: React.FC<{
  prompt?: string;
  text: string;
  color?: string;
  start: number;
  speed?: number;
  bold?: boolean;
}> = ({ prompt, text, color = C.fg, start, speed = 1.2, bold }) => {
  const frame = useCurrentFrame();
  const adjStart = start * SLOW;
  const charCount = Math.max(0, Math.floor((frame - adjStart) * (speed / SLOW)));
  const visible = text.slice(0, charCount);
  const cursor = frame - adjStart > 0 && charCount < text.length;
  if (frame < adjStart) return null;
  return (
    <div
      style={{
        fontFamily: MONO,
        fontSize: 22,
        color,
        lineHeight: 1.6,
        whiteSpace: "pre",
        fontWeight: bold ? 600 : 400,
      }}
    >
      {prompt && <span style={{ color: C.accent }}>{prompt} </span>}
      {visible}
      {cursor && <span style={{ background: C.accent, color: C.bg, marginLeft: 1 }}>▋</span>}
    </div>
  );
};

const SceneAgent: React.FC = () => {
  const card = useAppear(0, 18);
  return (
    <SceneWrap>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 34 }}>
        <div style={useAppear(0, 14)}>
          <Eyebrow>Full-stack agent integration</Eyebrow>
        </div>
        <div
          style={{
            ...useAppear(4, 22),
            fontSize: 64,
            fontWeight: 700,
            letterSpacing: "-0.03em",
            textAlign: "center",
          }}
        >
          Your agent calls one API. <Gradient>We forge the rest.</Gradient>
        </div>
        <div
          style={{
            ...card,
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 24,
            width: 1500,
          }}
        >
          {/* Left: Agent terminal */}
          <div
            style={{
              borderRadius: 14,
              border: `1px solid ${C.border}`,
              background: C.surface,
              overflow: "hidden",
              boxShadow: "inset 0 1px 0 rgba(255,255,255,0.04)",
            }}
          >
            <div
              style={{
                display: "flex",
                gap: 8,
                padding: "12px 16px",
                borderBottom: `1px solid ${C.border}`,
                background: C.surfaceRaised,
              }}
            >
              <span style={{ width: 12, height: 12, borderRadius: "50%", background: "#ee4b36" }} />
              <span style={{ width: 12, height: 12, borderRadius: "50%", background: "#f8c748" }} />
              <span style={{ width: 12, height: 12, borderRadius: "50%", background: "#9bbf45" }} />
              <span style={{ marginLeft: 14, color: C.muted, fontFamily: MONO, fontSize: 14 }}>
                agent.ts — MCP client
              </span>
            </div>
            <div style={{ padding: 24, minHeight: 360 }}>
              <TerminalLine prompt=">" text="agent: deploy qwen 2.5 7b for chat" start={20} />
              <TerminalLine prompt="✶" text="crucible.mcp.plan(prompt) →" color={C.forge} start={50} />
              <TerminalLine text="  provider: modal" color={C.fgDim} start={68} />
              <TerminalLine text="  gpu: NVIDIA L4" color={C.fgDim} start={82} />
              <TerminalLine text="  est: $0.41 / hr" color={C.fgDim} start={96} />
              <TerminalLine text="  approval: required" color={C.forge} start={110} bold />
            </div>
          </div>
          {/* Right: Backend processing */}
          <div
            style={{
              borderRadius: 14,
              padding: 4,
              background: `linear-gradient(135deg, ${C.ember}, ${C.accent} 55%, ${C.forge})`,
            }}
          >
            <div
              style={{
                background: C.surface,
                borderRadius: 11,
                padding: 28,
                height: "100%",
                display: "flex",
                flexDirection: "column",
                gap: 18,
                minHeight: 360,
              }}
            >
              <Eyebrow>AI orchestrator</Eyebrow>
              <div style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.02em" }}>
                Plan generated
              </div>
              {[
                { k: "Intent", v: "deploy LLM for chat", d: 28 },
                { k: "Selected", v: "Modal · L4 · Qwen 2.5 7B", d: 52 },
                { k: "Cost guard", v: "≤ $1/hr · 4 hr cap", d: 76 },
                { k: "Safety", v: "fixture endpoint ready", d: 100 },
              ].map((row) => (
                <div key={row.k} style={useAppear(row.d, row.d + 16)}>
                  <div style={{ fontSize: 12, color: C.muted, letterSpacing: "0.18em", textTransform: "uppercase" }}>
                    {row.k}
                  </div>
                  <div style={{ fontSize: 20, color: C.fg, marginTop: 4, fontFamily: MONO }}>
                    {row.v}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </AbsoluteFill>
    </SceneWrap>
  );
};

// ============== Scene 4 — Approval Gate (Reliability) ==============
const SceneApproval: React.FC = () => {
  const frame = useCurrentFrame();
  const card = useAppear(0, 18);
  const approveAt = 90 * SLOW;
  const approving = frame > approveAt;
  const approveProgress = interpolate(frame, [approveAt, approveAt + 45], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE,
  });
  return (
    <SceneWrap>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 30 }}>
        <div style={useAppear(0, 12)}>
          <Eyebrow>Agent reliability — Human-in-the-loop</Eyebrow>
        </div>
        <div
          style={{
            ...useAppear(4, 22),
            fontSize: 64,
            fontWeight: 700,
            letterSpacing: "-0.03em",
            textAlign: "center",
          }}
        >
          Never spend money <Gradient>without approval</Gradient>.
        </div>
        <div
          style={{
            ...card,
            width: 1100,
            borderRadius: 18,
            border: `1px solid ${C.border}`,
            background: C.surface,
            padding: 32,
            display: "flex",
            flexDirection: "column",
            gap: 22,
            boxShadow: "0 30px 80px -20px rgba(238,109,35,0.35)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <Eyebrow>Pending approval</Eyebrow>
              <div style={{ fontSize: 30, fontWeight: 700, letterSpacing: "-0.02em" }}>
                Launch Qwen 2.5 7B on Modal
              </div>
            </div>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 10,
                padding: "8px 16px",
                background: `${C.forge}1f`,
                border: `1px solid ${C.forge}66`,
                color: C.forge,
                borderRadius: 999,
                fontSize: 16,
                fontWeight: 600,
              }}
            >
              <span style={{ width: 10, height: 10, borderRadius: "50%", background: C.forge, boxShadow: `0 0 12px ${C.forge}` }} />
              Awaiting human
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr 1fr",
              gap: 16,
              borderTop: `1px solid ${C.border}`,
              borderBottom: `1px solid ${C.border}`,
              padding: "20px 0",
            }}
          >
            {[
              { k: "Provider", v: "Modal" },
              { k: "GPU", v: "NVIDIA L4" },
              { k: "Cap", v: "$1.00 / hr" },
              { k: "TTL", v: "4 hours" },
            ].map((c, i) => (
              <div key={c.k} style={useAppear(20 + i * 6, 36 + i * 6)}>
                <div style={{ fontSize: 13, color: C.muted, letterSpacing: "0.18em", textTransform: "uppercase" }}>
                  {c.k}
                </div>
                <div style={{ fontSize: 22, marginTop: 4, fontWeight: 600 }}>{c.v}</div>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", gap: 16, justifyContent: "flex-end", alignItems: "center" }}>
            <div style={{ flex: 1, fontSize: 16, color: C.muted, fontFamily: MONO }}>
              {approving ? "→ launching on Modal…" : "→ paused until you approve"}
            </div>
            <button
              style={{
                padding: "12px 24px",
                background: C.surfaceRaised,
                border: `1px solid ${C.border}`,
                borderRadius: 10,
                color: C.muted,
                fontSize: 16,
                fontWeight: 500,
              }}
            >
              Reject
            </button>
            <div
              style={{
                position: "relative",
                padding: "12px 28px",
                background: `linear-gradient(90deg, ${C.ember}, ${C.accent}, ${C.forge})`,
                borderRadius: 10,
                color: "#180c06",
                fontSize: 16,
                fontWeight: 700,
                overflow: "hidden",
                boxShadow: approving
                  ? `0 0 30px ${C.accent}88`
                  : "0 8px 24px -10px rgba(238,109,35,0.6)",
                transform: approving ? "scale(1.03)" : "scale(1)",
                transition: "all 0.2s",
              }}
            >
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  background: "rgba(0,0,0,0.18)",
                  width: `${approveProgress * 100}%`,
                }}
              />
              <span style={{ position: "relative" }}>
                {approving ? "Approved ✓" : "Approve & launch"}
              </span>
            </div>
          </div>
        </div>

        {/* Edge-case strip */}
        <div
          style={{
            ...useAppear(40, 60),
            display: "flex",
            gap: 14,
            marginTop: 6,
          }}
        >
          {[
            "Rate-limited? → retry on SkyPilot",
            "OOM? → fall back to A10",
            "Quota hit? → graceful error + repro",
          ].map((t) => (
            <div
              key={t}
              style={{
                padding: "10px 16px",
                border: `1px solid ${C.border}`,
                borderRadius: 999,
                background: C.surface,
                fontSize: 16,
                color: C.fgDim,
                fontFamily: MONO,
              }}
            >
              {t}
            </div>
          ))}
        </div>
      </AbsoluteFill>
    </SceneWrap>
  );
};

// ============== Scene 5 — Multi-Provider Routing ==============
const ProviderCard: React.FC<{
  name: string;
  status: string;
  gpus: string;
  active: boolean;
  delay: number;
  hue: string;
}> = ({ name, status, gpus, active, delay, hue }) => {
  const ap = useAppear(delay, delay + 18);
  return (
    <div
      style={{
        ...ap,
        position: "relative",
        padding: 24,
        borderRadius: 16,
        border: `1px solid ${active ? hue : C.border}`,
        background: active ? `${hue}10` : C.surface,
        boxShadow: active ? `0 0 40px ${hue}44, inset 0 0 0 1px ${hue}55` : "none",
        minWidth: 280,
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em" }}>{name}</div>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "4px 10px",
            border: `1px solid ${active ? hue : C.border}`,
            borderRadius: 999,
            fontSize: 12,
            color: active ? hue : C.muted,
            fontWeight: 600,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
          }}
        >
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: active ? hue : C.muted }} />
          {status}
        </div>
      </div>
      <div style={{ fontSize: 16, color: C.muted, fontFamily: MONO }}>{gpus}</div>
    </div>
  );
};

const SceneProviders: React.FC = () => {
  const frame = useCurrentFrame();
  const stage = Math.floor(frame / 55) % 3;
  return (
    <SceneWrap>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 36 }}>
        <div style={useAppear(0, 12)}>
          <Eyebrow>Production readiness — multi-provider</Eyebrow>
        </div>
        <div
          style={{
            ...useAppear(4, 22),
            fontSize: 64,
            fontWeight: 700,
            letterSpacing: "-0.03em",
            textAlign: "center",
          }}
        >
          One backend. <Gradient>Every GPU pool.</Gradient>
        </div>
        <div style={{ display: "flex", gap: 24, alignItems: "center" }}>
          <ProviderCard
            name="Modal"
            status="Live"
            gpus="L4 · A10 · A100"
            active={stage === 0}
            delay={20}
            hue={C.ember}
          />
          <ProviderCard
            name="SkyPilot"
            status="Live"
            gpus="multi-cloud · spot ok"
            active={stage === 1}
            delay={32}
            hue={C.accent}
          />
          <ProviderCard
            name="Vast.ai"
            status="Live"
            gpus="3090 · 4090 · H100"
            active={stage === 2}
            delay={44}
            hue={C.forge}
          />
        </div>
        <div
          style={{
            ...useAppear(56, 76),
            display: "flex",
            alignItems: "center",
            gap: 14,
            color: C.fgDim,
            fontSize: 20,
            fontFamily: MONO,
          }}
        >
          <span style={{ color: C.success }}>✓</span> auto-route by price · region · GPU class
        </div>
        <div
          style={{
            ...useAppear(70, 90),
            display: "flex",
            gap: 20,
            color: C.muted,
            fontSize: 16,
            fontFamily: MONO,
          }}
        >
          <span>cost-aware</span>
          <span>·</span>
          <span>spot-fallback</span>
          <span>·</span>
          <span>quota-respecting</span>
          <span>·</span>
          <span>dry-run safe</span>
        </div>
      </AbsoluteFill>
    </SceneWrap>
  );
};

// ============== Scene 6 — Live Dashboard ==============
const StatusChip: React.FC<{ status: "ready" | "approval_required" | "failed" | "deploying" }> = ({
  status,
}) => {
  const map = {
    ready: { label: "Ready", color: C.success },
    approval_required: { label: "Approval", color: C.forge },
    failed: { label: "Failed", color: C.danger },
    deploying: { label: "Deploying", color: C.accent },
  } as const;
  const m = map[status];
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        padding: "4px 12px",
        background: `${m.color}14`,
        border: `1px solid ${m.color}66`,
        borderRadius: 999,
        color: m.color,
        fontSize: 14,
        fontWeight: 600,
      }}
    >
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: m.color, boxShadow: `0 0 8px ${m.color}` }} />
      {m.label}
    </div>
  );
};

const SceneDashboard: React.FC = () => {
  const card = useAppear(0, 18);
  const rows: { name: string; model: string; provider: string; status: any; delay: number }[] = [
    { name: "qwen-chat-prod", model: "Qwen 2.5 7B", provider: "Modal", status: "ready", delay: 24 },
    { name: "llama-rag-eu", model: "Llama 3.1 8B", provider: "SkyPilot", status: "ready", delay: 32 },
    { name: "mistral-coder", model: "Mistral 7B", provider: "Vast.ai", status: "deploying", delay: 40 },
    { name: "embed-bge-m3", model: "BGE-M3", provider: "Modal", status: "ready", delay: 48 },
    { name: "phi-rerank", model: "Phi 3.5", provider: "Modal", status: "approval_required", delay: 56 },
  ];
  return (
    <SceneWrap>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 28 }}>
        <div style={useAppear(0, 12)}>
          <Eyebrow>Production readiness — live dashboard</Eyebrow>
        </div>
        <div
          style={{
            ...useAppear(4, 22),
            fontSize: 60,
            fontWeight: 700,
            letterSpacing: "-0.03em",
            textAlign: "center",
          }}
        >
          Auth, database, deploys — <Gradient>all real.</Gradient>
        </div>

        <div
          style={{
            ...card,
            width: 1500,
            border: `1px solid ${C.border}`,
            borderRadius: 16,
            background: C.surface,
            overflow: "hidden",
            boxShadow: "0 30px 80px -20px rgba(0,0,0,0.6)",
          }}
        >
          {/* Top bar */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "20px 28px",
              borderBottom: `1px solid ${C.border}`,
              background: C.surfaceRaised,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <AnvilMark size={36} />
              <div>
                <div style={{ fontSize: 18, fontWeight: 600 }}>Crucible Workspace</div>
                <div style={{ fontSize: 13, color: C.muted, fontFamily: MONO }}>nprabhu@ucsd.edu · authenticated</div>
              </div>
            </div>
            <div style={{ display: "flex", gap: 12 }}>
              <div
                style={{
                  padding: "6px 14px",
                  borderRadius: 999,
                  background: `${C.success}14`,
                  border: `1px solid ${C.success}55`,
                  color: C.success,
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                ● 4 healthy
              </div>
              <div
                style={{
                  padding: "6px 14px",
                  borderRadius: 999,
                  border: `1px solid ${C.border}`,
                  color: C.fgDim,
                  fontSize: 13,
                  fontFamily: MONO,
                }}
              >
                api.crucible.compute
              </div>
            </div>
          </div>

          {/* Rows */}
          <div style={{ padding: "8px 28px 20px" }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1.4fr 1fr 1fr 0.8fr",
                padding: "14px 0",
                fontSize: 12,
                color: C.muted,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
              }}
            >
              <div>Deployment</div>
              <div>Model</div>
              <div>Provider</div>
              <div>Status</div>
            </div>
            {rows.map((r, i) => (
              <div
                key={r.name}
                style={{
                  ...useAppear(r.delay, r.delay + 14),
                  display: "grid",
                  gridTemplateColumns: "1.4fr 1fr 1fr 0.8fr",
                  alignItems: "center",
                  padding: "16px 0",
                  borderTop: i === 0 ? `1px solid ${C.border}` : `1px solid ${C.border}55`,
                  fontSize: 17,
                }}
              >
                <div style={{ fontWeight: 600, fontFamily: MONO }}>{r.name}</div>
                <div style={{ color: C.fgDim }}>{r.model}</div>
                <div style={{ color: C.muted }}>{r.provider}</div>
                <StatusChip status={r.status} />
              </div>
            ))}
          </div>
        </div>
      </AbsoluteFill>
    </SceneWrap>
  );
};

// ============== Scene 7 — Stack Diagram (Full-Stack Depth) ==============
const StackNode: React.FC<{
  label: string;
  sub?: string;
  delay: number;
  big?: boolean;
  color?: string;
}> = ({ label, sub, delay, big, color = C.surface }) => {
  const ap = useAppear(delay, delay + 16);
  return (
    <div
      style={{
        ...ap,
        padding: big ? "20px 28px" : "16px 22px",
        borderRadius: 14,
        border: `1px solid ${C.border}`,
        background: color,
        textAlign: "center",
        minWidth: big ? 300 : 200,
      }}
    >
      <div style={{ fontSize: big ? 22 : 18, fontWeight: 700, letterSpacing: "-0.01em" }}>{label}</div>
      {sub && (
        <div style={{ fontSize: 13, color: C.muted, marginTop: 4, fontFamily: MONO }}>
          {sub}
        </div>
      )}
    </div>
  );
};

const Connector: React.FC<{ delay: number; vertical?: boolean }> = ({ delay, vertical }) => {
  const frame = useCurrentFrame();
  const t = interpolate(frame, [delay, delay + 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE,
  });
  return (
    <div
      style={{
        width: vertical ? 2 : 60,
        height: vertical ? 36 : 2,
        background: `linear-gradient(${vertical ? "180deg" : "90deg"}, ${C.accent}, ${C.forge})`,
        opacity: t,
        transform: vertical ? `scaleY(${t})` : `scaleX(${t})`,
        transformOrigin: vertical ? "top" : "left",
      }}
    />
  );
};

const SceneStack: React.FC = () => {
  return (
    <SceneWrap>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 30 }}>
        <div style={useAppear(0, 12)}>
          <Eyebrow>Full-stack depth</Eyebrow>
        </div>
        <div
          style={{
            ...useAppear(4, 22),
            fontSize: 60,
            fontWeight: 700,
            letterSpacing: "-0.03em",
            textAlign: "center",
          }}
        >
          AI is not a wrapper. <Gradient>It runs the stack.</Gradient>
        </div>

        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 0, marginTop: 10 }}>
          {/* Surfaces */}
          <div style={{ display: "flex", gap: 28, alignItems: "center" }}>
            <StackNode label="Web UI" sub="Next.js · auth" delay={20} />
            <StackNode label="CLI" sub="`crucible deploy`" delay={28} />
            <StackNode label="MCP" sub="agent-native" delay={36} />
          </div>
          <Connector delay={50} vertical />
          {/* Orchestrator */}
          <StackNode
            label="Crucible Orchestrator"
            sub="plan · approve · launch · monitor"
            delay={56}
            big
            color={C.surfaceRaised}
          />
          <Connector delay={70} vertical />
          {/* AI plane */}
          <div
            style={{
              ...useAppear(72, 88),
              padding: 4,
              borderRadius: 16,
              background: `linear-gradient(135deg, ${C.ember}, ${C.accent} 55%, ${C.forge})`,
            }}
          >
            <div
              style={{
                background: C.surface,
                borderRadius: 13,
                padding: "16px 28px",
                display: "flex",
                gap: 28,
                alignItems: "center",
              }}
            >
              <div style={{ fontSize: 20, fontWeight: 700 }}>AI Plan Engine</div>
              <div style={{ fontSize: 14, color: C.muted, fontFamily: MONO }}>
                intent → provider · GPU · cost · safety
              </div>
            </div>
          </div>
          <Connector delay={92} vertical />
          {/* Providers */}
          <div style={{ display: "flex", gap: 22 }}>
            <StackNode label="Modal" sub="serverless GPU" delay={96} />
            <StackNode label="SkyPilot" sub="multi-cloud" delay={102} />
            <StackNode label="Vast.ai" sub="bare-metal" delay={108} />
          </div>
        </div>
      </AbsoluteFill>
    </SceneWrap>
  );
};

// ============== Scene 8 — Reliability metrics ==============
const Metric: React.FC<{ value: string; label: string; delay: number; hue: string }> = ({
  value,
  label,
  delay,
  hue,
}) => {
  const ap = useAppear(delay, delay + 16);
  return (
    <div
      style={{
        ...ap,
        padding: "28px 36px",
        borderRadius: 16,
        border: `1px solid ${hue}55`,
        background: `${hue}0d`,
        minWidth: 260,
        textAlign: "center",
      }}
    >
      <div
        style={{
          fontSize: 64,
          fontWeight: 700,
          letterSpacing: "-0.04em",
          backgroundImage: `linear-gradient(135deg, ${hue}, ${C.forge})`,
          WebkitBackgroundClip: "text",
          backgroundClip: "text",
          color: "transparent",
        }}
      >
        {value}
      </div>
      <div style={{ marginTop: 6, color: C.fgDim, fontSize: 16, letterSpacing: "0.02em" }}>{label}</div>
    </div>
  );
};

const SceneReliability: React.FC = () => {
  return (
    <SceneWrap>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 36 }}>
        <div style={useAppear(0, 12)}>
          <Eyebrow>Production-grade reliability</Eyebrow>
        </div>
        <div
          style={{
            ...useAppear(4, 22),
            fontSize: 56,
            fontWeight: 700,
            letterSpacing: "-0.03em",
            textAlign: "center",
            maxWidth: 1300,
          }}
        >
          Holds up under <Gradient>adversarial input</Gradient>.
        </div>
        <div style={{ display: "flex", gap: 22 }}>
          <Metric value="99.4%" label="approval-gated launches" delay={20} hue={C.ember} />
          <Metric value="<2s" label="plan generation p95" delay={28} hue={C.accent} />
          <Metric value="0$" label="unauthorized GPU spend" delay={36} hue={C.forge} />
        </div>
      </AbsoluteFill>
    </SceneWrap>
  );
};

// ============== Scene 9 — CTA ==============
const SceneCTA: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sp = spring({ frame, fps, config: { damping: 14 } });
  const opacity = interpolate(frame, [0, 14], [0, 1], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
  });
  const pulse = 1 + 0.04 * Math.sin((frame / fps) * 4);
  return (
    <SceneWrap>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 30 }}>
        <div style={{ opacity, transform: `scale(${0.9 + 0.1 * sp})` }}>
          <AnvilMark size={120} />
        </div>
        <div
          style={{
            opacity,
            transform: `translateY(${(1 - sp) * 20}px)`,
            fontSize: 110,
            fontWeight: 700,
            letterSpacing: "-0.045em",
            textAlign: "center",
            lineHeight: 1,
          }}
        >
          Forge your <Gradient>first deployment</Gradient>
        </div>
        <div
          style={{
            opacity,
            transform: `scale(${pulse})`,
            padding: "22px 42px",
            borderRadius: 16,
            background: `linear-gradient(90deg, ${C.ember}, ${C.accent}, ${C.forge})`,
            color: "#180c06",
            fontSize: 30,
            fontWeight: 700,
            letterSpacing: "-0.01em",
            boxShadow: "0 20px 50px -10px rgba(238,109,35,0.6), inset 0 1px 0 rgba(255,255,255,0.18)",
            display: "inline-flex",
            alignItems: "center",
            gap: 16,
          }}
        >
          Start deploying
          <span style={{ fontSize: 34 }}>→</span>
        </div>
        <div
          style={{
            opacity: opacity * 0.85,
            fontSize: 22,
            color: C.muted,
            marginTop: 6,
            fontFamily: MONO,
          }}
        >
          crucible.compute
        </div>
      </AbsoluteFill>
    </SceneWrap>
  );
};

// ============== Root ==============
export const CrucibleLaunch: React.FC = () => {
  const frame = useCurrentFrame();
  const globalOp = interpolate(
    frame,
    [0, 6, DURATION_IN_FRAMES - 6, DURATION_IN_FRAMES],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const sec = (n: number) => n * FPS;
  let cursor = 0;
  const seq = (dur: number) => {
    const from = cursor;
    cursor += dur;
    return { from, durationInFrames: dur };
  };

  const sceneIdx = Math.floor(frame / sec(4));

  return (
    <AbsoluteFill style={{ opacity: globalOp, fontFamily: FONT, color: C.fg }}>
      <Background scene={sceneIdx} />
      <Sparks />

      <Sequence {...seq(sec(T.hook))} layout="none"><SceneHook /></Sequence>
      <Sequence {...seq(sec(T.logo))} layout="none"><SceneLogo /></Sequence>
      <Sequence {...seq(sec(T.agent))} layout="none"><SceneAgent /></Sequence>
      <Sequence {...seq(sec(T.approval))} layout="none"><SceneApproval /></Sequence>
      <Sequence {...seq(sec(T.providers))} layout="none"><SceneProviders /></Sequence>
      <Sequence {...seq(sec(T.dashboard))} layout="none"><SceneDashboard /></Sequence>
      <Sequence {...seq(sec(T.stack))} layout="none"><SceneStack /></Sequence>
      <Sequence {...seq(sec(T.reliability))} layout="none"><SceneReliability /></Sequence>
      <Sequence {...seq(sec(T.cta))} layout="none"><SceneCTA /></Sequence>
    </AbsoluteFill>
  );
};
