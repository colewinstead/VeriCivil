export type DesktopHost = {
  preview: true;
  platform: string;
  saveFile(name: string, data: Uint8Array): Promise<"saved" | "cancelled">;
  onMenu(callback: (action: "new" | "open" | "save") => void): () => void;
};

declare global {
  interface Window { vericivilDesktop?: DesktopHost }
}
