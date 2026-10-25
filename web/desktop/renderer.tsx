import { createRoot } from "react-dom/client";
import CalculatorApp from "../app/CalculatorApp";
import "../app/globals.css";
import "./desktop.css";

createRoot(document.getElementById("root")!).render(<CalculatorApp desktop={window.vericivilDesktop} />);
