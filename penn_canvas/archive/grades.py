from canvasapi.course import Course
from canvasapi.enrollment import Enrollment
from canvasapi.submission import Submission
from pandas import DataFrame
from typer import echo

from penn_canvas.api import Instance, get_section
from penn_canvas.helpers import create_directory
from penn_canvas.style import print_item

from .helpers import format_name


def get_score_from_submissions(submissions: list[tuple[int, int]], user_id: str):
    return next(item[1] for item in submissions if item[0] == user_id)


def get_grade(
    enrollment: Enrollment,
    submissions: list[tuple[str, list[tuple[int, int]]]],
    instance: Instance,
) -> list:
    user_id = enrollment.user_id
    user = enrollment.user
    section_id = get_section(enrollment.course_section_id, instance=instance).name
    student_data = [
        user["sortable_name"],
        user_id,
        user["sis_user_id"],
        user["login_id"],
        section_id,
    ]
    submission_scores = [
        get_score_from_submissions(submission[1], user_id) for submission in submissions
    ]
    total_scores = [
        enrollment.grades["current_score"],
        enrollment.grades["unposted_current_score"],
        enrollment.grades["final_score"],
        enrollment.grades["unposted_final_score"],
        enrollment.grades["current_grade"],
        enrollment.grades["unposted_current_grade"],
        enrollment.grades["final_grade"],
        enrollment.grades["unposted_final_grade"],
    ]
    return student_data + submission_scores + total_scores


def get_enrollments(course: Course) -> list[Enrollment]:
    echo(") Finding students...")
    return [
        enrollment
        for enrollment in course.get_enrollments()
        if enrollment.type == "StudentEnrollment"
    ]


def get_manual_posting(assignment):
    return "Manual Posting" if assignment.post_manually else ""


def get_submission_score(submission: Submission):
    return round(float(submission.score), 2) if submission.score else submission.score


def fetch_grades(course, course_directory, assignments, instance, verbose):
    echo(") Exporting grades...")
    enrollments = get_enrollments(course)
    if not assignments:
        assignments = course.get_assignments()
    assignments = [assignment for assignment in assignments if assignment.published]
    assignment_posted = [""] * 5 + [
        get_manual_posting(assignment) for assignment in assignments
    ]
    assignment_points = (
        ["    Points Possible"]
        + [""] * 4
        + [assignment.points_possible for assignment in assignments]
        + (["(read only)"] * 8)
    )
    submissions = [
        (
            format_name(assignment.name),
            [
                (submission.user_id, get_submission_score(submission))
                for submission in assignment.get_submissions()
            ],
        )
        for assignment in assignments
    ]
    assignment_names = [submission[0] for submission in submissions]
    columns = (
        [
            "Student",
            "ID",
            "SIS User ID",
            "SIS Login ID",
            "Section",
        ]
        + assignment_names
        + [
            "Current Score",
            "Unposted Current Score",
            "Final Score",
            "Unposted Final Score",
            "Current Grade",
            "Unposted Current Grade",
            "Final Grade",
            "Unposted Final Grade",
        ]
    )
    grades_path = create_directory(course_directory / "Grades") / "Grades.csv"
    rows = (
        [assignment_posted]
        + [assignment_points]
        + [get_grade(enrollment, submissions, instance) for enrollment in enrollments]
    )
    grade_book = DataFrame(rows, columns=columns)
    grade_book.to_csv(grades_path, index=False)
    if verbose:
        total = len(rows)
        for index, row in enumerate(rows):
            row = [str(item) for item in row]
            print_item(index, total, ", ".join(row))
