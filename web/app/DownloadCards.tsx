"use client";

import { useSyncExternalStore } from "react";

type PreferredPlatform = "windows" | "browser";

const subscribe = () => () => {};

function detectPlatform(): PreferredPlatform {
  const platform = `${navigator.platform} ${navigator.userAgent}`.toLowerCase();
  if (platform.includes("win")) return "windows";
  return "browser";
}

export default function DownloadCards() {
  const preferred = useSyncExternalStore(subscribe, detectPlatform, () => "browser");

  return (
    <div className="download-grid">
      <article className={preferred === "windows" ? "preferred" : ""}>
        {preferred === "windows" && <span className="recommended">Recommended for this device</span>}
        <div className="platform-mark windows-mark" aria-hidden="true"><i /><i /><i /><i /></div>
        <p>WINDOWS 10 / 11 · x64</p>
        <h3>Windows</h3>
        <span>Optional desktop edition</span>
        <a className="download-button" href="/downloads">Windows downloads <b>↗</b></a>
      </article>

      <article className={preferred === "browser" ? "preferred" : ""}>
        {preferred === "browser" && <span className="recommended">Works on this device</span>}
        <div className="platform-mark browser-mark" aria-hidden="true"><i /></div>
        <p>MODERN DESKTOP BROWSER</p>
        <h3>Browser</h3>
        <span>No installation or account</span>
        <a className="download-button browser-button" href="/calculator">Open calculator <b>↗</b></a>
      </article>
    </div>
  );
}
