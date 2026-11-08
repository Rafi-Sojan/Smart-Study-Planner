import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import App from "./App";

afterEach(() => {
  vi.unstubAllGlobals();
});

it("shows the protected sign-in screen when the API requires a browser session", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          authentication_required: true,
          browser_login_enabled: true,
          authenticated: false,
          username: null,
          expires_at: null,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ),
  );

  render(<App />);

  expect(await screen.findByRole("heading", { name: /sign in to continue/i })).toBeVisible();
  expect(screen.getByText(/api key is never stored/i)).toBeVisible();
});

it("shows every model allowlisted by the API catalog", async () => {
  const response = (body: unknown) =>
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/v1/session")) {
        return response({
          authentication_required: false,
          browser_login_enabled: false,
          authenticated: true,
          username: null,
          expires_at: null,
        });
      }
      if (url.endsWith("/v1/models")) {
        return response({
          default_model_id: "early-30",
          models: [
            {
              model_id: "early-30",
              label: "30-day early warning",
              description: "Earlier support window",
              dataset: "OULAD",
              cutoff_days: 30,
              model_version: "early/1",
              threshold: 0.35,
              feature_count: 1,
              is_default: true,
            },
            {
              model_id: "balanced-60",
              label: "60-day balanced model",
              description: "Additional mid-course evidence",
              dataset: "OULAD",
              cutoff_days: 60,
              model_version: "balanced/2",
              threshold: 0.42,
              feature_count: 1,
              is_default: false,
            },
          ],
        });
      }
      if (url.includes("/v1/model-metadata")) {
        return response({
          model_id: "early-30",
          label: "30-day early warning",
          description: "Earlier support window",
          dataset: "OULAD",
          cutoff_days: 30,
          model_version: "early/1",
          model_source: "models:/early/1",
          registry_name: "early",
          registry_version: "1",
          threshold: 0.35,
          threshold_source: "mlflow_registry_tag",
          feature_count: 1,
          feature_names: ["activity_count"],
          feature_fields: [{ name: "activity_count", kind: "number", required: true }],
          feature_contract_sha256: "a".repeat(64),
        });
      }
      throw new Error(`Unexpected URL: ${url}`);
    }),
  );

  render(<App />);

  expect(await screen.findByRole("heading", { name: /build a plan around your week/i })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: /admin \/ model testing/i }));
  const selector = await screen.findByRole("combobox", { name: /risk model/i });
  expect(selector).toHaveValue("early-30");
  expect(screen.getByRole("option", { name: /30-day early warning/i })).toBeVisible();
  expect(screen.getByRole("option", { name: /60-day balanced model/i })).toBeVisible();
});

it("uses a student-friendly intake without loading model metadata by default", async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        authentication_required: false,
        browser_login_enabled: false,
        authenticated: true,
        username: null,
        expires_at: null,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  expect(await screen.findByRole("heading", { name: /build a plan around your week/i })).toBeVisible();
  expect(screen.getByRole("heading", { name: /tell us what you are planning/i })).toBeVisible();
  expect(screen.getByRole("textbox", { name: /^subjects/i })).toBeVisible();
  expect(screen.getByRole("button", { name: /generate my study plan/i })).toBeVisible();
  expect(screen.queryByText(/contract name:/i)).not.toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/v1\/session$/);
});
