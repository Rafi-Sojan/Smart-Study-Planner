import { coerceFeatureValue, humanizeFeatureName, riskBand } from "./utils";

describe("frontend input helpers", () => {
  it("renders model feature names as readable labels", () => {
    expect(humanizeFeatureName("assessment_mean")).toBe("Assessment Mean");
  });

  it("preserves categories while coercing numeric and missing values", () => {
    expect(coerceFeatureValue("64.5", "number")).toBe(64.5);
    expect(coerceFeatureValue("AAA", "string")).toBe("AAA");
    expect(coerceFeatureValue("  ", "number")).toBeNull();
  });

  it("uses the configured operating threshold for status text", () => {
    expect(riskBand(0.6, 0.5)).toBe("Support review suggested");
    expect(riskBand(0.2, 0.5)).toBe("No alert at this threshold");
  });
});
