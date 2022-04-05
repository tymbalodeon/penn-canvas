from pathlib import Path
from typing import Optional

from canvasapi.course import Course
from canvasapi.discussion_topic import DiscussionTopic
from pandas import read_csv
from pandas.core.frame import DataFrame
from typer import echo

from penn_canvas.helpers import create_directory, print_task_complete_message
from penn_canvas.style import color, print_item

from .helpers import (
    CSV_COMPRESSION_TYPE,
    format_display_text,
    format_name,
    print_unpacked_file,
    strip_tags,
)

ANNOUNCEMENTS_COMPRESSED_FILE = f"announcements.{CSV_COMPRESSION_TYPE}"


def display_announcement(index: int, total: int, title: str, message: str):
    title = color(format_display_text(title, limit=15))
    message = format_display_text(message)
    announcement_display = f"{title}: {message}"
    print_item(index, total, announcement_display)


def process_announcement(announcement: DiscussionTopic) -> list[str]:
    title = format_name(announcement.title)
    message = strip_tags(announcement.message)
    return [title, message]


def unpack_announcements(
    compress_path: Path, unpack_path: Path, verbose: bool
) -> Optional[Path]:
    echo(") Unpacking announcements...")
    compressed_file = compress_path / ANNOUNCEMENTS_COMPRESSED_FILE
    if not compressed_file.is_file():
        return None
    data_frame = read_csv(compressed_file)
    announcements = data_frame.values.tolist()
    announcements_path = create_directory(unpack_path / "Announcements")
    total = len(announcements)
    for index, announcement in enumerate(announcements):
        title, message = announcement
        title_path = announcements_path / f"{title}.txt"
        with open(title_path, "w") as announcement_file:
            announcement_file.write(message)
        if verbose:
            display_announcement(index, total, title, message)
            print_task_complete_message(announcements_path)
    return announcements_path


def fetch_announcements(
    course: Course,
    compress_path: Path,
    unpack_path: Path,
    unpack: bool,
    verbose: bool,
):
    echo(") Exporting announcements...")
    announcements: list[DiscussionTopic] = list(
        course.get_discussion_topics(only_announcements=True)
    )
    announcement_data = [
        process_announcement(announcement) for announcement in announcements
    ]
    data_frame = DataFrame(announcement_data, columns=["Title", "Message"])
    announcements_path = compress_path / ANNOUNCEMENTS_COMPRESSED_FILE
    data_frame.to_csv(announcements_path, index=False)
    total = len(announcement_data)
    if verbose:
        for index, announcement in enumerate(announcement_data):
            title, message = announcement
            if verbose:
                display_announcement(index, total, title, message)
    if unpack:
        unpacked_path = unpack_announcements(compress_path, unpack_path, verbose=False)
        if verbose:
            print_unpacked_file(unpacked_path)
