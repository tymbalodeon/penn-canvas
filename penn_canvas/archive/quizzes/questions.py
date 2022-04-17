from pathlib import Path

from canvasapi.quiz import Quiz, QuizQuestion
from pandas import DataFrame

from penn_canvas.archive.helpers import format_name, format_question_text
from penn_canvas.helpers import create_directory


def get_question_answers(question: QuizQuestion) -> str:
    return " / ".join([answer["text"] for answer in question.answers])


def get_questions_and_answers(quiz: Quiz) -> DataFrame:
    questions = list(quiz.get_questions())
    questions = [
        [format_question_text(question), get_question_answers(question)]
        for question in questions
    ]
    return DataFrame(questions, columns=["Question", "Answers"])


def get_quiz_questions(quiz: Quiz, quizzes_path: Path):
    questions = get_questions_and_answers(quiz)
    quiz_path = create_directory(quizzes_path / format_name(quiz.title))
    questions_path = quiz_path / "Questions.csv"
    questions.to_csv(questions_path, index=False)


def fetch_quiz_questions(quizzes: list[Quiz], quiz_path: Path):
    for quiz in quizzes:
        get_quiz_questions(quiz, quiz_path)
