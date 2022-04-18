from pathlib import Path

from canvasapi.quiz import Quiz, QuizQuestion
from pandas import DataFrame
from pandas.core.reshape.concat import concat

from penn_canvas.archive.helpers import format_question_text


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


def fetch_quiz_questions(quizzes: list[Quiz], quiz_path: Path):
    questions = [get_questions_and_answers(quiz) for quiz in quizzes]
    questions_data = concat(questions)
    questions_data.to_csv(quiz_path / "questions.csv.gz", index=False)
