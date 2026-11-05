"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { DesktopHost, DesktopUpdate } from "../lib/desktop";

function releaseNotesText(notes: string) {
  // Template contents stay inert; only text reaches React, never remote HTML.
  const template = document.createElement("template");
  template.innerHTML = notes;
  template.content.querySelectorAll("script, style, template, noscript, iframe, object").forEach(element => element.remove());
  template.content.querySelectorAll("br").forEach(element => element.replaceWith("\n"));
  template.content.querySelectorAll("p, div, h1, h2, h3, h4, h5, h6, li, blockquote, pre, tr").forEach(element => {
    if (element.tagName === "LI") element.prepend("• ");
    element.append("\n");
  });
  return (template.content.textContent || "").replace(/[ \t]*\n\s*/g, "\n").trim();
}

export default function DesktopUpdates({ host, open, onClose }: { host: DesktopHost; open: boolean; onClose(): void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [state, setState] = useState<DesktopUpdate>({ status: "idle", version: "" });
  const [error, setError] = useState("");
  const notes = useMemo(() => state.notes ? releaseNotesText(state.notes) : "", [state.notes]);
  useEffect(() => {
    const stop = host.onUpdate(setState);
    host.updateState().then(setState).catch(() => setError("Could not read update status. Try again from Help."));
    return stop;
  }, [host]);
  useEffect(() => {
    if (open) dialog.current?.showModal();
    else dialog.current?.close();
  }, [open]);
  const action = async (value: "check" | "download" | "install") => {
    setError("");
    try { setState(await host.updateAction(value)); }
    catch { setError("The update service could not respond. Your current app is unchanged."); }
  };
  const descriptions: Record<string, string> = {
    idle: "Check for a newer version of VeriCivil.", checking: "Checking for updates…", current: "You have the latest version.",
    available: `Version ${state.nextVersion} is available.`, downloading: "Downloading update…", downloaded: `Version ${state.nextVersion} is ready to install.`, installing: "Restarting to install…",
  };
  return <dialog className="desktop-update-dialog" ref={dialog} aria-labelledby="desktop-update-title" onCancel={onClose}>
    <h2 id="desktop-update-title">VeriCivil updates</h2>
    <p>Installed version {state.version || "…"}</p>
    <p role="status">{state.message || descriptions[state.status]}</p>
    {state.status === "downloading" && <><progress value={state.percent || 0} max="100" aria-label="Update download" /><p>{Math.round(state.percent || 0)}%</p></>}
    {notes && <details><summary>Release notes</summary><p className="update-notes">{notes}</p></details>}
    {error && <p role="alert">{error}</p>}
    <div className="desktop-update-actions">
      {["idle", "current", "error"].includes(state.status) && <button onClick={() => void action("check")}>Check for updates</button>}
      {state.status === "available" && <button onClick={() => void action("download")}>Download update</button>}
      {state.status === "downloaded" && <button onClick={() => void action("install")}>Restart and install</button>}
      {["disabled", "manual"].includes(state.status) && <><button onClick={() => void action("check")}>Check for updates</button><button onClick={() => void host.openDownloads().catch(() => setError("Could not open your browser. Visit vericivil.com/downloads."))}>Get latest download</button></>}
      <button autoFocus onClick={onClose}>Close</button>
    </div>
  </dialog>;
}
