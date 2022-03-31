from pathlib import Path

from canvasapi.course import Course
from canvasapi.discussion_topic import DiscussionTopic
from pandas import read_csv
from pandas.core.frame import DataFrame
from typer import echo

from penn_canvas.api import collect
from penn_canvas.helpers import create_directory, print_task_complete_message
from penn_canvas.style import color, print_item

from .helpers import COMPRESSION_TYPE, format_display_text, format_name, strip_tags

ANNOUNCEMENTS_COMPRESSED_FILE = f"announcements.{COMPRESSION_TYPE}"


def process_announcement(announcement: DiscussionTopic) -> list[str]:
    title = format_name(announcement.title)
    message = strip_tags(announcement.message)
    return [title, message]


def display_announcement(index: int, total: int, title: str, message: str):
    title = color(format_display_text(title, limit=15))
    message = format_display_text(message)
    announcement_display = f"{title}: {message}"
    print_item(index, total, announcement_display)


def unpack_announcements(course_path: Path, verbose: bool):
    echo(") Unpacking announcements...")
    data_frame = read_csv(course_path / ANNOUNCEMENTS_COMPRESSED_FILE)
    announcements = data_frame.values.tolist()
    announcements_path = create_directory(course_path / "Announcements")
    total = len(announcements)
    for index, announcement in enumerate(announcements):
        title, message = announcement
        title_path = announcements_path / f"{title}.txt"
        with open(title_path, "w") as announcement_file:
            announcement_file.write(message)
        if verbose:
            display_announcement(index, total, title, message)
            print_task_complete_message(announcements_path)


def archive_announcements(
    course: Course, course_path: Path, unpack: bool, verbose: bool
):
    echo(") Exporting announcements...")
    announcements: list[DiscussionTopic] = collect(
        course.get_discussion_topics(only_announcements=True)
    )
    announcement_data = [
        process_announcement(announcement) for announcement in announcements
    ]
    data_frame = DataFrame(announcement_data, columns=["Title", "Message"])
    announcements_path = course_path / ANNOUNCEMENTS_COMPRESSED_FILE
    data_frame.to_csv(announcements_path, index=False)
    total = len(announcement_data)
    if verbose:
        for index, announcement in enumerate(announcement_data):
            title, message = announcement
            if verbose:
                display_announcement(index, total, title, message)
    if unpack:
        unpack_announcements(course_path, verbose=False)
