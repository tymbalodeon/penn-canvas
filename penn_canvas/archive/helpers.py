from functools import lru_cache
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from tarfile import open as open_tarfile
from typing import Optional

from canvasapi.assignment import Assignment
from canvasapi.quiz import QuizQuestion
from canvasapi.submission import Submission
from loguru import logger
from typer import echo

from penn_canvas.style import color, print_item

COMPRESSION_TYPE = "gz"
CSV_COMPRESSION_TYPE = f"csv.{COMPRESSION_TYPE}"
TAR_COMPRESSION_TYPE = f"{COMPRESSION_TYPE}tar"
TAR_EXTENSION = f"tar.{COMPRESSION_TYPE}"


class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, data):
        self.text.write(data)

    def get_data(self):
        return self.text.getvalue()


def strip_tags(html: str) -> str:
    stripper = HTMLStripper()
    stripper.feed(html)
    return stripper.get_data()


@lru_cache
def get_assignment_submissions(assignment: Assignment) -> list[Submission]:
    return list(assignment.get_submissions(include=["submission_comments", "user"]))


@lru_cache
def get_submission_display(submission):
    try:
        submission_display = next(iter(submission.attachments))["display_name"]
    except Exception:
        submission_display = submission
    return color(submission_display, "cyan")


def format_name(name: str) -> str:
    return name.strip().replace("/", "-").replace(":", "-")


def format_text(parsed_text: str) -> str:
    try:
        return strip_tags(parsed_text).strip()
    except Exception:
        return ""


@lru_cache
def format_display_text(text: str, limit=50) -> str:
    truncated = len(text) > limit
    text = text.replace("\n", " ").replace("\t", " ").strip()[:limit]
    if truncated:
        final_character = text[-1]
        while final_character == " " or final_character == ".":
            text = text[:-1]
            final_character = text[-1]
        text = f"{text}..."
    return text


@lru_cache
def format_question_text(question: QuizQuestion) -> str:
    return strip_tags(question.question_text)


def print_description(index, total, title, description, prefix=""):
    assignment_display = color(format_display_text(title), "yellow")
    description_display = color(format_display_text(description), "cyan")
    message = f"{assignment_display}: {description_display}"
    print_item(index, total, message, prefix=prefix)


def print_unpacked_file(unpacked_path: Optional[Path]):
    if unpacked_path:
        echo(f"Unpacked to: {color(unpacked_path, 'blue')}")
    else:
        message = "ERROR: failed to unpack."
        logger.error(message)
        echo(message)


def extract_from_tar_file(file_name: str, tar_file: Path, destination: Path):
    with open_tarfile(tar_file) as archive:
        archive.extract(file_name, destination)
