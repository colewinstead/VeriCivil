import type { Metadata } from "next";
import GuardrailCalculator from "../../GuardrailCalculator";
import SiteHeader from "../../SiteHeader";
import SiteFooter from "../../SiteFooter";

export const metadata: Metadata = {
  alternates: { canonical: "https://vericivil.com/calculators/guardrail" },
  title: "Guardrail Length-of-Need Calculator",
  description: "Calculate near-side and opposing-side guardrail lengths using the shared Guardrail Python engine. Save projects and download PDF calculation sheets with optional MDOT references.",
};

export default function GuardrailPage() {
  return <><SiteHeader compact /><GuardrailCalculator /><SiteFooter /></>;
}
