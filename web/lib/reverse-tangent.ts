/* Engineering calculations remain in the shared Python engine. */
/* eslint-disable @typescript-eslint/no-explicit-any */
type Dict = Record<string, any>;

export function reverseTangentRequest(inputs: Dict) {
  const fields = ["criteria_profile", "speed", "curve_direction", "facility", "area", "lane_width", "lanes_rotated",
    "normal_crown", "max_superelevation", "roadway", "initial_section", "rotation_axis", "lane_widths",
    "crown_from_left", "left_normal_slope", "right_normal_slope", "initial_slope", "aashto_tables",
    "runoff_tangent_percent", "circular_placement_basis", "case_ii_placement_mode"];
  const sideFields = ["lane_count", "lane_width", "pivot_offset", "initial_slope", "runoff_tangent_percent", "circular_placement_basis"];
  return { radius_1: inputs.radius, radius_2: inputs.reverse_radius,
    inputs: { ...Object.fromEntries(fields.filter(key => inputs[key] !== undefined).map(key => [key, inputs[key]])),
      ...(inputs.roadway === "divided_case_ii" ? {case_ii_geometry_mode: "shared_corridor",
        case_ii: Object.fromEntries(["left", "right"].map(side => [side, Object.fromEntries(sideFields
          .filter(key => inputs.case_ii?.[side]?.[key] !== undefined).map(key => [key, inputs.case_ii[side][key]]))]))} : {}) } };
}
