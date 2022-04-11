from pathlib import Path
from typing import Optional

from canvasapi.assignment import Assignment
from canvasapi.course import Course
from canvasapi.enrollment import Enrollment
from canvasapi.submission import Submission
from pandas import DataFrame
from tqdm import tqdm
from typer import echo

from penn_canvas.api import Instance, get_section
from penn_canvas.helpers import create_directory
from penn_canvas.style import color, print_item

from .helpers import format_name


def get_enrollments(course: Course) -> list[Enrollment]:
    echo(") Getting students...")
    student_enrollments = course.get_enrollments(type=["StudentEnrollment"])
    return [enrollment for enrollment in student_enrollments]


def get_published_assignments(assignments: list[Assignment]) -> list[Assignment]:
    return [assignment for assignment in assignments if assignment.published]


def is_manual_posting(assignment: Assignment) -> str:
    return "Manual Posting" if assignment.post_manually else ""


def fill_rows(number_of_rows: int, fill_value="") -> list[str]:
    return [fill_value] * number_of_rows


def get_posting_types(assignments: list[Assignment]) -> list[list[str]]:
    posting_types = [is_manual_posting(assignment) for assignment in assignments]
    return [fill_rows(5) + posting_types]


def get_points_possible(assignments: list[Assignment]) -> list[list[str]]:
    points_possible = [assignment.points_possible for assignment in assignments]
    prefix_row = ["    Points Possible"]
    blank_rows = fill_rows(4)
    read_only_rows = fill_rows(8, fill_value="(read only)")
    return [prefix_row + blank_rows + points_possible + read_only_rows]


def get_submissions(assignments: list[Assignment]) -> list[list[Submission]]:
    echo(") Getting submissions...")
    return [list(assignment.get_submissions()) for assignment in tqdm(assignments)]


def get_user_submission(
    user_id: str, submissions: list[Submission]
) -> Optional[Submission]:
    return next(
        (submission for submission in submissions if submission.user_id == user_id),
        None,
    )


def get_submission_score(submission: Submission) -> str:
    score = submission.score
    if score:
        score = round(submission.score, 2)
    return score


def get_grades(
    enrollment: Enrollment,
    submissions: list[list[Submission]],
    instance: Instance,
    verbose: bool,
    index: int,
    total: int,
) -> list[str]:
    user_id = enrollment.user_id
    user = enrollment.user
    name = user["sortable_name"]
    section_id = get_section(enrollment.course_section_id, instance=instance).name
    grades = enrollment.grades
    final_grade = grades["final_grade"]
    student_data = [
        name,
        user_id,
        user["sis_user_id"],
        user["login_id"],
        section_id,
    ]
    user_submissions = [
        get_user_submission(user_id, submission) for submission in submissions
    ]
    submission_scores = [
        get_submission_score(submission)
        for submission in user_submissions
        if submission
    ]
    total_scores = [
        grades["current_score"],
        grades["unposted_current_score"],
        grades["final_score"],
        grades["unposted_final_score"],
        grades["current_grade"],
        grades["unposted_current_grade"],
        final_grade,
        grades["unposted_final_grade"],
    ]
    if verbose:
        message = f"{color(name)}: {color(final_grade, 'cyan')}"
        print_item(index, total, message)
    return student_data + submission_scores + total_scores


def get_enrollment_grades(
    enrollments: list[Enrollment],
    assignments: list[Assignment],
    instance: Instance,
    verbose: bool,
) -> list[list[str]]:
    submissions = get_submissions(assignments)
    total = len(enrollments)
    return [
        get_grades(enrollment, submissions, instance, verbose, index, total)
        for index, enrollment in enumerate(enrollments)
    ]


def get_assignment_names(assignments: list[Assignment]) -> list[str]:
    return [format_name(assignment.name) for assignment in assignments]


def get_all_columns(assignments: list[Assignment]) -> list[str]:
    assignment_names = get_assignment_names(assignments)
    student_columns = [
        "Student",
        "ID",
        "SIS User ID",
        "SIS Login ID",
        "Section",
    ]
    grade_columns = [
        "Current Score",
        "Unposted Current Score",
        "Final Score",
        "Unposted Final Score",
        "Current Grade",
        "Unposted Current Grade",
        "Final Grade",
        "Unposted Final Grade",
    ]
    return student_columns + assignment_names + grade_columns


def fetch_grades(
    course: Course,
    course_directory: Path,
    assignments: list[Assignment],
    instance: Instance,
    verbose: bool,
):
    echo(") Exporting grades...")
    enrollments = get_enrollments(course)
    if not assignments:
        echo(") Getting assignments...")
        assignments = list(course.get_assignments())
    published_assignments = get_published_assignments(assignments)
    posting_types = get_posting_types(published_assignments)
    points_possible = get_points_possible(published_assignments)
    enrollment_grades = get_enrollment_grades(
        enrollments, published_assignments, instance, verbose
    )
    grade_rows = posting_types + points_possible + enrollment_grades
    columns = get_all_columns(published_assignments)
    grade_book = DataFrame(grade_rows, columns=columns)
    grades_path = create_directory(course_directory / "Grades") / "Grades.csv"
    grade_book.to_csv(grades_path, index=False)
