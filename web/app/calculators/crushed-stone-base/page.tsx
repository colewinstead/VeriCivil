import type { Metadata } from "next";
import CrushedStoneBaseCalculator from "../../CrushedStoneBaseCalculator";
import SiteHeader from "../../SiteHeader";

export const metadata: Metadata = {
  alternates: { canonical: "https://vericivil.com/calculators/crushed-stone-base" },
  title: "Crushed Stone Base Tonnage Calculator",
  description: "Estimate compacted crushed stone roadway base volume and order tons across multiple construction segments.",
};

export default function CrushedStoneBasePage() {
  return <><SiteHeader compact /><CrushedStoneBaseCalculator /></>;
}
