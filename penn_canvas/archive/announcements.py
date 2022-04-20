from pathlib import Path
from typing import Optional

from canvasapi.course import Course
from canvasapi.discussion_topic import DiscussionTopic
from pandas import read_csv
from pandas.core.frame import DataFrame
from typer import echo

from penn_canvas.helpers import (
    create_directory,
    print_task_complete_message,
    write_file,
)
from penn_canvas.style import color, print_item

from .helpers import (
    CSV_COMPRESSION_TYPE,
    format_display_text,
    format_name,
    print_unpacked_file,
    strip_tags,
)

ANNOUNCEMENTS_COMPRESSED_FILE = f"announcements.{CSV_COMPRESSION_TYPE}"


def print_announcement(index: int, total: int, title: str, message: str):
    title = color(format_display_text(title, limit=15))
    message = format_display_text(message)
    announcement_display = f"{title}: {message}"
    print_item(index, total, announcement_display)


def get_announcement(announcement: DiscussionTopic) -> list[str]:
    title = format_name(announcement.title)
    message = strip_tags(announcement.message)
    return [title, message]


def unpack_announcements(
    compress_path: Path, unpack_path: Path, force: bool, verbose: bool
) -> Optional[Path]:
    echo(") Unpacking announcements...")
    announcements_path = unpack_path / "Announcements"
    already_complete = not force and announcements_path.exists()
    if already_complete:
        echo("Announcements already unpacked.")
        return None
    announcements_path = create_directory(announcements_path)
    compressed_file = compress_path / ANNOUNCEMENTS_COMPRESSED_FILE
    if not compressed_file.is_file():
        return None
    announcements = read_csv(compressed_file)
    total = len(announcements.index)
    for index, title, message in announcements.itertuples():
        title_path = announcements_path / f"{title}.txt"
        write_file(title_path, message)
        if verbose:
            print_announcement(index, total, title, message)
            print_task_complete_message(announcements_path)
    return announcements_path


def fetch_announcements(
    course: Course,
    compress_path: Path,
    unpack_path: Path,
    unpack: bool,
    force: bool,
    verbose: bool,
):
    echo(") Fetching announcements...")
    announcements_path = compress_path / ANNOUNCEMENTS_COMPRESSED_FILE
    already_complete = not force and announcements_path.is_file()
    if already_complete:
        echo("Announcements already fetched.")
    else:
        announcements: list[DiscussionTopic] = list(
            course.get_discussion_topics(only_announcements=True)
        )
        announcement_data = [
            get_announcement(announcement) for announcement in announcements
        ]
        data_frame = DataFrame(announcement_data, columns=["Title", "Message"])
        data_frame.to_csv(announcements_path, index=False)
        total = len(announcement_data)
        if verbose:
            for index, announcement in enumerate(announcement_data):
                title, message = announcement
                if verbose:
                    print_announcement(index, total, title, message)
    if unpack:
        unpacked_path = unpack_announcements(
            compress_path, unpack_path, force, verbose=False
        )
        if verbose:
            print_unpacked_file(unpacked_path)
