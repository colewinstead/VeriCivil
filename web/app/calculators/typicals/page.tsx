import type { Metadata } from "next";
import TypicalsApp from "../../TypicalsApp";
import SiteHeader from "../../SiteHeader";

export const metadata: Metadata = { title: "VeriCivil Typicals", description: "Parametric rural roadway section drafting preview." };

export default function TypicalsPage() {
  return <><SiteHeader compact /><TypicalsApp /></>;
}
