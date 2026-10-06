import { ImageResponse } from "next/og";

// The card shown when a link to AURA is shared (LinkedIn, Slack, WhatsApp...). Drawn here from the app's
// own colours, so there is no image file to keep in step. Only flexbox layouts work in ImageResponse.
export const alt = "AURA, an AI English speaking coach";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          width: "100%",
          height: "100%",
          padding: 72,
          background: "#f2f7fb",
          color: "#0d0d0d",
        }}
      >
        <div style={{ display: "flex", alignItems: "center" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 64,
              height: 64,
              background: "#40719e",
              color: "#ffffff",
              fontSize: 40,
            }}
          >
            A
          </div>
          <div style={{ display: "flex", marginLeft: 20, fontSize: 40, letterSpacing: 8 }}>AURA</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", fontSize: 100, lineHeight: 1.05 }}>Say something.</div>
          <div style={{ display: "flex", fontSize: 100, lineHeight: 1.05, color: "#40719e" }}>Hear what to fix.</div>
        </div>

        <div style={{ display: "flex", fontSize: 30, color: "#2b2b2b" }}>
          An AI English speaking coach · 6 companions · 7 scenarios · 7 speaking styles
        </div>
      </div>
    ),
    { ...size }
  );
}
