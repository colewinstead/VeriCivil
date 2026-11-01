/* eslint-disable @next/next/no-img-element -- authentic local calculator captures are deliberately displayed directly */
import calculators from "./generated/calculators.json";

const calculatorImages: Record<string, { src: string; alt: string }> = {
  typicals: {
    src: "/showcase/typicals-editor.webp",
    alt: "VeriCivil Typicals editor with editable roadway components and an engineering section",
  },
  superelevation: {
    src: "/showcase/calculator-ui.png",
    alt: "Superelevation Calculator browser workspace",
  },
  crushed_stone_base: {
    src: "/showcase/stone-base-results.png",
    alt: "Crushed Stone Base Calculator showing equivalent keyout width and tonnage results",
  },
};

export default function CalculatorCards() {
  return (
    <div className="calculator-card-grid">
      {calculators.map((calculator) => (
        <a className={`calculator-card calculator-card-${calculator.id}`} href={calculator.route} key={calculator.id}>
          <div className="calculator-card-topline">
            <span>{calculator.category}</span>
            <b>{calculator.access}</b>
          </div>
          <div className="calculator-card-image">
            <img src={calculatorImages[calculator.id].src} alt={calculatorImages[calculator.id].alt} loading="lazy" />
          </div>
          <h3>{calculator.short_title}</h3>
          <p>{calculator.description}</p>
          <div className="calculator-card-action"><span>{calculator.id === "typicals" ? "Open section designer" : calculator.id === "superelevation" ? "Open professional workspace" : "Open free quantity tool"}</span><b>↗</b></div>
        </a>
      ))}
    </div>
  );
}
