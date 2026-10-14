/* Pyodide curve records are JSON dictionaries. */
/* eslint-disable @typescript-eslint/no-explicit-any */
type Dict = Record<string, any>;
export type LandxmlInputs = { shared: Dict; curves: Record<string, Dict> };

export function editLandxmlInputs(state: LandxmlInputs, changes: Dict, index: number, scope: string, selected: number[]): LandxmlInputs {
  const curves = { ...state.curves };
  for (const target of scope === "curve" ? [index] : selected) {
    curves[target] = { ...curves[target], ...changes };
  }
  return { shared: scope === "curve" ? state.shared : { ...state.shared, ...changes }, curves };
}

export function curveInputValues(curve: Dict): Dict {
  const values = curve.results.inputs || {};
  const restored: Dict = {
    ...values, ...curve.meta, manual_spiral_length_check: false,
    criteria_profile: values.criteria_profile ?? curve.results.calculation_metadata?.criteria?.profile_id ?? "mdot-rdsd-2026-04-22",
    circular_placement_basis: values.circular_placement_basis ?? "runoff",
    pc: values.pc ?? "", pt: values.pt ?? "", speed: String(values.speed_mph ?? ""), radius: String(values.radius_ft ?? ""),
    facility: values.facility ?? "centerline", area: values.area_type ?? "rural", lane_width: String(values.lane_width_ft ?? "12"),
    lanes_rotated: String(values.lanes_rotated ?? "2"), e_manual: values.e_manual == null ? "" : String(values.e_manual),
    friction: values.friction_input ?? "", rel_grad: values.relative_gradient_input ?? "", normal_crown: String(values.normal_crown ?? "0.02"),
    Lr_manual: values.Lr_manual == null ? "" : String(values.Lr_manual), Lt_manual: values.Lt_manual == null ? "" : String(values.Lt_manual),
    curve_notes: curve.notes || "",
  };
  delete restored.project_name;
  delete restored.route_name;
  return restored;
}
