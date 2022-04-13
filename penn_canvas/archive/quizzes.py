from functools import lru_cache
from pathlib import Path

from canvasapi.course import Course
from canvasapi.quiz import Quiz, QuizQuestion
from canvasapi.submission import Submission
from pandas import DataFrame
from typer import echo, progressbar

from penn_canvas.helpers import create_directory
from penn_canvas.style import color, print_item

from .helpers import strip_tags


def get_question_text(question: QuizQuestion) -> str:
    return strip_tags(question.question_text)


def get_question_answers(question: QuizQuestion) -> str:
    return " / ".join([answer["text"] for answer in question.answers])


def get_questions_and_answers(quiz: Quiz) -> DataFrame:
    questions = list(quiz.get_questions())
    questions = [
        [get_question_text(question), get_question_answers(question)]
        for question in questions
    ]
    return DataFrame(questions, columns=["Question", "Answers"])


@lru_cache
def get_question(quiz: Quiz, question_id: int) -> str:
    return strip_tags(quiz.get_question(question_id).question_text)


def get_quiz_response(
    submission: dict, quiz: Quiz, name: str, points_possible: str
) -> list[str]:
    correct = submission["correct"]
    points = str(round(submission["points"], 2))
    question_id = submission["question_id"]
    question = get_question(quiz, question_id)
    text = strip_tags(submission["text"])
    return [name, correct, points, points_possible, question, text]


def get_user_responses(history: dict, quiz: Quiz, name: str, points_possible: str):
    if "submission_data" not in history:
        return []
    return [
        get_quiz_response(submission, quiz, name, points_possible)
        for submission in history["submission_data"]
    ]


def get_quiz_responses(
    submissions: list[Submission],
    quiz: Quiz,
    points_possible: str,
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
            submission_data = get_user_responses(
                history, quiz, user_name, points_possible
            )
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


def get_submission_score(submission: Submission, points_possible: str):
    name = submission.user["name"]
    score = str(round(submission.score, 2)) if submission.score else ""
    return [name, score, points_possible]


def get_submission_scores(
    submissions: list[Submission], points_possible: str
) -> list[list[str]]:
    return [
        get_submission_score(submission, points_possible) for submission in submissions
    ]


def get_quiz(
    course: Course,
    quiz: Quiz,
    compress_path: Path,
    verbose: bool,
    index=0,
    total=0,
):
    if verbose:
        print_item(index, total, color(quiz.title))
    quiz_path = create_directory(compress_path / "Quizzes")
    questions = get_questions_and_answers(quiz)
    questions_path = quiz_path / f"{quiz.title}_QUESTIONS.csv"
    questions.to_csv(questions_path, index=False)
    assignment = (
        course.get_assignment(quiz.assignment_id) if quiz.assignment_id else None
    )
    if assignment:
        points_possible = str(quiz.points_possible)
        include_parameters = ["submission_history", "user"]
        submissions = list(assignment.get_submissions(include=include_parameters))
        get_quiz_responses(submissions, quiz, points_possible, quiz_path, verbose)
        submission_scores = get_submission_scores(submissions, points_possible)
        columns = ["Student", "Score", "Points Possible"]
        user_scores = DataFrame(submission_scores, columns=columns)
        scores_path = quiz_path / f"{quiz.title}_SCORES.csv"
        user_scores.to_csv(scores_path, index=False)
    description = strip_tags(quiz.description) if quiz.description else quiz.description
    description_path = quiz_path / f"{quiz.title}_DESCRIPTION.txt"
    if description:
        with open(description_path, "w") as description_file:
            description_file.write(description)


def fetch_quizzes(course: Course, course_path: Path, verbose: bool):
    echo(") Exporting quizzes...")
    quizzes = list(course.get_quizzes())
    total = len(quizzes)
    if verbose:
        for index, quiz in enumerate(quizzes):
            get_quiz(course, quiz, course_path, verbose, index, total)
    else:
        with progressbar(quizzes, length=total) as progress:
            for quiz in progress:
                get_quiz(course, quiz, course_path, verbose)
