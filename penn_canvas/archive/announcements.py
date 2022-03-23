from pathlib import Path

from canvasapi.course import Course
from canvasapi.discussion_topic import DiscussionTopic
from pandas.core.frame import DataFrame
from pandas.io.pickle import read_pickle
from typer import echo

from penn_canvas.api import collect
from penn_canvas.helpers import create_directory
from penn_canvas.style import color, print_item

from .helpers import (
    PICKLE_COMPRESSION_TYPE,
    format_display_text,
    format_name,
    strip_tags,
)

ANNOUNCEMENTS_PICKLE_FILE = "announcements.pickle"


def process_announcement(announcement: DiscussionTopic) -> list[str]:
    title = format_name(announcement.title)
    message = strip_tags(announcement.message)
    return [title, message]


def display_announcement(index: int, total: int, title: str, message: str):
    title = color(format_display_text(title, limit=15))
    message = format_display_text(message)
    announcement_display = f"{title}: {message}"
    print_item(index, total, announcement_display)


def archive_announcements(course: Course, course_path: Path, verbose: bool):
    echo(") Exporting announcements...")
    announcements: list[DiscussionTopic] = collect(
        course.get_discussion_topics(only_announcements=True)
    )
    announcement_data: list[list[str]] = [
        process_announcement(announcement) for announcement in announcements
    ]
    data_frame = DataFrame(announcement_data, columns=["Title", "Message"])
    announcements_path = course_path / ANNOUNCEMENTS_PICKLE_FILE
    data_frame.to_pickle(announcements_path, compression=PICKLE_COMPRESSION_TYPE)
    total = len(announcement_data)
    if verbose:
        for index, announcement in enumerate(announcement_data):
            title, message = announcement
            if verbose:
                display_announcement(index, total, title, message)


def unpickle_announcements(course_path: Path, verbose: bool):
    data_frame = read_pickle(
        course_path / ANNOUNCEMENTS_PICKLE_FILE, compression=PICKLE_COMPRESSION_TYPE
    )
    announcements: list[list[str]] = data_frame.values.tolist()
    announcements_path = create_directory(course_path / "Announcements")
    total = len(announcements)
    for index, announcement in enumerate(announcements):
        title, message = announcement
        title_path = announcements_path / f"{title}.txt"
        with open(title_path, "w") as announcement_file:
            announcement_file.write(message)
        if verbose:
            display_announcement(index, total, title, message)
