export function runtimeVersionMatches(actual: { application_version?: string; calculation_engine_version?: string } | undefined,
  expected: { application_version: string; calculation_engine_version: string }): boolean {
  return actual?.application_version === expected.application_version
    && actual?.calculation_engine_version === expected.calculation_engine_version;
}
