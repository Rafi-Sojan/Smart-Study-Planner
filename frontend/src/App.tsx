import { FormEvent, useEffect, useMemo, useState } from "react";

import { ApiError, api } from "./api";
import type {
  AvailabilityDraft,
  FeatureField,
  FeatureValue,
  ModelCatalog,
  ModelMetadata,
  ModelOption,
  OptionalNumberDraft,
  RiskResponse,
  SessionState,
  StudentIntakeDraft,
  StudentIntakePayload,
  StudentStudyPlanResponse,
  TaskDraft,
} from "./types";
import {
  coerceFeatureValue,
  formatDateTime,
  humanizeFeatureName,
  localDateTime,
  riskBand,
  toIsoDateTime,
} from "./utils";

type WorkspaceMode = "student" | "admin";

const CONTEXT_FEATURE = /(gender|region|education|age|disabil|imd|cgpa|programme|course|module)/i;

function blankTask(index = 1): TaskDraft {
  return {
    task_id: `task-${index}`,
    title: "",
    subject: "",
    deadline: localDateTime(48),
    estimated_minutes: 90,
    completed_minutes: 0,
    difficulty: 3,
    importance: 3,
  };
}

function blankAvailability(): AvailabilityDraft {
  return { start: localDateTime(2), end: localDateTime(4) };
}

function blankStudentIntake(): StudentIntakeDraft {
  return {
    primary_goal: "build_consistency",
    subjects: "",
    course_type: "theory",
    current_term: 1,
    current_credit_load: "",
    previous_cgpa: "",
    recent_score_percent: "",
    attendance_percent: "",
    submission_rate_percent: "",
    weekly_study_hours: "",
    confidence_level: "",
    sleep_hours: "",
    stress_level: "",
    fatigue_level: "",
    concentration_level: "",
  };
}

function numberDraft(value: string): OptionalNumberDraft {
  return value === "" ? "" : Number(value);
}

function optionalNumber(value: OptionalNumberDraft): number | null {
  return value === "" ? null : value;
}

function requiredNumber(value: OptionalNumberDraft, label: string): number {
  if (value === "") throw new Error(`Enter ${label}.`);
  return value;
}

function studentIntakePayload(intake: StudentIntakeDraft): StudentIntakePayload {
  const subjects = intake.subjects
    .split(",")
    .map((subject) => subject.trim())
    .filter(Boolean);
  if (!subjects.length) throw new Error("Enter at least one subject.");
  return {
    primary_goal: intake.primary_goal,
    subjects,
    course_type: intake.course_type,
    current_term: intake.current_term,
    current_credit_load: optionalNumber(intake.current_credit_load),
    previous_cgpa: optionalNumber(intake.previous_cgpa),
    recent_score_percent: optionalNumber(intake.recent_score_percent),
    attendance_percent: optionalNumber(intake.attendance_percent),
    submission_rate_percent: optionalNumber(intake.submission_rate_percent),
    weekly_study_hours: optionalNumber(intake.weekly_study_hours),
    confidence_level: optionalNumber(intake.confidence_level),
    sleep_hours: requiredNumber(intake.sleep_hours, "typical sleep hours"),
    stress_level: requiredNumber(intake.stress_level, "a stress rating"),
    fatigue_level: requiredNumber(intake.fatigue_level, "a fatigue rating"),
    concentration_level: requiredNumber(intake.concentration_level, "a concentration rating"),
  };
}

function errorText(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "An unexpected error occurred.";
}

interface LoginViewProps {
  session: SessionState;
  busy: boolean;
  error: string | null;
  onLogin: (username: string, password: string) => Promise<void>;
}

function LoginView({ session, busy, error, onLogin }: LoginViewProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    await onLogin(username, password);
  }

  return (
    <main className="login-shell">
      <section className="login-brand" aria-labelledby="welcome-title">
        <p className="eyebrow">Evidence-aware academic support</p>
        <h1 id="welcome-title">Smart Study Planner</h1>
        <p className="login-lead">
          Review early academic-risk signals, organise competing tasks, and build a
          capacity-aware schedule that keeps a human reviewer in control.
        </p>
        <div className="principle-grid">
          <article>
            <span aria-hidden="true">01</span>
            <h2>Assess</h2>
            <p>Use only the inputs exposed by the approved model contract.</p>
          </article>
          <article>
            <span aria-hidden="true">02</span>
            <h2>Prioritise</h2>
            <p>Balance deadline, importance, difficulty, and available time.</p>
          </article>
          <article>
            <span aria-hidden="true">03</span>
            <h2>Review</h2>
            <p>Treat every alert and plan as decision support, not an automatic verdict.</p>
          </article>
        </div>
      </section>

      <section className="login-panel" aria-labelledby="sign-in-title">
        <div className="brand-mark" aria-hidden="true">SP</div>
        <p className="eyebrow">Protected workspace</p>
        <h2 id="sign-in-title">Sign in to continue</h2>
        <p className="muted">
          Your browser receives a short-lived secure session. The service API key is never
          stored in this page.
        </p>
        {!session.browser_login_enabled ? (
          <div className="notice danger" role="alert">
            Browser login is not configured. Set the documented authentication variables on
            the API service before using this interface.
          </div>
        ) : (
          <form className="login-form" onSubmit={submit}>
            <label>
              Username
              <input
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </label>
            {error && <div className="notice danger" role="alert">{error}</div>}
            <button className="button primary full" type="submit" disabled={busy}>
              {busy ? "Signing in…" : "Sign in securely"}
            </button>
          </form>
        )}
        <p className="privacy-note">
          Do not enter names, student identifiers, credentials, or free-text wellbeing data.
        </p>
      </section>
    </main>
  );
}

interface StudentIntakeFormProps {
  intake: StudentIntakeDraft;
  onChange: (patch: Partial<StudentIntakeDraft>) => void;
}

function StudentIntakeForm({ intake, onChange }: StudentIntakeFormProps) {
  return (
    <section className="editor-section student-intake">
      <div className="section-heading">
        <div>
          <p className="step">Step 1</p>
          <h2>Tell us what you are planning</h2>
          <p>
            Use familiar study information only. Do not enter your name, registration
            number, credentials, or private notes.
          </p>
        </div>
        <span className="count-badge">Student input</span>
      </div>

      <div className="field-grid three">
        <label className="field">
          <span>Primary goal</span>
          <select
            value={intake.primary_goal}
            onChange={(event) => onChange({ primary_goal: event.target.value as StudentIntakeDraft["primary_goal"] })}
          >
            <option value="build_consistency">Build a consistent routine</option>
            <option value="prepare_for_exams">Prepare for exams</option>
            <option value="complete_assignments">Complete assignments</option>
            <option value="recover_missed_work">Recover missed work</option>
            <option value="balance_subjects">Balance several subjects</option>
          </select>
        </label>
        <label className="field">
          <span>Subjects</span>
          <input
            value={intake.subjects}
            onChange={(event) => onChange({ subjects: event.target.value })}
            placeholder="Mathematics, Physics"
            required
          />
          <small>Separate multiple subjects with commas.</small>
        </label>
        <label className="field">
          <span>Course style</span>
          <select
            value={intake.course_type}
            onChange={(event) => onChange({ course_type: event.target.value as StudentIntakeDraft["course_type"] })}
          >
            <option value="theory">Mostly theory</option>
            <option value="theory_lab">Theory and laboratory</option>
            <option value="theory_project">Theory and project</option>
            <option value="elective">Elective</option>
            <option value="other">Other / mixed</option>
          </select>
        </label>
        <label className="field">
          <span>Current semester or term</span>
          <input
            type="number"
            min="1"
            max="12"
            value={intake.current_term}
            onChange={(event) => onChange({ current_term: Number(event.target.value) })}
            required
          />
        </label>
      </div>

      <div className="subsection-heading">
        <div>
          <h3>Academic snapshot for this demonstration</h3>
          <p>
            These optional estimates are understandable stand-ins while no university LMS is
            connected. Verified institutional values should replace them in production.
          </p>
        </div>
        <span>Optional</span>
      </div>
      <div className="field-grid three">
        <label className="field"><span>Previous CGPA (0–10)</span><input type="number" min="0" max="10" step="0.01" value={intake.previous_cgpa} onChange={(event) => onChange({ previous_cgpa: numberDraft(event.target.value) })} placeholder="7.5" /></label>
        <label className="field"><span>Recent average (%)</span><input type="number" min="0" max="100" step="0.1" value={intake.recent_score_percent} onChange={(event) => onChange({ recent_score_percent: numberDraft(event.target.value) })} placeholder="68" /></label>
        <label className="field"><span>Attendance estimate (%)</span><input type="number" min="0" max="100" step="0.1" value={intake.attendance_percent} onChange={(event) => onChange({ attendance_percent: numberDraft(event.target.value) })} placeholder="82" /></label>
        <label className="field"><span>Assignments submitted (%)</span><input type="number" min="0" max="100" step="0.1" value={intake.submission_rate_percent} onChange={(event) => onChange({ submission_rate_percent: numberDraft(event.target.value) })} placeholder="75" /></label>
        <label className="field"><span>Independent study per week (hours)</span><input type="number" min="0" max="100" step="0.5" value={intake.weekly_study_hours} onChange={(event) => onChange({ weekly_study_hours: numberDraft(event.target.value) })} placeholder="8" /></label>
        <label className="field"><span>Current credit load</span><input type="number" min="0" max="60" step="0.5" value={intake.current_credit_load} onChange={(event) => onChange({ current_credit_load: numberDraft(event.target.value) })} placeholder="20" /></label>
        <label className="field"><span>Confidence with current subjects (1–5)</span><input type="number" min="1" max="5" value={intake.confidence_level} onChange={(event) => onChange({ confidence_level: numberDraft(event.target.value) })} placeholder="3" /></label>
      </div>

      <div className="subsection-heading">
        <div><h3>Wellbeing context</h3><p>Required for wellbeing-aware scheduling. Use simple ratings only; no medical or free-text information is requested.</p></div>
        <span>Required</span>
      </div>
      <div className="field-grid four">
        <label className="field"><span>Typical sleep (hours)</span><input type="number" min="0" max="24" step="0.5" value={intake.sleep_hours} onChange={(event) => onChange({ sleep_hours: numberDraft(event.target.value) })} placeholder="7" required /></label>
        <label className="field"><span>Stress (0–10)</span><input type="number" min="0" max="10" value={intake.stress_level} onChange={(event) => onChange({ stress_level: numberDraft(event.target.value) })} placeholder="5" required /></label>
        <label className="field"><span>Fatigue (0–10)</span><input type="number" min="0" max="10" value={intake.fatigue_level} onChange={(event) => onChange({ fatigue_level: numberDraft(event.target.value) })} placeholder="4" required /></label>
        <label className="field"><span>Concentration (0–10)</span><input type="number" min="0" max="10" value={intake.concentration_level} onChange={(event) => onChange({ concentration_level: numberDraft(event.target.value) })} placeholder="7" required /></label>
      </div>
    </section>
  );
}

interface FeatureInputsProps {
  fields: FeatureField[];
  values: Record<string, string>;
  onChange: (name: string, value: string) => void;
}

function FeatureInputs({ fields, values, onChange }: FeatureInputsProps) {
  const groups = useMemo(
    () => [
      {
        title: "Learner and enrolment context",
        description: "Context fields used by the fitted model and subsequent fairness review.",
        fields: fields.filter((field) => CONTEXT_FEATURE.test(field.name)),
      },
      {
        title: "Academic and engagement signals",
        description: "Measured progress and participation inputs available at the scoring point.",
        fields: fields.filter((field) => !CONTEXT_FEATURE.test(field.name)),
      },
    ].filter((group) => group.fields.length > 0),
    [fields],
  );

  return (
    <div className="feature-groups">
      {groups.map((group) => (
        <section className="feature-group" key={group.title}>
          <div className="section-heading compact">
            <div>
              <h3>{group.title}</h3>
              <p>{group.description}</p>
            </div>
            <span className="count-badge">{group.fields.length} fields</span>
          </div>
          <div className="field-grid">
            {group.fields.map((field) => (
              <label className="field" key={field.name}>
                <span>{humanizeFeatureName(field.name)}</span>
                <input
                  type={field.kind === "number" ? "number" : "text"}
                  step={field.kind === "number" ? "any" : undefined}
                  inputMode={field.kind === "number" ? "decimal" : undefined}
                  value={values[field.name] ?? ""}
                  onChange={(event) => onChange(field.name, event.target.value)}
                  placeholder={field.kind === "string" ? "Enter category" : "Enter value"}
                  aria-describedby={`${field.name}-hint`}
                />
                <small id={`${field.name}-hint`}>
                  Contract name: <code>{field.name}</code> · {field.kind}
                </small>
              </label>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function RiskResult({ result }: { result: RiskResponse }) {
  return (
    <section className={`result-card ${result.alert ? "alert" : "clear"}`} aria-live="polite">
      <div className="score-block">
        <p className="eyebrow">Model output</p>
        <strong>{(result.risk_score * 100).toFixed(1)}%</strong>
        <span>{riskBand(result.risk_score, result.threshold)}</span>
      </div>
      <div className="score-detail">
        <progress max="1" value={result.risk_score} aria-label="Risk score" />
        <dl>
          <div><dt>Operating threshold</dt><dd>{(result.threshold * 100).toFixed(1)}%</dd></div>
          <div><dt>Alert</dt><dd>{result.alert ? "Yes — review" : "No"}</dd></div>
          <div><dt>Model</dt><dd>{result.model_version}</dd></div>
        </dl>
        <p>
          This score ranks support need under the loaded model. It is not a diagnosis,
          probability guarantee, or permission for an automated academic decision.
        </p>
      </div>
    </section>
  );
}

interface TaskEditorProps {
  tasks: TaskDraft[];
  onChange: (index: number, patch: Partial<TaskDraft>) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
}

function TaskEditor({ tasks, onChange, onAdd, onRemove }: TaskEditorProps) {
  return (
    <section className="editor-section">
      <div className="section-heading">
        <div><p className="step">Step 2</p><h3>Tasks and deadlines</h3><p>Add the work you need to schedule. Task IDs are created automatically.</p></div>
        <button className="button secondary" type="button" onClick={onAdd}>+ Add task</button>
      </div>
      <div className="stack">
        {tasks.map((task, index) => (
          <article className="edit-card" key={`${task.task_id}-${index}`}>
            <div className="edit-card-title">
              <h4>Task {index + 1}</h4>
              {tasks.length > 1 && (
                <button className="text-button danger-text" type="button" onClick={() => onRemove(index)}>
                  Remove
                </button>
              )}
            </div>
            <div className="field-grid three">
              <label className="field"><span>Title</span><input value={task.title} onChange={(event) => onChange(index, { title: event.target.value })} required /></label>
              <label className="field"><span>Subject</span><input value={task.subject} onChange={(event) => onChange(index, { subject: event.target.value })} required /></label>
              <label className="field"><span>Deadline</span><input type="datetime-local" value={task.deadline} onChange={(event) => onChange(index, { deadline: event.target.value })} required /></label>
              <label className="field"><span>Estimated minutes</span><input type="number" min="15" max="10080" value={task.estimated_minutes} onChange={(event) => onChange(index, { estimated_minutes: Number(event.target.value) })} required /></label>
              <label className="field"><span>Completed minutes</span><input type="number" min="0" max={task.estimated_minutes} value={task.completed_minutes} onChange={(event) => onChange(index, { completed_minutes: Number(event.target.value) })} required /></label>
              <label className="field"><span>Difficulty (1–5)</span><input type="number" min="1" max="5" value={task.difficulty} onChange={(event) => onChange(index, { difficulty: Number(event.target.value) })} required /></label>
              <label className="field"><span>Importance (1–5)</span><input type="number" min="1" max="5" value={task.importance} onChange={(event) => onChange(index, { importance: Number(event.target.value) })} required /></label>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function PlanResult({ plan }: { plan: StudentStudyPlanResponse }) {
  const taskLookup = new Map(plan.ranked_tasks.map((task) => [task.task_id, task]));
  const supportLabel = plan.alert ? "Support review recommended" : "Standard planning support";
  return (
    <section className="plan-result" aria-live="polite">
      <div className="result-summary">
        <div><p className="eyebrow">Generated plan</p><h3>{plan.sessions.length} focused sessions</h3><p>{Object.values(plan.unscheduled_minutes).reduce((sum, value) => sum + value, 0)} minutes remain unscheduled.</p></div>
        <div className={`status-pill ${plan.alert ? "warning" : "ok"}`}>{supportLabel}</div>
      </div>
      <div className="plan-columns">
        <div>
          <h4>Schedule</h4>
          {plan.sessions.length ? (
            <ol className="timeline">
              {plan.sessions.map((session, index) => (
                <li key={`${session.task_id}-${session.start}-${index}`}>
                  <time>{formatDateTime(session.start)}</time>
                  <strong>{session.title}</strong>
                  <span>{session.subject} · {session.study_minutes} minutes</span>
                </li>
              ))}
            </ol>
          ) : <p className="empty-state">No session fits the supplied availability.</p>}
        </div>
        <div>
          <h4>Priority rationale</h4>
          <div className="stack small">
            {plan.ranked_tasks.map((task, index) => (
              <article className="priority-card" key={task.task_id}>
                <span>#{index + 1}</span>
                <div><strong>{task.title ?? task.task_id}</strong><p>{task.subject ? `${task.subject} · ` : ""}{task.rationale.join(" · ")}</p></div>
                <b>{Math.round(task.priority_score * 100)}</b>
              </article>
            ))}
          </div>
          <h4>Recommendations</h4>
          <ul className="recommendations">
            {plan.recommendations.map((recommendation) => <li key={recommendation}>{recommendation}</li>)}
          </ul>
        </div>
      </div>
      <section className="evidence-summary" aria-labelledby="evidence-summary-title">
        <div>
          <p className="eyebrow">Evidence summary</p>
          <h4 id="evidence-summary-title">
            {plan.evidence.reliability === "partial" ? "Partial demonstration evidence" : "Limited demonstration evidence"}
          </h4>
          <p>{plan.evidence.message}</p>
        </div>
        <dl>
          <div><dt>University/LMS connection</dt><dd>{plan.evidence.institutional_data_connected ? "Connected" : "Not connected"}</dd></div>
          <div><dt>Sources used</dt><dd>{plan.evidence.source_labels.join(", ")}</dd></div>
        </dl>
      </section>
      {plan.human_review_required && (
        <div className="notice review">
          Human review is required. Confirm feasibility, accessibility needs, and student
          preference before acting on this plan.
        </div>
      )}
      <span className="visually-hidden">{taskLookup.size} tasks were ranked.</span>
    </section>
  );
}

export default function App() {
  const [session, setSession] = useState<SessionState | null>(null);
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null);
  const [selectedModelId, setSelectedModelId] = useState("");
  const [metadata, setMetadata] = useState<ModelMetadata | null>(null);
  const [mode, setMode] = useState<WorkspaceMode>("student");
  const [intake, setIntake] = useState<StudentIntakeDraft>(blankStudentIntake());
  const [featureValues, setFeatureValues] = useState<Record<string, string>>({});
  const [tasks, setTasks] = useState<TaskDraft[]>([blankTask()]);
  const [availability, setAvailability] = useState<AvailabilityDraft[]>([blankAvailability()]);
  const [sessionMinutes, setSessionMinutes] = useState(50);
  const [breakMinutes, setBreakMinutes] = useState(10);
  const [risk, setRisk] = useState<RiskResponse | null>(null);
  const [plan, setPlan] = useState<StudentStudyPlanResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fields = useMemo<FeatureField[]>(() => {
    if (!metadata) return [];
    return metadata.feature_fields.length
      ? metadata.feature_fields
      : metadata.feature_names.map((name) => ({ name, kind: "unknown", required: true }));
  }, [metadata]);

  const selectedModel = useMemo<ModelOption | null>(
    () => catalog?.models.find((model) => model.model_id === selectedModelId) ?? null,
    [catalog, selectedModelId],
  );

  async function loadMetadata(modelId: string) {
    const loaded = await api.metadata(modelId);
    setSelectedModelId(modelId);
    setMetadata(loaded);
    setFeatureValues(
      Object.fromEntries(
        (loaded.feature_fields.length
          ? loaded.feature_fields
          : loaded.feature_names.map((name) => ({ name })))
          .map((field) => [field.name, ""]),
      ),
    );
  }

  async function loadCatalog() {
    const loaded = await api.models();
    if (!loaded.models.length) throw new Error("No selectable models are available.");
    setCatalog(loaded);
    await loadMetadata(loaded.default_model_id);
  }

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const state = await api.session();
        if (!active) return;
        setSession(state);
      } catch (caught) {
        if (active) setError(errorText(caught));
      }
    })();
    return () => { active = false; };
  }, []);

  async function login(username: string, password: string) {
    setBusy(true);
    setError(null);
    try {
      const state = await api.login(username, password);
      setSession(state);
      window.scrollTo({ top: 0, behavior: "auto" });
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    setBusy(true);
    try {
      const state = await api.logout();
      setSession(state);
      setCatalog(null);
      setSelectedModelId("");
      setMetadata(null);
      setMode("student");
      setRisk(null);
      setPlan(null);
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(false);
    }
  }

  function parsedFeatures(): Record<string, FeatureValue> {
    return Object.fromEntries(
      fields.map((field) => [
        field.name,
        coerceFeatureValue(featureValues[field.name] ?? "", field.kind),
      ]),
    );
  }

  async function chooseModel(modelId: string) {
    if (modelId === selectedModelId) return;
    setBusy(true);
    setError(null);
    setRisk(null);
    setPlan(null);
    try {
      await loadMetadata(modelId);
      window.scrollTo({ top: 0, behavior: "auto" });
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(false);
    }
  }

  async function enterAdminMode() {
    setMode("admin");
    setError(null);
    setPlan(null);
    if (metadata) return;
    setBusy(true);
    try {
      await loadCatalog();
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(false);
    }
  }

  function enterStudentMode() {
    setMode("student");
    setError(null);
    setRisk(null);
  }

  async function submitRisk(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setRisk(null);
    try {
      if (!selectedModelId) throw new Error("Choose a model before scoring.");
      setRisk(await api.riskScore(selectedModelId, parsedFeatures()));
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(false);
    }
  }

  async function submitStudentPlan(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setPlan(null);
    try {
      const generated = await api.studentStudyPlan({
        intake: studentIntakePayload(intake),
        tasks: tasks.map((task) => ({ ...task, deadline: toIsoDateTime(task.deadline) })),
        availability: availability.map((slot) => ({
          start: toIsoDateTime(slot.start),
          end: toIsoDateTime(slot.end),
        })),
        session_minutes: sessionMinutes,
        break_minutes: breakMinutes,
      });
      setPlan(generated);
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(false);
    }
  }

  if (!session) {
    return <main className="loading-screen"><div className="spinner" /><p>{error ?? "Connecting to the planner…"}</p></main>;
  }
  if (!session.authenticated) {
    return <LoginView session={session} busy={busy} error={error} onLogin={login} />;
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <a className="wordmark" href="#main-content" aria-label="Smart Study Planner home">
          <span>SP</span><div><strong>Smart Study Planner</strong><small>Academic support workspace</small></div>
        </a>
        <div className="header-actions">
          <span className="secure-indicator"><i /> {mode === "student" ? "Student view" : "Admin testing"}</span>
          {session.authentication_required && <button className="text-button" type="button" onClick={logout} disabled={busy}>Sign out</button>}
        </div>
      </header>

      <aside className="sidebar">
        <nav aria-label="Planner sections">
          <p className="nav-label">Workspace</p>
          <button className={mode === "student" ? "active" : ""} onClick={enterStudentMode} type="button"><span>01</span> Student planner</button>
          <button className={mode === "admin" ? "active" : ""} onClick={() => void enterAdminMode()} type="button"><span>02</span> Admin / model testing</button>
        </nav>
        {mode === "student" ? (
          <section className="model-card student-view-card" aria-label="Student experience">
            <p className="nav-label">Student experience</p>
            <strong>Understandable inputs only</strong>
            <span>Goals, subjects, tasks, deadlines, and availability</span>
            <span>Model columns are derived by the backend</span>
          </section>
        ) : (
          <section className="model-card" aria-label="Loaded model">
            <p className="nav-label">Serving contract</p>
            {metadata ? <><strong>{metadata.label}</strong><span>{metadata.model_version}</span><span>{metadata.feature_count} required features</span><span>Threshold {(metadata.threshold * 100).toFixed(1)}%</span><code title={metadata.feature_contract_sha256}>{metadata.feature_contract_sha256.slice(0, 12)}…</code></> : <p>No model metadata available.</p>}
          </section>
        )}
        <section className="sidebar-note"><strong>Research boundary</strong><p>Outputs support a reviewed intervention. They must not determine grades, admission, discipline, or financial aid.</p></section>
      </aside>

      <main id="main-content" className="workspace">
        {mode === "student" ? (
          <>
            <div className="workspace-heading">
              <div><p className="eyebrow">Personal study planning</p><h1>Build a plan around your week</h1><p>Tell us what you want to achieve, what is due, and when you can study. Technical model inputs stay behind the scenes.</p></div>
              <span className="status-pill ok">Student-friendly</span>
            </div>

            <section className="evidence-flow" aria-label="How information is used">
              <div><span>1</span><strong>You provide</strong><p>Goals, tasks, deadlines, wellbeing, and preferences</p></div>
              <div><span>2</span><strong>University provides</strong><p>Verified records when an LMS is connected</p></div>
              <div><span>3</span><strong>Backend derives</strong><p>The exact approved model inputs</p></div>
              <div><span>4</span><strong>Planner returns</strong><p>A reviewable, capacity-aware schedule</p></div>
            </section>

            <form onSubmit={submitStudentPlan}>
              <StudentIntakeForm intake={intake} onChange={(patch) => setIntake((current) => ({ ...current, ...patch }))} />
              <TaskEditor tasks={tasks} onChange={(index, patch) => setTasks((current) => current.map((task, taskIndex) => taskIndex === index ? { ...task, ...patch } : task))} onAdd={() => setTasks((current) => [...current, blankTask(current.length + 1)])} onRemove={(index) => setTasks((current) => current.filter((_, taskIndex) => taskIndex !== index))} />
              <section className="editor-section">
                <div className="section-heading"><div><p className="step">Step 3</p><h3>Availability and focus cycle</h3><p>Add the real windows in which you can study.</p></div><button className="button secondary" type="button" onClick={() => setAvailability((current) => [...current, blankAvailability()])}>+ Add window</button></div>
                <div className="stack">
                  {availability.map((slot, index) => (
                    <article className="edit-card inline" key={`${slot.start}-${index}`}>
                      <label className="field"><span>Available from</span><input type="datetime-local" value={slot.start} onChange={(event) => setAvailability((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, start: event.target.value } : item))} required /></label>
                      <label className="field"><span>Available until</span><input type="datetime-local" value={slot.end} onChange={(event) => setAvailability((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, end: event.target.value } : item))} required /></label>
                      {availability.length > 1 && <button className="text-button danger-text" type="button" onClick={() => setAvailability((current) => current.filter((_, itemIndex) => itemIndex !== index))}>Remove</button>}
                    </article>
                  ))}
                </div>
                <div className="field-grid cycle-grid">
                  <label className="field"><span>Preferred study session (minutes)</span><input type="number" min="15" max="120" value={sessionMinutes} onChange={(event) => setSessionMinutes(Number(event.target.value))} /></label>
                  <label className="field"><span>Break between sessions (minutes)</span><input type="number" min="0" max="30" value={breakMinutes} onChange={(event) => setBreakMinutes(Number(event.target.value))} /></label>
                </div>
              </section>

              {error && <div className="notice danger" role="alert">{error}</div>}
              <div className="submit-bar"><p>The backend derives model inputs. Your payload is not written to application logs.</p><button className="button primary" type="submit" disabled={busy}>{busy ? "Building your plan…" : "Generate my study plan"}</button></div>
            </form>

            {plan && <PlanResult plan={plan} />}
          </>
        ) : (
          <>
            <div className="workspace-heading">
              <div><p className="eyebrow">Administrator workspace</p><h1>Test an approved model contract</h1><p>Inspect registered model metadata and submit exact fitted features for controlled testing.</p></div>
              <span className="status-pill warning">Restricted testing</span>
            </div>
            <div className="notice review admin-banner">
              This interface is for authorised operators and model validation. Institutional
              deployment still requires role-based access control and audited use.
            </div>

            {!metadata ? (
              <section className="empty-panel">
                <h2>{busy ? "Loading the model contract…" : "Model contract is unavailable"}</h2>
                <p>{error ?? "Choose retry to load the allowlisted administrator catalog."}</p>
                <button className="button primary" type="button" disabled={busy} onClick={() => loadCatalog().catch((caught) => setError(errorText(caught)))}>Retry</button>
              </section>
            ) : (
              <>
                <section className="model-picker" aria-labelledby="model-picker-title">
                  <div className="model-picker-copy">
                    <p className="step">Step 1</p>
                    <h2 id="model-picker-title">Choose an approved model</h2>
                    <p>Only deployment-allowlisted models are available to this testing interface.</p>
                  </div>
                  <div className="model-picker-control">
                    <label htmlFor="risk-model">Risk model</label>
                    <select id="risk-model" value={selectedModelId} onChange={(event) => void chooseModel(event.target.value)} disabled={busy}>
                      {catalog?.models.map((model) => (
                        <option value={model.model_id} key={model.model_id}>{model.label}{model.is_default ? " — recommended" : ""}</option>
                      ))}
                    </select>
                    {selectedModel && (
                      <div className="model-option-detail" aria-live="polite">
                        <strong>{selectedModel.label}</strong>
                        <p>{selectedModel.description}</p>
                        <div className="model-tags">
                          {selectedModel.dataset && <span>{selectedModel.dataset}</span>}
                          {selectedModel.cutoff_days && <span>Day {selectedModel.cutoff_days}</span>}
                          <span>{selectedModel.feature_count} inputs</span>
                          <span>Threshold {(selectedModel.threshold * 100).toFixed(1)}%</span>
                        </div>
                      </div>
                    )}
                  </div>
                </section>

                <form onSubmit={submitRisk}>
                  <section className="editor-section">
                    <div className="section-heading"><div><p className="step">Step 2</p><h2>Raw model input contract</h2><p>Exact internal fields are shown only in this administrator testing mode.</p></div><span className="count-badge">{fields.length} features</span></div>
                    <FeatureInputs fields={fields} values={featureValues} onChange={(name, value) => setFeatureValues((current) => ({ ...current, [name]: value }))} />
                  </section>
                  {error && <div className="notice danger" role="alert">{error}</div>}
                  <div className="submit-bar"><p>Review the complete fitted contract before testing.</p><button className="button primary" type="submit" disabled={busy}>{busy ? "Working…" : "Calculate test risk score"}</button></div>
                </form>
                {risk && <RiskResult result={risk} />}
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}
