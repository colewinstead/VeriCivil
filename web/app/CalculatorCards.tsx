/* eslint-disable @next/next/no-img-element -- authentic local calculator captures are deliberately displayed directly */
import calculators from "./generated/calculators.json";

const calculatorImages: Record<string, { src: string; alt: string }> = {
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
            {calculator.id === "typicals" ? <svg viewBox="0 0 560 220" role="img" aria-label="Parametric roadway typical section preview"><path d="M40 165 100 120 180 115 280 108 380 115 460 120 520 165 M100 129 180 124 280 117 380 124 460 129 M100 138 180 133 280 126 380 133 460 138" stroke="currentColor" fill="none" strokeWidth="2"/><path d="M180 65H380 M180 55V90 M280 48V144 M380 55V90" stroke="currentColor" fill="none"/><text x="218" y="51" fill="currentColor" fontSize="16">Editable section geometry</text></svg> : <img src={calculatorImages[calculator.id].src} alt={calculatorImages[calculator.id].alt} />}
          </div>
          <h3>{calculator.short_title}</h3>
          <p>{calculator.description}</p>
          <div className="calculator-card-action"><span>{calculator.id === "typicals" ? "Open section designer" : calculator.id === "superelevation" ? "Open professional workspace" : "Open free quantity tool"}</span><b>↗</b></div>
        </a>
      ))}
    </div>
  );
}
