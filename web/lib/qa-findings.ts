export function groupQaFindings<T extends { code: string; severity: string }>(findings: T[], filter: string) {
  const visible = findings.filter(finding => filter === "all" || finding.severity === filter);
  return {
    actionable: visible.filter(finding => finding.code !== "UNCALCULATED_CURVE")
      .sort((a, b) => Number(b.severity === "block") - Number(a.severity === "block")),
    pending: visible.filter(finding => finding.code === "UNCALCULATED_CURVE"),
  };
}

export function requiresCompoundCalculation(neighbors: number[] | undefined, excluded: number[], hasCalculation: boolean) {
  return !hasCalculation && !!neighbors?.some(index => !excluded.includes(index));
}
