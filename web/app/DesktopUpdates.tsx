"use client";

import { useEffect, useRef, useState } from "react";
import type { DesktopHost, DesktopUpdate } from "../lib/desktop";

export default function DesktopUpdates({ host, open, onClose }: { host: DesktopHost; open: boolean; onClose(): void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [state, setState] = useState<DesktopUpdate>({ status: "idle", version: "" });
  const [error, setError] = useState("");
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
    {state.notes && <details><summary>Release notes</summary><p className="update-notes">{state.notes}</p></details>}
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
