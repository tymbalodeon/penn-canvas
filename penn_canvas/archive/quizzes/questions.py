from os import remove
from pathlib import Path
from tarfile import open as open_tarfile
from typing import Optional

from canvasapi.quiz import Quiz, QuizQuestion
from pandas import DataFrame, read_csv
from pandas.core.reshape.concat import concat
from typer import echo

from penn_canvas.archive.assignments.assignment_descriptions import QUIZ_ID
from penn_canvas.archive.helpers import format_name, format_question_text
from penn_canvas.helpers import create_directory
from penn_canvas.style import color, print_item


def get_question_answers(question: QuizQuestion) -> str:
    return " / ".join([answer["text"] for answer in question.answers])


def get_questions_and_answers(quiz: Quiz) -> DataFrame:
    questions = list(quiz.get_questions())
    questions = [
        [
            quiz.id,
            quiz.title,
            format_question_text(question),
            get_question_answers(question),
        ]
        for question in questions
    ]
    return DataFrame(
        questions, columns=["Quiz ID", "Quiz Title", "Question", "Answers"]
    )


def unpack_quiz_questions(
    compress_path: Path, archive_tar_path: Path, unpack_path: Path, verbose: bool
) -> Optional[Path]:
    echo("Unpacking quiz questions...")
    quizzes_tar_file = open_tarfile(archive_tar_path)
    quizzes_tar_file.extract("./questions.csv.gz", compress_path)
    unpacked_questions_path = compress_path / "questions.csv.gz"
    questions_data = read_csv(unpacked_questions_path)
    questions_data.fillna("", inplace=True)
    quiz_ids = questions_data[QUIZ_ID].unique()
    quizzes = [
        questions_data[questions_data[QUIZ_ID] == quiz_id] for quiz_id in quiz_ids
    ]
    total = len(quizzes)
    for index, quiz in enumerate(quizzes):
        quiz = quiz.drop(columns=QUIZ_ID)
        quiz_title = next(iter(quiz["Quiz Title"].tolist()), "")
        quiz_title = format_name(quiz_title)
        if verbose:
            print_item(index, total, color(quiz_title))
        questions_path = create_directory(unpack_path / quiz_title) / "Questions.csv"
        quiz.to_csv(questions_path, index=False)
    remove(compress_path / "questions.csv.gz")
    return unpack_path


def fetch_quiz_questions(quizzes: list[Quiz], quiz_path: Path):
    questions = [get_questions_and_answers(quiz) for quiz in quizzes]
    questions_data = concat(questions)
    questions_data.to_csv(quiz_path / "questions.csv.gz", index=False)
