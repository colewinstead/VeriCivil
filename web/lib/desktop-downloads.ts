export const DESKTOP_RELEASES = "https://github.com/colewinstead/VeriCivil/releases/latest";
type Asset = { name: string; browser_download_url: string };
export type DesktopDownload = { label: string; url: string; filename: string; unsigned: boolean; portable: boolean };

export function desktopDownloads(value: unknown): { version: string; downloads: DesktopDownload[] } | null {
  if (!value || typeof value !== "object") return null;
  const release = value as { tag_name?: unknown; draft?: unknown; prerelease?: unknown; assets?: unknown };
  if (typeof release.tag_name !== "string" || !/^v\d+\.\d+\.\d+$/.test(release.tag_name) || release.draft || release.prerelease || !Array.isArray(release.assets)) return null;
  const version = release.tag_name.slice(1);
  const base = `https://github.com/colewinstead/VeriCivil/releases/download/${release.tag_name}/`;
  const assets = release.assets.filter((asset): asset is Asset => !!asset && typeof asset.name === "string" && typeof asset.browser_download_url === "string" && asset.browser_download_url === base + asset.name);
  const downloads: DesktopDownload[] = [];
  for (const [label, os, arch, legacy] of [
    ["Windows x64", "win", "x64", "Windows-x64.zip"],
    ["Mac · Apple Silicon", "mac", "arm64", "macOS-Apple-Silicon.dmg"],
    ["Mac · Intel", "mac", "x64", "macOS-Intel.dmg"],
  ]) {
    const prefix = `VeriCivil-Superelevation-${version}-${os}-${arch}`;
    const extension = os === "win" ? "exe" : "dmg";
    const names = [`${prefix}.${extension}`, `${prefix}-unsigned.${extension}`, `Superelevation-Desktop-Preview-${version}-${legacy}`];
    const asset = names.map(name => assets.find(asset => asset.name === name)).find(Boolean);
    if (asset) downloads.push({ label, url: asset.browser_download_url, filename: asset.name, unsigned: asset.name.includes("-unsigned.") || asset.name.startsWith("Superelevation-Desktop-Preview-"), portable: asset.name.endsWith(".zip") });
  }
  return { version, downloads };
}

let cache: { expires: number; release: ReturnType<typeof desktopDownloads> } | undefined;
export async function latestDesktopDownloads() {
  if (cache && cache.expires > Date.now()) return cache.release;
  try {
    const response = await fetch("https://api.github.com/repos/colewinstead/VeriCivil/releases/latest", { headers: { Accept: "application/vnd.github+json", "User-Agent": "VeriCivil-downloads" }, signal: AbortSignal.timeout(7000) });
    if (!response.ok) throw new Error("Release lookup unavailable");
    const release = desktopDownloads(await response.json());
    if (!release) throw new Error("Release data unavailable");
    cache = { expires: Date.now() + 5 * 60 * 1000, release };
    return release;
  } catch { return cache?.release || null; }
}
