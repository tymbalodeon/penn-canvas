from pathlib import Path

from canvasapi.assignment import Assignment
from canvasapi.course import Course
from canvasapi.submission import Submission
from canvasapi.user import User
from pandas import DataFrame
from requests import get
from typer import echo, progressbar

from penn_canvas.api import Instance, collect, get_user
from penn_canvas.archive.archive import format_name, strip_tags
from penn_canvas.helpers import create_directory, format_timestamp
from penn_canvas.style import color, print_item


def get_assignments(course: Course) -> tuple[list[Assignment], int]:
    echo(") Finding assignments...")
    assignments = collect(course.get_assignments())
    return assignments, len(assignments)


def process_comment(comment: dict) -> str:
    author = comment["author_name"]
    created_at = format_timestamp(comment["created_at"])
    edited_at = format_timestamp(comment["edited_at"]) if comment["edited_at"] else ""
    comment = comment["comment"]
    media_comment = (
        comment["media_comment"]["url"] if "media_comment" in comment else ""
    )
    return (
        f"{author}\nCreated: {created_at}\nEdited:"
        f" {edited_at}\n\n{comment}{media_comment}"
    )


def process_submission(
    submission: Submission,
    instance: Instance,
    verbose: bool,
    assignment_index: int,
    total_assignments: int,
    submission_index: int,
    total_submissions: int,
    assignment: str,
    assignment_path: Path,
    comments_path: Path,
) -> list[User | str | int]:
    user = get_user(submission.user_id, instance=instance).name
    try:
        grader = get_user(submission.grader_id, instance=instance).name
    except Exception:
        grader = None
    try:
        grade = round(float(submission.grade), 2)
    except Exception:
        grade = submission.grade
    try:
        score = round(submission.score, 2)
    except Exception:
        score = submission.score
    submissions_path = create_directory(assignment_path / "Submission Files")
    try:
        body = strip_tags(submission.body.replace("\n", " ")).strip()
        with open(
            submissions_path / f"{assignment}_SUBMISSION ({user}).txt", "w"
        ) as submissions_file:
            submissions_file.write(body)
    except Exception:
        body = ""
    try:
        attachments = [
            (attachment["url"], attachment["filename"])
            for attachment in submission.attachments
        ]
        for url, filename in attachments:
            name, extension = filename.split(".")
            with open(
                submissions_path / f"{name} ({user}).{extension}", "wb"
            ) as stream:
                response = get(url, stream=True)
                for chunk in response.iter_content(chunk_size=128):
                    stream.write(chunk)
    except Exception:
        attachments = []
    comments = [process_comment(comment) for comment in submission.submission_comments]
    comments_body = "\n\n".join(comments)
    submission_comments_path = comments_path / f"{assignment}_COMMENTS ({user}).txt"
    with open(submission_comments_path, "w") as submission_comments_file:
        submission_comments_file.write(comments_body)
    if verbose:
        user_display = color(user, "cyan")
        if submission_index == 0:
            color(
                f"==== ASSIGNMENT {assignment_index + 1}/{total_assignments}:"
                f" {assignment} ====",
                "magenta",
                True,
            )
        echo(
            f" - ({submission_index + 1}/{total_submissions})"
            f" {user_display} {color(grade, 'yellow')}"
        )
    return [
        user,
        submission.submission_type.replace("_", " ")
        if submission.submission_type
        else submission.submission_type,
        grade,
        score,
        grader,
    ]


def archive_assignment(
    assignment: Assignment,
    course_directory: Path,
    instance: Instance,
    index=0,
    total=0,
    verbose=False,
):
    assignment_name = format_name(assignment.name)
    assignment_directory = create_directory(course_directory / "Assignments")
    assignment_path = create_directory(assignment_directory / assignment_name)
    description_path = assignment_path / f"{assignment_name}_DESCRIPTION.txt"
    submissions_path = assignment_path / f"{assignment_name}_GRADES.csv"
    comments_path = create_directory(assignment_path / "Submission Comments")
    submissions = collect(assignment.get_submissions(include="submission_comments"))
    submissions = [
        process_submission(
            submission,
            instance,
            verbose,
            index,
            total,
            submission_index,
            len(submissions),
            assignment_name,
            assignment_path,
            comments_path,
        )
        for submission_index, submission in enumerate(submissions)
    ]
    try:
        description = assignment.description.replace("\n", " ")
        description = strip_tags(description).strip().split()
        description = " ".join(description)
    except Exception:
        description = ""
    columns = ["User", "Submission type", "Grade", "Score", "Grader"]
    submissions_data_frame = DataFrame(submissions, columns=columns)
    submissions_data_frame.to_csv(submissions_path, index=False)
    with open(description_path, "w") as assignment_file:
        assignment_file.write(description)
    if verbose:
        print_item(index, total, f"{color(assignment_name)}: {description}")


def archive_assignments(
    course: Course, course_path: Path, instance: Instance, verbose: bool
):
    echo(") Exporting assignments...")
    assignment_objects, assignment_total = get_assignments(course)
    if verbose:
        for index, assignment in enumerate(assignment_objects):
            archive_assignment(
                assignment, course_path, instance, index, assignment_total, verbose
            )
    else:
        with progressbar(assignment_objects, length=assignment_total) as progress:
            for assignment in progress:
                archive_assignment(assignment, course_path, instance)
    return assignment_objects
