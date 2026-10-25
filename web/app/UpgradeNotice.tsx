"use client";

import { useEffect, useRef } from "react";

type UpgradeNoticeProps = {
  feature: string;
  onClose: () => void;
};

export default function UpgradeNotice({ feature, onClose }: UpgradeNoticeProps) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const dismiss = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", dismiss);
    return () => window.removeEventListener("keydown", dismiss);
  }, [onClose]);

  return (
    <div className="upgrade-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className="upgrade-dialog" role="dialog" aria-modal="true" aria-labelledby="upgrade-title" aria-describedby="upgrade-copy">
        <p className="eyebrow">Professional workflow</p>
        <h2 id="upgrade-title">{feature} requires Pro</h2>
        <p id="upgrade-copy">Your current inputs, results, and project state are unchanged.</p>
        <p className="upgrade-privacy">Upgrading will verify account access only. Engineering files and calculations stay on this device.</p>
        <div className="upgrade-actions">
          <button ref={closeRef} onClick={onClose}>Keep calculating</button>
          <a className="primary" href="/account" target="_blank" rel="noreferrer">View Pro options</a>
        </div>
      </section>
    </div>
  );
}
