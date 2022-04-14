from pathlib import Path

from canvasapi.assignment import Assignment
from canvasapi.course import Course
from canvasapi.quiz import Quiz
from canvasapi.submission import Submission
from pandas import DataFrame

from penn_canvas.api import Instance
from penn_canvas.archive.helpers import format_question_text, strip_tags
from penn_canvas.helpers import create_directory
from penn_canvas.style import color, print_item


def get_assignment_submissions(assignment: Assignment) -> list[Submission]:
    include_parameters = ["submission_history", "user"]
    return list(assignment.get_submissions(include=include_parameters))


def get_question_text(question_id: int, quiz: Quiz) -> str:
    question = quiz.get_question(question_id)
    return format_question_text(question)


def get_quiz_response(submission: dict, quiz: Quiz, name: str) -> list[str]:
    correct = submission["correct"]
    points = str(round(submission["points"], 2))
    points_possible = quiz.points_possible
    question_id = submission["question_id"]
    question = get_question_text(question_id, quiz)
    text = strip_tags(submission["text"])
    return [name, correct, points, points_possible, question, text]


def get_user_responses(history: dict, quiz: Quiz, name: str):
    if "submission_data" not in history:
        return []
    return [
        get_quiz_response(submission, quiz, name)
        for submission in history["submission_data"]
    ]


def get_quiz_responses(
    submissions: list[Submission],
    quiz: Quiz,
    quiz_path: Path,
    verbose: bool,
):
    total = len(submissions)
    for index, submission in enumerate(submissions):
        histories = submission.submission_history
        user_name = submission.user["name"]
        if verbose:
            message = f"Getting submission data for {color(user_name, 'cyan')}..."
            print_item(index, total, message, prefix="\t*")
        for history in histories:
            submission_data = get_user_responses(history, quiz, user_name)
            columns = [
                "Student",
                "Correct",
                "Points",
                "Points Possible",
                "Question",
                "Text",
            ]
            history_data_frame = DataFrame(submission_data, columns=columns)
            file_name = f"{user_name}_submissions_{history['id']}.csv"
            submissions_path = create_directory(quiz_path / "Submissions")
            submission_data_path = submissions_path / file_name
            history_data_frame.to_csv(submission_data_path, index=False)


def get_all_quiz_responses(
    course: Course,
    compress_path: Path,
    instance: Instance,
    verbose: bool,
):
    assignments = list(
        assignment
        for assignment in course.get_assignments()
        if assignment.is_quiz_assignment
    )
    quiz_path = create_directory(compress_path / "Quizzes")
    for assignment in assignments:
        quiz = course.get_quiz(assignment.quiz_id, instance=instance)
        submissions = get_assignment_submissions(assignment)
        get_quiz_responses(submissions, quiz, quiz_path, verbose)
