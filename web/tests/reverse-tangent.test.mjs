import assert from "node:assert/strict";
import test from "node:test";
import { reverseTangentRequest } from "../lib/reverse-tangent.ts";

test("reverse advice sends shared section inputs without inherited overrides or geometry", () => {
  const request = reverseTangentRequest({criteria_profile:"aashto", speed:65, radius:4000, reverse_radius:3000,
    roadway:"divided_case_ii", case_ii_geometry_mode:"explicit_radii", pc:"1000", pt:"2000", alignment_type:"spiral",
    e_manual:.06, Lr_manual:100, friction:.1, rel_grad:.005, override_standard_placement:true,
    geometry_provenance:{source:"LandXML"}, landxml_source:{content:"private"},
    case_ii:{left:{lane_count:2, pivot_offset:-12, radius:123, speed:50, Lr_manual:99},
      right:{lane_count:4, pivot_offset:12, e_manual:.08}}});
  assert.equal(request.radius_1,4000);
  assert.equal(request.radius_2,3000);
  assert.deepEqual(request.inputs,{criteria_profile:"aashto",speed:65,roadway:"divided_case_ii",
    case_ii_geometry_mode:"shared_corridor",case_ii:{left:{lane_count:2,pivot_offset:-12},right:{lane_count:4,pivot_offset:12}}});
});
