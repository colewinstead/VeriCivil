import { createRoot } from "react-dom/client";
import CalculatorApp from "../app/CalculatorApp";
import TypicalsApp from "../app/TypicalsApp";
import "../app/globals.css";
import "./desktop.css";

if (window.location.hash === "#typicals") document.title = "Typicals · VeriCivil Desktop Preview";
createRoot(document.getElementById("root")!).render(window.location.hash === "#typicals" ? <TypicalsApp desktop={window.vericivilDesktop} /> : <CalculatorApp desktop={window.vericivilDesktop} />);
