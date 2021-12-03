from datetime import datetime
from pathlib import Path

from pandas.core.frame import DataFrame

from penn_canvas.helpers import get_canvas

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


def format_timestamp(timestamp):
    if timestamp:
        date = datetime.fromisoformat(timestamp.replace("Z", ""))
        return date.strftime("%b %w, %Y (%I:%M:%S %p)")
    else:
        return timestamp


def investigate_main():
    for course_id in course_ids:
        course = canvas.get_course(course_id)
        print(f"Processing {course.name}...")
        course_path = (
            Path.home()
            / "Desktop"
            / course.name.strip().replace(" ", "_").replace("/", "-")
        )
        if not course_path.exists():
            Path.mkdir(course_path)
        assignments_path = course_path / "assignments.csv"
        discussions_path = course_path / "discussions.csv"
        quizzes_path = course_path / "quizzes.csv"
        print("\tGetting assignments...")
        assignments = [
            [
                assignment.name,
                ", ".join(
                    [
                        assignment.replace("_", " ")
                        for assignment in assignment.submission_types
                    ]
                ),
                format_timestamp(assignment.due_at),
                format_timestamp(assignment.unlock_at),
                format_timestamp(assignment.lock_at),
                assignment.points_possible,
            ]
            for assignment in course.get_assignments()
        ]
        print("\tGetting discussions...")
        discussions = [
            [discussion.title, discussion.lock_at]
            for discussion in course.get_discussion_topics()
        ]
        print("\tGetting quizzes...")
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
        assignments = DataFrame(
            assignments,
            columns=[
                "Name",
                "Submission Types",
                "Due Date",
                "Unlock Date",
                "Lock Date",
                "Points Possible",
            ],
        )
        assignments.to_csv(assignments_path, index=False)
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
