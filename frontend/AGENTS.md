# Frontend-specific agent guide

This file applies to `frontend/` in addition to the repository-level guide.

## Student experience

The default interface is a student-friendly intake and planner. Do not expose
the model's engineered feature vector, registry URI, feature hash, or raw model
metadata to students. Raw feature entry and detailed model diagnostics belong in
an explicitly separated administrator/model-testing mode.

Student input includes goals, subjects, tasks, deadlines, availability, session
length, break preferences, and academic context. Sleep, stress, fatigue, and
concentration are compulsory and must be visibly labelled as required. Frontend
validation is usability support; the API remains the authoritative validator.

Display risk output as reviewed support guidance rather than a deterministic or
clinical judgement. Preserve evidence-quality explanations, human-review
language, accessible labels, keyboard operation, responsive layout, and clear
loading/error states.

## Implementation checks

Keep API payload types in `src/types.ts`, request logic in `src/api.ts`, and
behavioural coverage in Vitest. Required fields must be represented in both
TypeScript types and rendered HTML validation.

Run:

```powershell
npm run check
npm test -- --run
npm run build
```

Do not leave the Vite development server running unless the user asks for it.

