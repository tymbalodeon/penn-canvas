from functools import lru_cache
from html.parser import HTMLParser
from io import StringIO
from typing import Optional

from canvasapi.assignment import Assignment
from canvasapi.submission import Submission
from typer import echo

from penn_canvas.style import color

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
    return list(assignment.get_submissions(include="submission_comments"))


@lru_cache
def get_submission_display(submission):
    try:
        submission_display = next(iter(submission.attachments))["display_name"]
    except Exception:
        submission_display = submission
    return color(submission_display, "cyan")


def format_name(name: str) -> str:
    return name.strip().replace("/", "-").replace(":", "-")


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


def should_run_option(option: Optional[bool], archive_all: bool) -> bool:
    return option if isinstance(option, bool) else archive_all


def print_unpacked_file(unpacked_file):
    echo(f"Unpacked to: {color(unpacked_file, 'blue')}")
