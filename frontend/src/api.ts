import type {
  AvailabilityPayload,
  FeatureValue,
  ModelCatalog,
  ModelMetadata,
  RiskResponse,
  SessionState,
  StudentIntakePayload,
  StudentStudyPlanResponse,
  StudyPlanResponse,
  StudyTaskPayload,
} from "./types";

const API_BASE = "/api";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function errorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          item && typeof item === "object" && "msg" in item
            ? String((item as { msg: unknown }).msg)
            : String(item),
        )
        .join("; ");
    }
  }
  return fallback;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(
      errorMessage(body, `Request failed with status ${response.status}`),
      response.status,
    );
  }
  return body as T;
}

export const api = {
  session: () => request<SessionState>("/v1/session"),
  login: (username: string, password: string) =>
    request<SessionState>("/v1/session", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request<SessionState>("/v1/session/logout", { method: "POST" }),
  models: () => request<ModelCatalog>("/v1/models"),
  metadata: (modelId: string) =>
    request<ModelMetadata>(`/v1/model-metadata?model_id=${encodeURIComponent(modelId)}`),
  riskScore: (modelId: string, features: Record<string, FeatureValue>) =>
    request<RiskResponse>("/v1/risk-score", {
      method: "POST",
      body: JSON.stringify({ model_id: modelId, features }),
    }),
  studyPlan: (payload: {
    model_id: string;
    features: Record<string, FeatureValue>;
    tasks: StudyTaskPayload[];
    availability: AvailabilityPayload[];
    session_minutes: number;
    break_minutes: number;
  }) =>
    request<StudyPlanResponse>("/v1/study-plan", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  studentStudyPlan: (payload: {
    intake: StudentIntakePayload;
    tasks: StudyTaskPayload[];
    availability: AvailabilityPayload[];
    session_minutes: number;
    break_minutes: number;
  }) =>
    request<StudentStudyPlanResponse>("/v1/student-study-plan", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
