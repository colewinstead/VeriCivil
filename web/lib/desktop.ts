export type DesktopProject = { name: string; content: string; token?: string };
export type DesktopUpdate = {
  status: string;
  version: string;
  nextVersion?: string;
  percent?: number;
  message?: string;
  notes?: string;
};
export type DesktopHost = {
  access: "free";
  platform: string;
  saveFile(name: string, data: Uint8Array, saveAs?: boolean): Promise<"saved" | "cancelled">;
  onMenu(callback: (action: "new" | "open" | "save" | "save-as" | "updates") => void): () => void;
  onProject(callback: (project: DesktopProject) => void): () => void;
  openProjectDialog(): Promise<void>;
  projectOpened(token: string, accepted: boolean): Promise<void>;
  ready(): Promise<DesktopProject | null>;
  newProject(): Promise<void>;
  saveRecovery(content: string | null): Promise<void>;
  resolveRecovery(restored: boolean): Promise<void>;
  workspaceState(dirty: boolean, busy: boolean): Promise<void>;
  reportRuntimeFailure(): Promise<void>;
  onUpdate(callback: (state: DesktopUpdate) => void): () => void;
  updateState(): Promise<DesktopUpdate>;
  updateAction(action: "check" | "download" | "install"): Promise<DesktopUpdate>;
  openDownloads(): Promise<void>;
};

declare global {
  interface Window { vericivilDesktop?: DesktopHost }
}
