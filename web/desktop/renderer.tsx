import { createRoot } from "react-dom/client";
import type { DesktopBranding } from "../lib/desktop";
import CalculatorApp from "../app/CalculatorApp";
import "../app/globals.css";
import "./desktop.css";

declare const __DESKTOP_BRANDING__: DesktopBranding;

createRoot(document.getElementById("root")!).render(<CalculatorApp desktop={window.vericivilDesktop} desktopBranding={__DESKTOP_BRANDING__} />);
