/* Python presentation packets retain the shared service's dictionary shape. */
/* eslint-disable @typescript-eslint/no-explicit-any */
type Dict = Record<string, any>;

export function previewStationLabel(frames: Dict[], station: number): string {
  if (!frames.length || station < frames[0].station_ft || station > frames.at(-1)!.station_ft) return "";
  const frame = frames.filter(item => item.station_ft <= station).at(-1)!;
  if (station === frame.station_ft) return frame.station;
  // Python supplies the civil origin and region for each equation-bounded span.
  const civil = frame.civil_station_ft + (station - frame.station_ft);
  const hundreds = Math.floor(civil / 100);
  return `${hundreds}+${(civil - hundreds * 100).toFixed(3).padStart(6, "0")}${frame.station_suffix}`;
}

export function crossSectionPreview(frames: Dict[], station: number): Dict[] | null {
  if (!frames.length || station < frames[0].station_ft || station > frames.at(-1)!.station_ft) return null;
  const index = frames.findIndex(frame => frame.station_ft >= station);
  const right = frames[index];
  const left = frames[Math.max(0, index - 1)];
  const fraction = right.station_ft === left.station_ft ? 0 : (station - left.station_ft) / (right.station_ft - left.station_ft);
  if (!left.segments.length || left.segments.length !== right.segments.length) return null;
  if (left.segments.some((segment: Dict, index: number) => segment.name !== right.segments[index].name)) return null;
  return left.segments.map((segment: Dict, index: number) => {
    const next = right.segments[index];
    const mix = (a: number, b: number) => a + (b - a) * fraction;
    const slope = mix(segment.slope_pct, next.slope_pct);
    const rounded = slope.toFixed(2);
    return { ...segment,
      left: { x: mix(segment.left.x, next.left.x), y: mix(segment.left.y, next.left.y) },
      right: { x: mix(segment.right.x, next.right.x), y: mix(segment.right.y, next.right.y) },
      slope_pct: slope, slope_label: `≈ ${Number(rounded) > 0 ? "+" : ""}${rounded}%`,
    };
  });
}
