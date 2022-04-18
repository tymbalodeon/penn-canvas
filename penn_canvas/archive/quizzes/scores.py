from pathlib import Path

from canvasapi.quiz import Quiz
from canvasapi.submission import Submission
from pandas import DataFrame
from pandas.core.reshape.concat import concat

from penn_canvas.api import Instance, get_user


def get_submission_score(
    submission: Submission, points_possible: str, instance: Instance
):
    name = get_user(submission.user_id, instance=instance).name
    score = str(round(submission.score, 2)) if submission.score else ""
    return [name, score, points_possible]


def get_submission_scores(
    submissions: list[Submission], quiz: Quiz, quizzes_path: Path, instance: Instance
) -> DataFrame:
    points_possible = quiz.points_possible
    submission_scores = [
        [quiz.id, quiz.title]
        + get_submission_score(submission, points_possible, instance)
        for submission in submissions
    ]
    columns = ["Quiz ID", "Quiz Title", "Student", "Score", "Points Possible"]
    return DataFrame(submission_scores, columns=columns)


def fetch_submission_scores(quizzes: list[Quiz], quiz_path: Path, instance: Instance):
    scores = list()
    for quiz in quizzes:
        submissions = list(quiz.get_submissions())
        scores.append(get_submission_scores(submissions, quiz, quiz_path, instance))
    scores_data = concat(scores)
    scores_data.to_csv(quiz_path / "scores.csv.gz", index=False)
