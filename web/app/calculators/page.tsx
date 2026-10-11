import type { Metadata } from "next";
import CalculatorCards from "../CalculatorCards";
import SiteHeader from "../SiteHeader";

export const metadata: Metadata = {
  alternates: { canonical: "https://vericivil.com/calculators" },
  title: "Roadway Calculators",
  description: "Browse VeriCivil roadway design and construction quantity calculators powered by tested Python engines.",
};

export default function CalculatorsPage() {
  return <main className="catalog-shell"><SiteHeader compact /><header className="catalog-header"><p className="marketing-eyebrow"><span /> Calculator directory</p><h1>Focused tools for<br /><em>roadway work.</em></h1><p>Choose a calculator built around visible assumptions, traceable methods, and engineering review.</p></header><section className="catalog-list"><CalculatorCards /></section><div className="engineering-note"><span>ENGINEERING AIDS</span><p>Verify criteria, inputs, assumptions, results, and applicability against governing requirements before use in design or construction.</p></div></main>;
}
