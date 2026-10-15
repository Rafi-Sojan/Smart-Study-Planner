# EdNet dataset and notebook documentation

## Purpose and scope

EdNet is evaluated as a complementary dataset for a TOEIC-specific adaptive
practice component of Smart Study Planner. It is not a replacement for the
current OULAD academic-risk baseline and it cannot, by itself, implement a
general planner for arbitrary courses. EdNet records learner interactions with
a Korean TOEIC tutoring service; it does not provide a learner's calendar,
availability, deadlines, assignment workload, or a validated measure of
learning gain.

The accompanying analysis is in
[`notebooks/05_ednet_eda.ipynb`](../notebooks/05_ednet_eda.ipynb). The notebook
contains the existing executed tables and figures plus formal explanations of
the statistical unit, visualization choices, feature implications, and limits.
The official release description is available in the
[EdNet README](https://github.com/riiid/ednet/blob/master/README.md).

## Provenance and release structure

EdNet was released from Santa, a Korean TOEIC preparation service. The release
is hierarchical:

| Release | Main information | Appropriate interpretation |
| --- | --- | --- |
| KT1 | Question-response records | Answer correctness and question history |
| KT2 | KT1-style activity plus question-solving actions | Answer attempts and interaction sequence |
| KT3 | KT2-style activity plus explanations and lectures | Review and instructional-resource use |
| KT4 | Broader action stream including media and payment events | Rich behavioral context and platform actions |
| Contents | Questions, lectures, payments, and coupons | Content metadata and catalog structure |

The tiers are overlapping views of activity, not independent samples. Their
row counts and action counts must therefore not be added to estimate a single
total number of learning events. Payment and coupon events describe access or
promotion and are not direct learning outcomes. The release does not provide a
released score variable suitable for treating as ground-truth achievement.

## Local data requirements

The raw archives are intentionally outside Git because of their size and
license constraints. For local execution, obtain the permitted EdNet release
and place the relevant archives under the project data directory, for example:

```text
data/raw/ednet/EdNet-KT1.zip
data/raw/ednet/EdNet-Contents.zip
```

The notebook currently contains machine-specific absolute paths inherited from
the existing analysis. Before claiming a portable rerun, replace those paths
with project-relative or configurable paths. The raw archives should not be
fabricated, committed, or substituted with synthetic records.

## Cleaning and feature extraction decisions

The notebook applies the following analytical rules:

1. **Answer filtering.** Rows with a blank `user_answer` are excluded from
   correctness rates because no answered question is observed. A blank action
   is not silently converted to an incorrect answer.
2. **Question catalog join.** KT1 responses are joined to question metadata by
   question ID. `is_correct` is derived by comparing the observed answer with
   the catalog answer key. The join is a content-enrichment step, not a source
   of new learner outcomes.
3. **Multiple analysis units.** User histories, question exposure, bundle
   exposure, and TOEIC-part rates are summarized separately. Every percentage
   must be read with its corresponding denominator.
4. **Repeated questions.** Repeated question IDs are retained because retries,
   answer changes, and review are meaningful behavior. They are not treated as
   independent learning opportunities when interpreting history length or
   exposure.
5. **Skewed histories.** Medians, percentiles, log-scale histograms, and the
   empirical cumulative distribution function are used because interaction
   histories are long-tailed. These summaries support robust history-length,
   attempt-count, and cold-start features.
6. **Content heterogeneity.** Part-level correctness and exposure are reported
   descriptively. They can motivate part-aware features, but differences do not
   establish that a TOEIC part caused a learner outcome.
7. **Exposure imbalance.** Question- and bundle-level response counts are
   inspected to identify popular and unanswered content. This guards against
   confusing platform selection or popularity with learner ability.
8. **Elapsed time.** `elapsed_time` is measured in milliseconds and is an
   interaction interval, not validated study duration. Extreme and repeated
   values are inspected as data-quality signals. Any later feature should use a
   documented transformation or robust aggregate rather than raw hours.
9. **Missing catalog metadata.** Sentinel values such as `-1`, unknown lecture
   deployment dates, numeric-only tags, and missing video lengths remain
   explicitly documented. They are not interpreted as meaningful skills or
   durations.

## Notebook-reported findings

The following values are reported by the existing executed notebook cells. They
should be reproduced by rerunning the notebook against the permitted local
archives; they are not results of a new execution in this documentation pass.

- The KT1 learner-history distribution has a median of **10 distinct
  questions**, with 75% of users at **37 or fewer**. **24.3%** of users have
  answered at least one question ID more than once.
- Among **95.27 million nonblank answers**, the reported correctness rate is
  **65.3%**. Reported accuracy varies by TOEIC part, including **73.8%** for
  Part 1 and **60.4%** for Part 5. These are observed answer rates, not causal
  measures of learning.
- **885 of 13,169** catalog questions, or **6.7%**, have no observed response
  in the scanned KT1 activity. Exposure is uneven: the reported median
  question exposure is **4,627** responses, while the most-answered question
  has **241,688**.
- **99.4%** of answered bundles are reported to have question counts within 1%
  of each other. This supports bundle-level analysis, but it does not prove
  that every learner experiences a bundle in the same way.
- Most reported response-time values are between 5 seconds and 2 minutes, but
  **21,558** values exceed 10 minutes. The inspected extreme records reach
  approximately **18–79 hours**, reinforcing the warning against treating raw
  elapsed time as study duration.

These findings motivate feature candidates such as prior correctness, recent
attempt count, distinct-question count, repeated-question count, part and tag
identifiers, bundle exposure, and use of explanations or media. They do not
justify claiming that those features cause improvement.

## Relevance to the planner

EdNet is a reasonable source for a TOEIC practice recommender or adaptive
question-selection module. A future supervised task could predict correctness
on a future question using only a learner's preceding history. A defensible
evaluation would use learner-held-out splits and chronological feature
construction so that future interactions cannot leak into earlier predictions.
Cold-start users need an explicit population baseline or diagnostic sequence
because many histories are short.

EdNet is not sufficient for the planner's general scheduling problem. A
production planner still needs structured inputs for goals, available time,
deadlines, course or assignment priority, and user feedback. Those inputs must
come from the application or a dataset with the relevant fields.

## Limitations and governance

- Observed questions and recommendations are subject to selection and exposure
  bias; the logs cannot establish that an action caused learning.
- Sparse histories create cold-start and unequal-observation problems.
- Numeric tags are identifiers, not human-readable skill names, and the
  supplied catalog does not provide the full instructional text needed for
  semantic interpretation.
- Shifted timestamps protect privacy. Use within-user order and relative gaps,
  not real calendar dates, for temporal features.
- Payment and coupon information should not be used as a proxy for learning
  progress without a clear, ethically justified product purpose.
- The official release is licensed **CC BY-NC 4.0**. Confirm attribution and
  non-commercial-use obligations before redistribution or commercial use.

## Remaining reproducibility work

Notebook 05 has been documented without changing its existing embedded outputs.
To make it fully portable and executable from a clean checkout:

1. parameterize the EdNet archive paths;
2. define `activity_bands` before its summary cell;
3. obtain the permitted EdNet archives locally;
4. execute the notebook from top to bottom and inspect all outputs; and
5. if EdNet modeling is added, create a leakage-safe feature pipeline and
   learner-held-out, time-respecting evaluation separate from the OULAD target.

