export type Point = [number, number];
export type SectionComponent = { id: string; end_point: string; name: string; kind: string; paved: boolean; params: Record<string, number>; points?: Point[] };
export type LibraryItem = { kind: string; label: string; paved?: boolean; fields: Record<string, { label: string; default: number; minimum: number; maximum: number }>; template: SectionComponent };
export type Level = { name: string; description: string; rgb: string | null; lineweight_mm: number | null; bylevel_color: string | null; bylevel_weight: string | null; bylevel_style: string | null; dash_ft: number[] | null };
export type Catalog = { format: string; version: number; source: string; revision: string; extraction_status: string; levels: Level[] };
export type Project = {
  format: string; version: number; units: string; origin: Point; left: SectionComponent[]; right: SectionComponent[];
  metadata: { title: string; route: string; construction: string; stations: string; notes: string[] };
  layers: { id: string; name: string; material: string; thickness_in: number }[]; ground: Point[];
  constraints: { locked_points: Record<string, Point> }; drafting: { scale_ft_per_in: number; text_height_in: number; dimension_gap_in: number; font: string; precision: number };
  print: { monochrome: boolean; width_in: number; height_in: number; lineweights_mm?: Record<string, number> }; annotations: Record<string, Point>;
  level_mappings: Record<string, string>; catalog: Catalog | null;
};
export type Primitive = { kind: "line" | "text" | "circle" | "polygon"; points?: Point[]; text_width?: number; rotation?: number; a: Point; b?: Point; text?: string; height?: number; radius?: number; role: string; component: string };
export type Scene = { bounds: [number, number, number, number]; primitives: Primitive[]; warnings: string[];
  styles: Record<string, { name: string; rgb: string; lineweight_mm: number; dash_ft: number[]; resolved: boolean; plot: boolean }>;
  geometry: { points: Record<string, Point>; layers: { depth_ft: number }[] } };
export type SectionExport = { content_base64: string; report: Record<string, unknown> | null };
