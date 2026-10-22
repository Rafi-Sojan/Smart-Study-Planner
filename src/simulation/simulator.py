"""Generate a reproducible synthetic Indian-university planner dataset.

The generator creates relational CSV tables for planner development. All rows
are simulated. No generated value should be presented as an observation about
real students or a real university.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from .scenarios import (
    COURSE_CATALOG,
    RESOURCE_TYPES,
    STUDENT_PROFILES,
    TOPIC_TEMPLATES,
)


@dataclass(frozen=True)
class SimulationConfig:
    """Parameters controlling one reproducible simulation run.

    ``seed`` fixes the pseudo-random stream; the remaining fields define the
    population, academic calendar, and output location. The defaults are the
    project's primary 1,000-student development scenario. A smaller scenario
    can be supplied explicitly for fast tests.
    """

    output_dir: Path
    seed: int = 42
    students: int = 1000
    terms: int = 3
    weeks_per_term: int = 16
    start_date: str = "2025-07-01"
    overwrite: bool = False


def _clip(value: float, low: float, high: float) -> float:
    """Restrict a simulated continuous value to a valid domain.

    Clipping prevents impossible values such as negative study hours or
    scores above the declared scale while retaining random variation inside
    the domain.
    """
    return float(np.clip(value, low, high))


def _date(value: pd.Timestamp) -> str:
    """Serialize a timestamp as an ISO calendar date for CSV output."""
    return value.date().isoformat()


def _datetime(value: pd.Timestamp) -> str:
    """Serialize a timestamp as an ISO-like second-resolution datetime."""
    return value.strftime("%Y-%m-%dT%H:%M:%S")


def _round(value: float, digits: int = 3) -> float:
    """Round generated numeric values to a stable, readable precision."""
    return round(float(value), digits)


def _grade(score: float) -> str:
    """Map a 0--100 assessment score to the synthetic letter-grade scale."""
    if score >= 90:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B+"
    if score >= 60:
        return "B"
    if score >= 50:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _term_rows(config: SimulationConfig) -> list[dict[str, Any]]:
    """Build term rows from the configured start date and term length.

    A 21-day inter-term interval represents a planning gap for examinations,
    results, registration, and academic holidays. It is a simulation
    assumption, not a universal academic-calendar rule.
    """
    start = pd.Timestamp(config.start_date)
    rows = []
    for term_number in range(1, config.terms + 1):
        term_start = start + pd.Timedelta(days=(term_number - 1) * (config.weeks_per_term * 7 + 21))
        term_end = term_start + pd.Timedelta(days=config.weeks_per_term * 7 - 1)
        rows.append(
            {
                "term_id": f"TERM{term_number}",
                "university_id": "UNI001",
                "academic_year": f"{term_start.year}-{term_end.year}",
                "semester_name": f"Semester {term_number}",
                "start_date": _date(term_start),
                "end_date": _date(term_end),
                "exam_session": "regular",
            }
        )
    return rows


def _course_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Create course, topic, and course-topic bridge tables.

    Each course receives four ordered topics. The bridge table preserves the
    many-to-many relationship and stores topic sequence and assessment weight.
    """
    courses = []
    topics = []
    course_topics = []
    for course in COURSE_CATALOG:
        courses.append(
            {
                key: course[key]
                for key in (
                    "course_id",
                    "course_code",
                    "course_name",
                    "course_type",
                    "credits",
                    "difficulty",
                    "assessment_scheme",
                    "estimated_effort_hours",
                )
            }
            | {"program_id": "BTECH-CSE"}
        )
        topic_names = TOPIC_TEMPLATES[course["course_type"]]
        previous_topic = None
        for order, topic_name in enumerate(topic_names, start=1):
            topic_id = f"{course['course_id']}-T{order}"
            topics.append(
                {
                    "topic_id": topic_id,
                    "topic_name": f"{course['course_name']} - {topic_name}",
                    "difficulty": course["difficulty"],
                    "estimated_effort_hours": _round(course["estimated_effort_hours"] / 4, 2),
                    "prerequisite_topic_id": previous_topic,
                }
            )
            course_topics.append(
                {
                    "course_topic_id": f"{course['course_id']}-CT{order}",
                    "course_id": course["course_id"],
                    "topic_id": topic_id,
                    "sequence_order": order,
                    "assessment_weight": _round(1 / 4, 3),
                    "recommended_deadline": None,
                }
            )
            previous_topic = topic_id
    return courses, topics, course_topics


def _students(rng: np.random.Generator, count: int) -> tuple[list[dict[str, Any]], dict[str, dict[str, float]]]:
    """Create student profile rows and unobserved behavioural state.

    Public rows contain planner-facing attributes. The returned latent state
    drives correlated attendance, performance, sleep, availability, and
    recommendation behaviour without exposing a fabricated causal claim.
    """
    profiles = list(STUDENT_PROFILES)
    rows = []
    latent: dict[str, dict[str, float]] = {}
    categories = ("general", "obc", "sc", "st", "ews")
    for index in range(count):
        student_id = f"STU{index + 1:04d}"
        profile_name = profiles[index % len(profiles)]
        profile = STUDENT_PROFILES[profile_name]
        ability = _clip(profile["prior_performance"] + rng.normal(0, 0.45), 4.0, 9.8)
        reliability = _clip(profile["study_reliability"] + rng.normal(0, 0.05), 0.15, 0.98)
        rows.append(
            {
                "student_id": student_id,
                "program_id": "BTECH-CSE",
                "admission_year": 2025,
                "category": categories[index % len(categories)],
                "study_mode": "regular",
                "residence_type": profile["residence_type"],
                "employment_status": profile["employment_status"],
                "consent_status": "synthetic_development_only",
            }
        )
        latent[student_id] = {
            "profile_index": float(index % len(profiles)),
            "ability": ability,
            "reliability": reliability,
            "attendance_probability": _clip(profile["attendance_probability"] + rng.normal(0, 0.025), 0.45, 0.99),
            "sleep_hours": _clip(profile["sleep_hours"] + rng.normal(0, 0.35), 4.5, 9.0),
            "available_hours": _clip(profile["available_hours"] + rng.normal(0, 0.35), 0.75, 6.0),
        }
    return rows, latent


def generate_dataset(config: SimulationConfig) -> dict[str, int]:
    """Generate all synthetic tables and return their row counts.

    The function validates the requested scenario, constructs parent tables
    before child tables, writes one CSV per relational entity, and records
    provenance in ``manifest.json``. With a fixed configuration and seed, the
    output is reproducible. Existing CSV files are never silently replaced;
    callers must opt in with ``overwrite=True``.
    """

    if config.students < 4:
        raise ValueError("students must be at least 4 to cover all scenario profiles")
    if config.terms < 1 or config.terms > 3:
        raise ValueError("terms must be between 1 and 3 for the supplied course catalogue")
    if config.weeks_per_term < 8:
        raise ValueError("weeks_per_term must be at least 8")

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    existing_csvs = list(output_dir.glob("*.csv"))
    if existing_csvs and not config.overwrite:
        raise FileExistsError(
            f"Output directory already contains CSV files: {output_dir}. "
            "Choose a new directory or remove it deliberately before regenerating."
        )
    if config.overwrite:
        for path in output_dir.glob("*.csv"):
            path.unlink()
        manifest_path = output_dir / "manifest.json"
        if manifest_path.exists():
            manifest_path.unlink()

    rng = np.random.default_rng(config.seed)
    terms = _term_rows(config)
    courses, topics, course_topics = _course_rows()
    students, latent = _students(rng, config.students)
    term_by_number = {index + 1: row for index, row in enumerate(terms)}
    course_by_id = {course["course_id"]: course for course in COURSE_CATALOG}

    universities = [
        {
            "university_id": "UNI001",
            "university_name": "Synthetic Institute of Technology",
            "state": "Karnataka",
            "accreditation_category": "autonomous_simulation",
        }
    ]
    campuses = [{"campus_id": "CAMP001", "university_id": "UNI001", "campus_name": "Main Campus", "city": "Bengaluru"}]
    departments = [{"department_id": "DEPT-CSE", "campus_id": "CAMP001", "department_name": "Computer Science and Engineering"}]
    programs = [
        {
            "program_id": "BTECH-CSE",
            "department_id": "DEPT-CSE",
            "program_name": "B.Tech Computer Science and Engineering",
            "degree_level": "undergraduate",
            "regulation_scheme": "CBCS_NE P_SIMULATION".replace(" ", ""),
            "duration_years": 4,
            "grading_scale": "10_point",
        }
    ]

    offerings = []
    offering_by_id: dict[str, dict[str, Any]] = {}
    for course in COURSE_CATALOG:
        if course["term_number"] > config.terms:
            continue
        term = term_by_number[course["term_number"]]
        offering = {
            "offering_id": f"{course['course_id']}-{term['term_id']}",
            "course_id": course["course_id"],
            "term_id": term["term_id"],
            "department_id": "DEPT-CSE",
            "section": "A",
            "faculty_id": f"FAC-{course['term_number']:02d}",
            "attendance_requirement_percent": 75.0,
        }
        offerings.append(offering)
        offering_by_id[offering["offering_id"]] = offering

    enrollments = []
    enrollment_by_id: dict[str, dict[str, Any]] = {}
    for student in students:
        student_latent = latent[student["student_id"]]
        for offering in offerings:
            course = course_by_id[offering["course_id"]]
            is_backlog = student_latent["profile_index"] == 3 and course["term_number"] == 1 and rng.random() < 0.12
            enrollment_id = f"ENR-{student['student_id']}-{offering['offering_id']}"
            row = {
                "enrollment_id": enrollment_id,
                "student_id": student["student_id"],
                "offering_id": offering["offering_id"],
                "attempt_number": 2 if is_backlog else 1,
                "is_backlog": bool(is_backlog),
                "enrollment_status": "active",
                "enrollment_date": term_by_number[course["term_number"]]["start_date"],
            }
            enrollments.append(row)
            enrollment_by_id[enrollment_id] = row

    academic_performance = []
    for student in students:
        student_latent = latent[student["student_id"]]
        cumulative = None
        for term_number, term in term_by_number.items():
            if term_number > config.terms:
                continue
            semester_gpa = _clip(student_latent["ability"] + rng.normal(0, 0.4), 4.0, 10.0)
            cumulative = semester_gpa if cumulative is None else _clip((cumulative + semester_gpa) / 2, 4.0, 10.0)
            term_credits = sum(
                course["credits"]
                for course in COURSE_CATALOG
                if course["term_number"] == term_number
            )
            academic_performance.append(
                {
                    "performance_id": f"PERF-{student['student_id']}-{term['term_id']}",
                    "student_id": student["student_id"],
                    "term_id": term["term_id"],
                    "semester_gpa": _round(semester_gpa, 2),
                    "cumulative_gpa": _round(cumulative, 2),
                    "grading_scale": "10_point",
                    "attempted_credits": term_credits,
                    "earned_credits": int(round(term_credits * _clip(semester_gpa / 10, 0.35, 1.0))),
                    "failed_credits": int(round(term_credits * _clip((10 - semester_gpa) / 12, 0.0, 0.55))),
                    "backlog_count": int(student_latent["profile_index"] == 3 and semester_gpa < 6.0),
                    "result_date": term["end_date"],
                }
            )

    timetable = []
    attendance = []
    attendance_state: dict[str, tuple[int, int]] = {}
    for offering_index, offering in enumerate(offerings):
        course = course_by_id[offering["course_id"]]
        term = term_by_number[course["term_number"]]
        term_start = pd.Timestamp(term["start_date"])
        weekday = offering_index % 5
        timetable.append(
            {
                "timetable_id": f"TT-{offering['offering_id']}",
                "offering_id": offering["offering_id"],
                "weekday": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"][weekday],
                "start_time": f"{9 + offering_index % 5:02d}:00",
                "end_time": f"{11 + offering_index % 5:02d}:00",
                "room": f"BLOCK-{chr(65 + offering_index % 3)}-{101 + offering_index % 10}",
            }
        )
        class_offset = (weekday - term_start.weekday()) % 7
        class_dates = [term_start + pd.Timedelta(days=class_offset + week * 7) for week in range(config.weeks_per_term)]
        for enrollment in [row for row in enrollments if row["offering_id"] == offering["offering_id"]]:
            student_latent = latent[enrollment["student_id"]]
            present_count = 0
            for class_number, class_date in enumerate(class_dates, start=1):
                present = bool(rng.random() < student_latent["attendance_probability"])
                present_count += int(present)
                attendance_state[enrollment["enrollment_id"]] = (present_count, len(class_dates))
                attendance.append(
                    {
                        "attendance_id": f"ATT-{enrollment['enrollment_id']}-{class_date.strftime('%Y%m%d')}",
                        "enrollment_id": enrollment["enrollment_id"],
                        "class_date": _date(class_date),
                        "attendance_status": "present" if present else "absent",
                        "attendance_percentage": _round(100 * present_count / class_number, 2),
                        "attendance_gap_to_required": _round(
                            (present_count / class_number * 100) - offering["attendance_requirement_percent"], 2
                        ),
                    }
                )

    assessments = []
    assessment_by_offering: dict[str, list[dict[str, Any]]] = {}
    for offering in offerings:
        course = course_by_id[offering["course_id"]]
        term = term_by_number[course["term_number"]]
        term_start = pd.Timestamp(term["start_date"])
        types = ("internal", "assignment", "end_semester")
        if "practical" in course["assessment_scheme"] or "lab" in course["course_type"]:
            types = ("internal", "practical", "end_semester")
        rows = []
        for index, assessment_type in enumerate(types):
            assessment_date = term_start + pd.Timedelta(days=(index + 1) * (config.weeks_per_term * 7 // 4))
            if assessment_type == "end_semester":
                assessment_date = pd.Timestamp(term["end_date"]) - pd.Timedelta(days=5)
            row = {
                "assessment_id": f"ASM-{offering['offering_id']}-{index + 1}",
                "offering_id": offering["offering_id"],
                "assessment_type": assessment_type,
                "assessment_date": _date(assessment_date),
                "maximum_marks": 100.0,
                "weightage": 0.25 if assessment_type != "end_semester" else 0.5,
            }
            assessments.append(row)
            rows.append(row)
        assessment_by_offering[offering["offering_id"]] = rows

    assessment_attempts = []
    outcomes = []
    for enrollment in enrollments:
        offering = offering_by_id[enrollment["offering_id"]]
        student_latent = latent[enrollment["student_id"]]
        course = course_by_id[offering["course_id"]]
        assessment_scores = []
        present_count, total_classes = attendance_state[enrollment["enrollment_id"]]
        attendance_ratio = present_count / total_classes
        for assessment in assessment_by_offering[offering["offering_id"]]:
            score = _clip(
                25
                + student_latent["ability"] * 7
                + student_latent["reliability"] * 18
                + attendance_ratio * 12
                - (5 if course["difficulty"] == "hard" else 0)
                + rng.normal(0, 8),
                0,
                100,
            )
            assessment_scores.append(score)
            late_submission = bool(rng.random() > student_latent["reliability"] + 0.2)
            assessment_attempts.append(
                {
                    "attempt_id": f"ATTEMPT-{enrollment['enrollment_id']}-{assessment['assessment_id']}",
                    "assessment_id": assessment["assessment_id"],
                    "enrollment_id": enrollment["enrollment_id"],
                    "marks_obtained": _round(score, 2),
                    "grade": _grade(score),
                    "is_supplementary": False,
                    "submission_status": "late" if late_submission else "submitted",
                    "late_submission": late_submission,
                }
            )
        final_score = _clip(float(np.mean(assessment_scores)), 0, 100)
        withdrawn = bool(student_latent["reliability"] < 0.4 and attendance_ratio < 0.65 and rng.random() < 0.12)
        passed = bool(final_score >= 40 and not withdrawn)
        outcomes.append(
            {
                "outcome_id": f"OUT-{enrollment['enrollment_id']}",
                "student_id": enrollment["student_id"],
                "offering_id": enrollment["offering_id"],
                "final_grade": "W" if withdrawn else _grade(final_score),
                "result_status": "withdrawn" if withdrawn else ("passed" if passed else "failed"),
                "passed": passed,
                "withdrawn": withdrawn,
                "requires_retake": not passed,
            }
        )

    resources = []
    for topic in topics:
        for index, resource_type in enumerate(RESOURCE_TYPES[:3], start=1):
            resources.append(
                {
                    "resource_id": f"RES-{topic['topic_id']}-{index}",
                    "course_id": topic["topic_id"].split("-T")[0],
                    "topic_id": topic["topic_id"],
                    "resource_type": resource_type,
                    "resource_title": f"{topic['topic_name']} - {resource_type.replace('_', ' ').title()}",
                    "difficulty": topic["difficulty"],
                    "estimated_duration_minutes": int(topic["estimated_effort_hours"] * 60 / 3),
                    "language": "English",
                    "accessibility_format": "text_and_video" if resource_type == "lecture_video" else "text",
                }
            )

    student_preferences = []
    goals = []
    for student in students:
        student_latent = latent[student["student_id"]]
        student_preferences.append(
            {
                "preference_id": f"PREF-{student['student_id']}",
                "student_id": student["student_id"],
                "preferred_study_period": "morning" if int(student_latent["profile_index"]) % 2 == 0 else "evening",
                "preferred_session_minutes": int(45 + student_latent["reliability"] * 45),
                "preferred_break_minutes": 10,
                "notification_preference": "enabled",
                "accessibility_needs": "none",
            }
        )
        goals.append(
            {
                "goal_id": f"GOAL-{student['student_id']}",
                "student_id": student["student_id"],
                "goal_type": "semester_gpa",
                "target_grade": "A" if student_latent["ability"] >= 7 else "B+",
                "target_cgpa": _round(_clip(student_latent["ability"] + 0.6, 5.5, 10), 2),
                "target_date": terms[min(config.terms, len(terms)) - 1]["end_date"],
                "priority": "high" if student_latent["reliability"] < 0.55 else "medium",
                "goal_status": "active",
            }
        )

    availability = []
    sleep_records = []
    wellbeing = []
    constraints = []
    for student in students:
        student_latent = latent[student["student_id"]]
        for term_number, term in term_by_number.items():
            term_start = pd.Timestamp(term["start_date"])
            for day_number in range(config.weeks_per_term * 7):
                current = term_start + pd.Timedelta(days=day_number)
                available = _clip(student_latent["available_hours"] + rng.normal(0, 0.55), 0.25, 7.0)
                sleep = _clip(student_latent["sleep_hours"] + rng.normal(0, 0.7), 3.5, 9.5)
                academic_screen = _clip(available * rng.uniform(0.45, 0.85), 0, 8)
                recreational_screen = _clip(rng.normal(2.2, 1.0), 0.1, 6.0)
                fatigue = _clip(6.5 - sleep + rng.normal(0, 0.6), 0, 10)
                availability.append(
                    {
                        "availability_id": f"AVL-{student['student_id']}-{current.strftime('%Y%m%d')}",
                        "student_id": student["student_id"],
                        "availability_date": _date(current),
                        "available_hours": _round(available, 2),
                        "class_hours": _round(rng.uniform(3.0, 6.0), 2),
                        "commute_hours": _round(rng.uniform(0.25, 2.2) if student["residence_type"] == "day_scholar" else 0.1, 2),
                        "part_time_work_hours": _round(rng.uniform(0, 3.0) if student["employment_status"] == "part_time" else 0, 2),
                        "availability_reason": "normal_day",
                    }
                )
                sleep_records.append(
                    {
                        "sleep_id": f"SLEEP-{student['student_id']}-{current.strftime('%Y%m%d')}",
                        "student_id": student["student_id"],
                        "sleep_date": _date(current),
                        "sleep_start": _datetime(current - pd.Timedelta(days=1) + pd.Timedelta(hours=23, minutes=int(rng.integers(-45, 46)))),
                        "wake_time": _datetime(current + pd.Timedelta(hours=7, minutes=int(rng.integers(-45, 46)))),
                        "total_sleep_hours": _round(sleep, 2),
                        "sleep_quality_score": _round(_clip(10 - fatigue + rng.normal(0, 0.7), 1, 10), 2),
                        "nap_minutes": int(rng.choice([0, 0, 20, 30, 45])),
                        "sleep_interruptions": int(rng.choice([0, 0, 1, 2])),
                        "sleep_source": "synthetic_self_report",
                    }
                )
                wellbeing.append(
                    {
                        "wellbeing_id": f"WELL-{student['student_id']}-{current.strftime('%Y%m%d')}",
                        "student_id": student["student_id"],
                        "observation_date": _date(current),
                        "academic_screen_minutes": int(academic_screen * 60),
                        "recreational_screen_minutes": int(recreational_screen * 60),
                        "total_screen_minutes": int((academic_screen + recreational_screen) * 60),
                        "total_break_minutes": int(rng.uniform(20, 100)),
                        "sleep_hours": _round(sleep, 2),
                        "sleep_deficit_hours": _round(max(0, 7.5 - sleep), 2),
                        "fatigue_score": _round(fatigue, 2),
                        "concentration_score": _round(_clip(8.5 - fatigue + rng.normal(0, 0.7), 0, 10), 2),
                        "stress_score": _round(_clip(4 + fatigue / 2 + rng.normal(0, 1), 0, 10), 2),
                    }
                )
            constraints.append(
                {
                    "constraint_id": f"CON-{student['student_id']}-T{term_number}",
                    "student_id": student["student_id"],
                    "constraint_date": _date(term_start + pd.Timedelta(days=int(rng.integers(7, 80)))),
                    "constraint_type": "placement_preparation" if term_number == 2 else "family_commitment",
                    "start_time": "18:00",
                    "end_time": "21:00",
                    "impact_level": "medium",
                }
            )

    study_sessions = []
    breaks = []
    recommendations = []
    feedback = []
    resource_interactions = []
    topic_state = []
    goal_progress = []
    session_counter = 0
    for student in students:
        student_latent = latent[student["student_id"]]
        for term_number, term in term_by_number.items():
            term_start = pd.Timestamp(term["start_date"])
            term_offerings = [row for row in offerings if row["term_id"] == term["term_id"]]
            for week in range(config.weeks_per_term):
                for session_index in range(2):
                    session_counter += 1
                    offering = term_offerings[(week * 2 + session_index) % len(term_offerings)]
                    course_topics_for_course = [row for row in course_topics if row["course_id"] == offering["course_id"]]
                    topic_mapping = course_topics_for_course[(week + session_index) % len(course_topics_for_course)]
                    session_day = term_start + pd.Timedelta(days=week * 7 + session_index + 1)
                    planned_duration = int(rng.choice([45, 60, 75, 90]))
                    completed = bool(rng.random() < student_latent["reliability"] + 0.35)
                    actual_duration = int(planned_duration * rng.uniform(0.55, 1.15)) if completed else 0
                    break_minutes = int(rng.uniform(8, 20)) if completed and actual_duration >= 45 else 0
                    actual_start = session_day + pd.Timedelta(hours=int(rng.choice([7, 9, 17, 19])))
                    session_id = f"SESSION-{session_counter:06d}"
                    study_sessions.append(
                        {
                            "session_id": session_id,
                            "student_id": student["student_id"],
                            "enrollment_id": f"ENR-{student['student_id']}-{offering['offering_id']}",
                            "topic_id": topic_mapping["topic_id"],
                            "planned_start": _datetime(actual_start),
                            "actual_start": _datetime(actual_start + pd.Timedelta(minutes=int(rng.integers(0, 25)))) if completed else None,
                            "planned_duration_minutes": planned_duration,
                            "actual_duration_minutes": actual_duration,
                            "active_study_minutes": max(0, actual_duration - break_minutes),
                            "screen_time_minutes": int(max(0, actual_duration * rng.uniform(0.4, 1.0))),
                            "distraction_minutes": int(rng.uniform(0, 20) if completed else 0),
                            "planned_break_minutes": 10 if planned_duration >= 60 else 5,
                            "actual_break_minutes": break_minutes,
                            "break_count": int(1 if break_minutes else 0),
                            "session_mode": "online" if rng.random() < 0.65 else "mixed",
                            "device_type": str(rng.choice(["laptop", "phone", "tablet"])),
                            "completion_status": "completed" if completed else "missed",
                            "post_session_mastery": _round(_clip(student_latent["ability"] / 10 + rng.normal(0, 0.08), 0, 1), 3) if completed else None,
                        }
                    )
                    if break_minutes:
                        breaks.append(
                            {
                                "break_id": f"BREAK-{session_id}",
                                "session_id": session_id,
                                "break_start": _datetime(actual_start + pd.Timedelta(minutes=max(20, actual_duration // 2))),
                                "break_end": _datetime(actual_start + pd.Timedelta(minutes=max(20, actual_duration // 2 + break_minutes))),
                                "duration_minutes": break_minutes,
                                "break_type": "planned",
                                "planned": True,
                                "restorative_rating": _round(_clip(rng.normal(7, 1.3), 1, 10), 2),
                            }
                        )
                    recommendation_id = f"REC-{session_id}"
                    accepted = bool(rng.random() < student_latent["reliability"] + 0.3)
                    recommendations.append(
                        {
                            "recommendation_id": recommendation_id,
                            "enrollment_id": f"ENR-{student['student_id']}-{offering['offering_id']}",
                            "topic_id": topic_mapping["topic_id"],
                            "recommendation_date": _date(session_day),
                            "recommended_duration_minutes": planned_duration,
                            "recommended_break_minutes": 10 if planned_duration >= 60 else 5,
                            "priority": "high" if week >= config.weeks_per_term - 3 else "medium",
                            "recommendation_reason": "assessment_deadline" if week >= config.weeks_per_term - 3 else "topic_mastery",
                            "accepted": accepted,
                            "completed": completed,
                        }
                    )
                    if accepted and rng.random() < 0.7:
                        feedback.append(
                            {
                                "feedback_id": f"FDBK-{recommendation_id}",
                                "recommendation_id": recommendation_id,
                                "student_id": student["student_id"],
                                "feedback_date": _date(session_day),
                                "usefulness_score": int(rng.integers(3, 6)),
                                "difficulty_score": int(rng.integers(2, 6)),
                                "feedback_text": "synthetic_feedback",
                            }
                        )
            for topic in [row for row in topics if row["topic_id"].startswith(tuple(course["course_id"] for course in COURSE_CATALOG if course["term_number"] == term_number))]:
                for cutoff in (30, 60, 90):
                    if cutoff >= config.weeks_per_term * 7:
                        continue
                    observation = term_start + pd.Timedelta(days=cutoff)
                    topic_state.append(
                        {
                            "state_id": f"STATE-{student['student_id']}-{term_number}-{topic['topic_id']}-{cutoff}",
                            "enrollment_id": f"ENR-{student['student_id']}-{topic['topic_id'].split('-T')[0]}-TERM{term_number}",
                            "topic_id": topic["topic_id"],
                            "observation_date": _date(observation),
                            "mastery_score": _round(_clip(student_latent["ability"] / 10 + rng.normal(0, 0.1), 0, 1), 3),
                            "confidence_score": _round(_clip(student_latent["reliability"] + rng.normal(0, 0.1), 0, 1), 3),
                            "fatigue_score": _round(_clip(5 - student_latent["sleep_hours"] / 2 + rng.normal(0, 0.7), 0, 10), 2),
                            "remaining_effort_hours": _round(max(0.5, topic["estimated_effort_hours"] * (1 - student_latent["ability"] / 12)), 2),
                        }
                    )
            goal_progress.append(
                {
                    "progress_id": f"PROGRESS-{student['student_id']}-T{term_number}",
                    "student_id": student["student_id"],
                    "goal_id": f"GOAL-{student['student_id']}",
                    "observation_date": term["end_date"],
                    "current_progress": _round(_clip(student_latent["ability"] / 10 + rng.normal(0, 0.08), 0, 1), 3),
                    "target_progress": 1.0,
                    "progress_gap": _round(_clip(1 - student_latent["ability"] / 10, 0, 1), 3),
                }
            )
            for resource in resources:
                if resource["course_id"] in {row["course_id"] for row in term_offerings} and rng.random() < 0.3:
                    opened = term_start + pd.Timedelta(days=int(rng.integers(3, config.weeks_per_term * 7 - 1)))
                    completed_resource = bool(rng.random() < student_latent["reliability"] + 0.25)
                    resource_interactions.append(
                        {
                            "interaction_id": f"INTERACT-{student['student_id']}-{resource['resource_id']}",
                            "student_id": student["student_id"],
                            "resource_id": resource["resource_id"],
                            "opened_at": _datetime(opened),
                            "completed_at": _datetime(opened + pd.Timedelta(minutes=resource["estimated_duration_minutes"])) if completed_resource else None,
                            "view_duration_minutes": int(resource["estimated_duration_minutes"] * rng.uniform(0.3, 1.1)),
                            "completion_status": "completed" if completed_resource else "partial",
                            "resource_rating": int(rng.integers(3, 6)) if completed_resource else None,
                        }
                    )

    faculty_support = [
        {
            "support_id": f"SUPPORT-{offering['offering_id']}",
            "offering_id": offering["offering_id"],
            "support_type": "office_hours" if index % 2 == 0 else "tutorial",
            "support_date": term_by_number[course_by_id[offering["course_id"]]["term_number"]]["start_date"],
            "response_time_hours": int(rng.integers(4, 48)),
            "student_satisfaction_score": _round(rng.uniform(3.0, 5.0), 2),
        }
        for index, offering in enumerate(offerings)
    ]
    academic_events = []
    for term_number, term in term_by_number.items():
        term_start = pd.Timestamp(term["start_date"])
        academic_events.extend(
            [
                {
                    "event_id": f"EVENT-T{term_number}-1",
                    "university_id": "UNI001",
                    "event_date": _date(term_start + pd.Timedelta(days=35)),
                    "event_type": "holiday",
                    "event_name": "University Holiday",
                    "affects_classes": True,
                },
                {
                    "event_id": f"EVENT-T{term_number}-2",
                    "university_id": "UNI001",
                    "event_date": _date(term_start + pd.Timedelta(days=65)),
                    "event_type": "festival",
                    "event_name": "Campus Festival",
                    "affects_classes": True,
                },
                {
                    "event_id": f"EVENT-T{term_number}-3",
                    "university_id": "UNI001",
                    "event_date": _date(pd.Timestamp(term["end_date"]) - pd.Timedelta(days=5)),
                    "event_type": "examination",
                    "event_name": "End Semester Examination",
                    "affects_classes": True,
                },
            ]
        )
    exam_schedule = [
        {
            "exam_id": f"EXAM-{assessment['assessment_id']}",
            "offering_id": assessment["offering_id"],
            "exam_type": assessment["assessment_type"],
            "exam_date": assessment["assessment_date"],
            "exam_start_time": "10:00",
            "exam_duration_minutes": 180 if assessment["assessment_type"] == "end_semester" else 90,
            "exam_weightage": assessment["weightage"],
        }
        for assessment in assessments
    ]

    tables: dict[str, list[dict[str, Any]]] = {
        "universities": universities,
        "campuses": campuses,
        "departments": departments,
        "programs": programs,
        "students": students,
        "academic_terms": terms,
        "courses": courses,
        "course_offerings": offerings,
        "enrollments": enrollments,
        "topics": topics,
        "course_topics": course_topics,
        "academic_performance": academic_performance,
        "class_timetable": timetable,
        "attendance_records": attendance,
        "assessments": assessments,
        "assessment_attempts": assessment_attempts,
        "exam_schedule": exam_schedule,
        "learning_resources": resources,
        "resource_interactions": resource_interactions,
        "student_topic_state": topic_state,
        "availability": availability,
        "student_preferences": student_preferences,
        "student_goals": goals,
        "student_goal_progress": goal_progress,
        "calendar_constraints": constraints,
        "study_sessions": study_sessions,
        "break_records": breaks,
        "sleep_records": sleep_records,
        "daily_wellbeing": wellbeing,
        "planner_recommendations": recommendations,
        "recommendation_feedback": feedback,
        "faculty_support": faculty_support,
        "academic_events": academic_events,
        "outcomes": outcomes,
    }
    for table_name, rows in tables.items():
        pd.DataFrame(rows).to_csv(output_dir / f"{table_name}.csv", index=False)

    counts = {name: len(rows) for name, rows in tables.items()}
    manifest = {
        "dataset_name": "synthetic_indian_university_smart_study_planner",
        "data_source": "synthetic",
        "synthetic_record_flag": True,
        "generator": "src.simulation.simulator",
        "seed": config.seed,
        "configuration": {
            "students": config.students,
            "terms": config.terms,
            "weeks_per_term": config.weeks_per_term,
            "start_date": config.start_date,
        },
        "tables": counts,
        "limitations": [
            "Rows are simulated and are not observations about real students.",
            "Behaviour distributions are assumptions for development and testing.",
            "Synthetic performance must not be reported as real-world model evidence.",
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return counts


def _load_config(path: Path) -> dict[str, Any]:
    """Load and validate a YAML mapping used to configure the generator."""
    with path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError("simulation configuration must contain a mapping")
    return loaded


def main() -> None:
    """Parse CLI overrides, generate the dataset, and print row counts."""
    parser = argparse.ArgumentParser(description="Generate the synthetic Indian-university planner dataset")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--students", type=int, default=None)
    parser.add_argument("--terms", type=int, default=None)
    parser.add_argument("--weeks-per-term", type=int, default=None)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--overwrite", action="store_true", help="Replace generated CSVs in the exact output directory")
    args = parser.parse_args()
    config_values = _load_config(args.config) if args.config is not None else {}
    output_dir = args.output_dir or Path(config_values.get("output_dir", "data/raw/synthetic"))
    seed = args.seed if args.seed is not None else int(config_values.get("seed", 42))
    students = args.students if args.students is not None else int(config_values.get("students", 1000))
    terms = args.terms if args.terms is not None else int(config_values.get("terms", 3))
    weeks_per_term = (
        args.weeks_per_term
        if args.weeks_per_term is not None
        else int(config_values.get("weeks_per_term", 16))
    )
    start_date = args.start_date or str(config_values.get("start_date", "2025-07-01"))
    counts = generate_dataset(
        SimulationConfig(
            output_dir=output_dir,
            seed=seed,
            students=students,
            terms=terms,
            weeks_per_term=weeks_per_term,
            start_date=start_date,
            overwrite=args.overwrite,
        )
    )
    print(json.dumps({"output_dir": str(output_dir), "tables": counts}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
