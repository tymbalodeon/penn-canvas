from datetime import datetime, timedelta
from pathlib import Path

from pandas import DataFrame, read_csv
from typer import Exit, echo

from penn_canvas.helpers import BOX_PATH, TODAY_AS_Y_M_D, color, get_canvas

COMMAND = "Investigate"
INPUT_FILE_NAME = "Input file"
RESULTS = BOX_PATH / "OGC Request"
INPUT_FILE_NAME = RESULTS / "investigate.csv"


def get_investigate_input_file():
    input_file = next(
        (
            csv_file
            for csv_file in RESULTS.glob("*csv")
            if "investigate" in csv_file.name and TODAY_AS_Y_M_D in csv_file.name
        ),
        None,
    )
    if not input_file:
        echo(
            "An \"investigate csv file matching today's date was not found. Please add"
            " one and try again."
        )
        raise Exit()
    else:
        return input_file


def format_timestamp(timestamp):
    if timestamp:
        date = datetime.fromisoformat(timestamp.replace("Z", ""))
        return date.strftime("%b %w, %Y (%I:%M:%S %p)")
    else:
        return None


def get_submitted_at_date(submission):
    try:
        return format_timestamp(submission.submitted_at)
    except Exception:
        return None


def get_grader(grader_id, canvas):
    try:
        return canvas.get_user(grader_id) if grader_id > 0 else None
    except Exception:
        return None


def process_assignment(assignment, user_id, canvas, index, total):
    name = assignment.name
    submission_types = ", ".join(
        [assignment.replace("_", " ") for assignment in assignment.submission_types]
    )
    due_date = format_timestamp(assignment.due_at)
    unlock_date = format_timestamp(assignment.unlock_at)
    lock_date = format_timestamp(assignment.lock_at)
    points_possible = assignment.points_possible
    submission = next(
        submission
        for submission in assignment.get_submissions(include="submission_comments")
        if submission.user_id == user_id
    )
    submitted_at = get_submitted_at_date(submission)
    attempt = submission.attempt
    grade = submission.grade
    grade_matches_current_submission = submission.grade_matches_current_submission
    score = submission.score
    grader_id = get_grader(submission.grader_id, canvas)
    graded_at = format_timestamp(submission.graded_at)
    late = submission.late
    excused = submission.excused
    missing = submission.missing
    late_policy_status = submission.late_policy_status
    points_deducted = submission.points_deducted
    seconds_late = timedelta(seconds=submission.seconds_late)
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
    late_display = "LATE" if late else "ON TIME"
    echo(
        f" - ({index + 1:,}/{total:,}) {color(name)}:"
        f" {color(late_display, 'red' if late else 'green')}"
    )
    return assignment_row


def investigate_main():
    input_file = get_investigate_input_file()
    try:
        user_id = next(iter(read_csv(input_file)["Canvas User ID"].tolist()))
        course_ids = read_csv(input_file)["Canvas Course ID"].tolist()
    except Exception:
        echo("The input file is not formatted correctly. Please update and try again.")
        raise Exit()
    canvas = get_canvas()
    canvas_user = canvas.get_user(user_id)
    echo(f"Investigating student {canvas_user.name}...")
    for course_id in course_ids:
        course = canvas.get_course(course_id)
        echo(f"Processing {course.name}...")
        course_path = RESULTS / course.name.strip().replace(" ", "_").replace("/", "-")
        if not course_path.exists():
            Path.mkdir(course_path)
        assignments_path = course_path / "assignments.csv"
        discussions_path = course_path / "discussions.csv"
        quizzes_path = course_path / "quizzes.csv"
        echo("\tGetting assignments...")
        assignments = [assignment for assignment in course.get_assignments()]
        assignments_rows = [
            process_assignment(assignment, user_id, canvas, index, len(assignments))
            for index, assignment in enumerate(assignments)
        ]
        assignments = DataFrame(
            assignments_rows,
            columns=[
                "Name",
                "Submission Types",
                "Due Date",
                "Unlock Date",
                "Lock Date",
                "Points Possible",
                f"Submitted At Date",
                f"Attempt",
                f"Grade",
                f"Grade Matches Current Submission",
                f"Score",
                f"Grader ID",
                f"Graded At Date",
                f"Late",
                f"Excused",
                f"Missing",
                f"Late Policy Status",
                f"Points Deducted",
                f"Seconds Late",
                f"Extra Attempts",
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
