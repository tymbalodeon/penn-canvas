from datetime import datetime
from pathlib import Path

from pandas.core.frame import DataFrame
from typer import echo

from penn_canvas.helpers import BOX_PATH, get_canvas

user_id = 5408866
course_ids = [
    1398885,
    1417301,
    1390661,
    1414102,
    1412419,
    1414933,
    1374407,
    1400009,
    1400016,
    1371056,
    1376386,
]
canvas = get_canvas()
canvas_user = canvas.get_user(user_id)


def format_timestamp(timestamp):
    if timestamp:
        date = datetime.fromisoformat(timestamp.replace("Z", ""))
        return date.strftime("%b %w, %Y (%I:%M:%S %p)")
    else:
        return timestamp


def get_submitted_at_or_none(submission):
    try:
        return format_timestamp(submission.submitted_at)
    except Exception:
        return None


def get_grader_or_none(grader_id):
    try:
        return canvas.get_user(grader_id) if grader_id > 0 else None
    except Exception:
        return None


def investigate_main():
    echo(f"Investigating student {canvas_user.name}...")
    for course_id in course_ids:
        course = canvas.get_course(course_id)
        echo(f"Processing {course.name}...")
        course_path = (
            BOX_PATH
            / "OGC Request"
            / course.name.strip().replace(" ", "_").replace("/", "-")
        )
        if not course_path.exists():
            Path.mkdir(course_path)
        assignments_path = course_path / "assignments.csv"
        discussions_path = course_path / "discussions.csv"
        quizzes_path = course_path / "quizzes.csv"
        echo("\tGetting assignments...")
        assignments = [assignment for assignment in course.get_assignments()]
        assignments_rows = list()
        for assignment in assignments:
            name = assignment.name
            submission_types = ", ".join(
                [
                    assignment.replace("_", " ")
                    for assignment in assignment.submission_types
                ]
            )
            due_date = format_timestamp(assignment.due_at)
            unlock_date = format_timestamp(assignment.unlock_at)
            lock_date = format_timestamp(assignment.lock_at)
            points_possible = assignment.points_possible
            submission = next(
                submission
                for submission in assignment.get_submissions(
                    include="submission_comments"
                )
                if submission.user_id == user_id
            )
            submitted_at = get_submitted_at_or_none(submission)
            attempt = submission.attempt
            grade = submission.grade
            grade_matches_current_submission = (
                submission.grade_matches_current_submission
            )
            score = submission.score
            grader_id = get_grader_or_none(submission.grader_id)
            graded_at = format_timestamp(submission.graded_at)
            late = submission.late
            excused = submission.excused
            missing = submission.missing
            late_policy_status = submission.late_policy_status
            points_deducted = submission.points_deducted
            seconds_late = submission.seconds_late
            extra_attempts = submission.extra_attempts
            assignment_row = [
                name,
                submission_types,
                due_date,
                unlock_date,
                lock_date,
                points_possible,
                submitted_at,
                attempt,
                grade,
                grade_matches_current_submission,
                score,
                grader_id,
                graded_at,
                late,
                excused,
                missing,
                late_policy_status,
                points_deducted,
                seconds_late,
                extra_attempts,
            ]
            assignments_rows.append(assignment_row)
        assignments = DataFrame(
            assignments_rows,
            columns=[
                "Name",
                "Submission Types",
                "Due Date",
                "Unlock Date",
                "Lock Date",
                "Points Possible",
                f"User {user_id} Submitted At Date",
                f"User {user_id} Attempt",
                f"User {user_id} Grade",
                f"User {user_id} Grade Matches Current Submission",
                f"User {user_id} Score",
                f"User {user_id} Grader ID",
                f"User {user_id} Graded At Date",
                f"User {user_id} Late",
                f"User {user_id} Excused",
                f"User {user_id} Missing",
                f"User {user_id} Late Policy Status",
                f"User {user_id} Points Deducted",
                f"User {user_id} Seconds Late",
                f"User {user_id} Extra Attempts",
            ],
        )
        assignments.to_csv(assignments_path, index=False)
        echo("\tGetting discussions...")
        discussions = [
            [discussion.title, discussion.lock_at]
            for discussion in course.get_discussion_topics()
        ]
        echo("\tGetting quizzes...")
        quizzes = [
            [
                quiz.title,
                format_timestamp(quiz.due_at),
                format_timestamp(quiz.unlock_at),
                format_timestamp(quiz.lock_at),
                quiz.points_possible,
            ]
            for quiz in course.get_quizzes()
        ]
        discussions = DataFrame(
            discussions,
            columns=["Name", "Lock Date"],
        )
        discussions.to_csv(discussions_path, index=False)
        quizzes = DataFrame(
            quizzes,
            columns=["Name", "Due Date", "Unlock Date", "Lock Date", "Points Possible"],
        )
        quizzes.to_csv(quizzes_path, index=False)
