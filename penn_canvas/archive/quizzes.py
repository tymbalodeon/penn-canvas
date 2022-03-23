from pathlib import Path

from canvasapi.course import Course
from canvasapi.quiz import Quiz
from pandas import DataFrame
from typer import echo, progressbar

from penn_canvas.api import Instance, collect
from penn_canvas.archive.archive import format_name
from penn_canvas.helpers import create_directory
from penn_canvas.style import print_item

from .archive import strip_tags
from .style import color


def get_quizzes(course: Course) -> tuple[list[Quiz], int]:
    echo(") Finding quizzes...")
    quizzes = collect(course.get_quizzes())
    return quizzes, len(quizzes)


def archive_quiz(course, quiz, verbose, course_directory, index=0, total=0):
    title = format_name(quiz.title)
    if verbose:
        print_item(index, total, f"{title}")
    description = strip_tags(quiz.description) if quiz.description else quiz.description
    if verbose:
        echo("\t> Getting questions...")
    questions = [
        [
            strip_tags(question.question_text),
            ", ".join([answer["text"] for answer in question.answers]),
        ]
        for question in quiz.get_questions()
    ]
    assignment = course.get_assignment(quiz.assignment_id)
    if verbose:
        echo("\t> Getting submissions...")
    submissions = collect(
        assignment.get_submissions(include=["submission_history", "user"])
    )
    QUIZ_DIRECTORY = create_directory(course_directory / "Quizzes")
    quiz_path = create_directory(QUIZ_DIRECTORY / title)
    description_path = quiz_path / f"{title}_DESCRIPTION.txt"
    questions_path = quiz_path / f"{title}_QUESTIONS.csv"
    scores_path = quiz_path / f"{title}_SCORES.csv"
    submissions_path = create_directory(quiz_path / "Submissions")
    submission_histories = [
        (submission.user["name"], submission.submission_history)
        for submission in submissions
    ]
    submissions_total = len(submission_histories)
    for index, submission_history in enumerate(submission_histories):
        name, histories = submission_history
        if verbose:
            print_item(
                index,
                submissions_total,
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
                        submission_data["question_id"],
                        strip_tags(submission_data["text"]),
                    ]
                    for submission_data in history["submission_data"]
                ]
                if "submission_data" in history
                else []
            )
            submission_data = DataFrame(
                submission_data,
                columns=["Student", "Correct", "Points", "Question ID", "Text"],
            )
            submission_data_path = (
                submissions_path / f"{name}_submissions_{history['id']}.csv"
            )
            submission_data.to_csv(submission_data_path, index=False)
    if verbose:
        echo("\t> Collecting user scores...")
    user_scores = [
        [
            submission.user["name"],
            round(submission.score, 2) if submission.score else submission.score,
        ]
        for submission in submissions
    ]
    user_scores = DataFrame(user_scores, columns=["Student", "Score"])
    questions = DataFrame(questions, columns=["Question", "Answers"])
    user_scores.to_csv(scores_path, index=False)
    questions.to_csv(questions_path, index=False)
    if description:
        if verbose:
            echo("\t> Getting description...")
        with open(description_path, "w") as description_file:
            description_file.write(description)


def archive_quizzes(
    course: Course, course_path: Path, instance: Instance, verbose: bool
):
    echo(") Exporting quizzes...")
    quiz_objects, quiz_total = get_quizzes(course)
    if verbose:
        total = len(quiz_objects)
        for index, quiz in enumerate(quiz_objects):
            archive_quiz(course, quiz, verbose, course_path, index, total)
    else:
        with progressbar(quiz_objects, length=quiz_total) as progress:
            for quiz in progress:
                archive_quiz(quiz, verbose, course_path, instance)
