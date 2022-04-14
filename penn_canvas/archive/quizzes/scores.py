from pathlib import Path

from canvasapi.quiz import Quiz
from canvasapi.submission import Submission
from pandas import DataFrame

from penn_canvas.api import Instance, get_user
from penn_canvas.helpers import create_directory


def get_submission_score(
    submission: Submission, points_possible: str, instance: Instance
):
    name = get_user(submission.user_id, instance=instance).name
    score = str(round(submission.score, 2)) if submission.score else ""
    return [name, score, points_possible]


def get_submission_scores(
    submissions: list[Submission], quiz: Quiz, quiz_path: Path, instance: Instance
):
    points_possible = quiz.points_possible
    submission_scores = [
        get_submission_score(submission, points_possible, instance)
        for submission in submissions
    ]
    columns = ["Student", "Score", "Points Possible"]
    user_scores = DataFrame(submission_scores, columns=columns)
    scores_path = quiz_path / f"{quiz.title}_SCORES.csv"
    user_scores.to_csv(scores_path, index=False)


def get_all_submission_scores(
    quizzes: list[Quiz], compress_path: Path, instance: Instance
):
    for quiz in quizzes:
        quiz_path = create_directory(compress_path / "Quizzes")
        submissions = list(quiz.get_submissions())
        get_submission_scores(submissions, quiz, quiz_path, instance)
