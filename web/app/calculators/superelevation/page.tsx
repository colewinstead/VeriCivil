import type { Metadata } from "next";
import CalculatorApp from "../../CalculatorApp";

export const metadata: Metadata = {
  alternates: { canonical: "https://vericivil.com/calculators/superelevation" },
  title: "Superelevation Calculator",
  description: "Run roadway superelevation calculations and CAD-ready exports privately in your browser.",
};

export default function SuperelevationCalculatorPage() {
  return <CalculatorApp />;
}
