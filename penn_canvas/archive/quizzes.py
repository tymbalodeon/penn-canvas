from pathlib import Path

from canvasapi.course import Course
from canvasapi.quiz import Quiz
from canvasapi.rubric import Rubric
from canvasapi.submission import Submission
from pandas import DataFrame
from typer import echo, progressbar

from penn_canvas.api import collect
from penn_canvas.archive.rubrics import get_rubrics
from penn_canvas.helpers import create_directory
from penn_canvas.style import color, print_item

from .helpers import format_name, strip_tags


def get_quizzes(course: Course) -> tuple[list[Quiz], int]:
    echo(") Finding quizzes...")
    quizzes = collect(course.get_quizzes())
    return quizzes, len(quizzes)


def process_submission(
    questions: dict,
    submission_history: tuple[str, list],
    submissions_path: Path,
    index: int,
    total: int,
    verbose: bool,
):
    name, histories = submission_history
    if verbose:
        print_item(
            index,
            total,
            f"Getting submission data for {color(name)}...",
            prefix="\t\t*",
        )
    for history in histories:
        submission_data = (
            [
                [
                    name,
                    submission_data["correct"],
                    submission_data["points"],
                    questions[submission_data["question_id"]]["question"],
                    strip_tags(submission_data["text"]),
                ]
                for submission_data in history["submission_data"]
            ]
            if "submission_data" in history
            else []
        )
        history_data_frame = DataFrame(
            submission_data,
            columns=["Student", "Correct", "Points", "Question ID", "Text"],
        )
        submission_data_path = (
            submissions_path / f"{name}_submissions_{history['id']}.csv"
        )
        history_data_frame.to_csv(submission_data_path, index=False)


def archive_quiz(
    course: Course,
    quiz: Quiz,
    course_directory: Path,
    verbose: bool,
    index=0,
    total=0,
):
    title = format_name(quiz.title)
    if verbose:
        print_item(index, total, f"{title}")
    description = strip_tags(quiz.description) if quiz.description else quiz.description
    if verbose:
        echo("\t> Getting questions...")
    questions = {
        question.id: {
            "question": strip_tags(question.question_text),
            "answer": ", ".join([answer["text"] for answer in question.answers]),
        }
        for question in quiz.get_questions()
    }
    assignment = course.get_assignment(quiz.assignment_id)
    if verbose:
        echo("\t> Getting submissions...")
    submissions: list[Submission] = collect(
        assignment.get_submissions(include=["submission_history", "user"])
    )
    quiz_directory = create_directory(course_directory / "Quizzes")
    quiz_path = create_directory(quiz_directory / title)
    description_path = quiz_path / f"{title}_DESCRIPTION.txt"
    questions_path = quiz_path / f"{title}_QUESTIONS.csv"
    scores_path = quiz_path / f"{title}_SCORES.csv"
    submissions_path = create_directory(quiz_path / "Submissions")
    submission_histories: list[tuple[str, list]] = [
        (submission.user["name"], submission.submission_history)
        for submission in submissions
    ]
    submissions_total = len(submission_histories)
    for index, submission_history in enumerate(submission_histories):
        process_submission(
            questions,
            submission_history,
            submissions_path,
            index,
            submissions_total,
            verbose,
        )
    if verbose:
        echo("\t> Collecting user scores...")
    points_possible = quiz.points_possible
    submission_scores = [
        [
            submission.user["name"],
            round(submission.score, 2) if submission.score else submission.score,
            points_possible,
        ]
        for submission in submissions
    ]
    user_scores = DataFrame(
        submission_scores, columns=["Student", "Score", "Points Possible"]
    )
    questions_text = [
        [question["question"], question["answers"]] for question in questions.values()
    ]
    questions_data_frame = DataFrame(questions_text, columns=["Question", "Answers"])
    user_scores.to_csv(scores_path, index=False)
    questions_data_frame.to_csv(questions_path, index=False)
    if description:
        if verbose:
            echo("\t> Getting description...")
        with open(description_path, "w") as description_file:
            description_file.write(description)


def archive_quizzes(
    course: Course, course_path: Path, rubrics: list[Rubric], verbose: bool
):
    echo(") Exporting quizzes...")
    quiz_objects, quiz_total = get_quizzes(course)
    if not rubrics:
        rubrics, _ = get_rubrics(course)
    if verbose:
        total = len(quiz_objects)
        for index, quiz in enumerate(quiz_objects):
            archive_quiz(course, quiz, course_path, verbose, index, total)
    else:
        with progressbar(quiz_objects, length=quiz_total) as progress:
            for quiz in progress:
                archive_quiz(course, quiz, course_path, verbose)
