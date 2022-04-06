from pathlib import Path
from shutil import make_archive, rmtree, unpack_archive
from typing import Optional

from canvasapi.course import Course
from canvasapi.discussion_topic import DiscussionEntry, DiscussionTopic
from pandas import DataFrame
from pandas.core.reshape.concat import concat
from typer import echo, progressbar

from penn_canvas.api import Instance, get_user
from penn_canvas.helpers import create_directory, format_timestamp
from penn_canvas.style import color, print_item

from .helpers import (
    CSV_COMPRESSION_TYPE,
    TAR_COMPRESSION_TYPE,
    TAR_EXTENSION,
    format_display_text,
    format_name,
    format_text,
    print_unpacked_file,
)

DISCUSSIONS_TAR_STEM = "discussions"
DISCUSSIONS_TAR_NAME = f"{DISCUSSIONS_TAR_STEM}.{TAR_EXTENSION}"
UNPACK_DISCUSSIONS_DIRECTORY = DISCUSSIONS_TAR_STEM.title()
DISCUSSION_ENTRIES_COMPRESSED_FILE = f"discussion_entries.{CSV_COMPRESSION_TYPE}"
DISCUSSION_DESCRIPTIONS_COMPRESSED_FILE = (
    f"discussion_descriptions.{CSV_COMPRESSION_TYPE}"
)
DISCUSSION_ID = "Discussion ID"
DISCUSSION_TITLE = "Discussion Title"


def get_entry(
    entry: DiscussionEntry,
    discussion_id: str,
    discussion_title: str,
    instance: Instance,
    verbose: bool,
    index: int,
    total: int,
) -> list[str]:
    user_id = entry.user["id"]
    user = entry.user["display_name"]
    email = get_user(user_id, instance=instance).email
    timestamp = format_timestamp(entry.created_at)
    message = format_text(entry.message)
    if verbose:
        user_display = color(user, "cyan")
        timestamp_display = color(timestamp, "yellow")
        entry_display = (
            f"{user_display} {timestamp_display} {format_display_text(message)}"
        )
        print_item(index, total, entry_display, prefix="\t*")
    return [discussion_id, discussion_title, user_id, user, email, timestamp, message]


def get_discussion_description(
    discussion: DiscussionTopic, verbose: bool, index: int, total: int
) -> list[str]:
    discussion_title = discussion.title
    description = format_text(discussion.message)
    if verbose:
        message = f"{color(discussion_title)}: {format_display_text(description)}"
        print_item(index, total, message)
    return [discussion.id, discussion_title, description]


def get_discussion_descriptions(
    discussions: list[DiscussionTopic], verbose: bool
) -> DataFrame:
    echo(") Exporting discussion descriptions..")
    total = len(discussions)
    descriptions = [
        get_discussion_description(discussion, verbose, index, total)
        for index, discussion in enumerate(discussions)
    ]
    columns = [DISCUSSION_ID, DISCUSSION_TITLE, "Description"]
    return DataFrame(descriptions, columns=columns)


def get_discussion_entries(
    discussion: DiscussionTopic,
    instance: Instance,
    verbose: bool,
    index=0,
    total=0,
) -> DataFrame:
    if verbose:
        discussion_title_display = format_name(discussion.title)
        print_item(index, total, color(discussion_title_display))
    entries = list(discussion.get_topic_entries())
    entries_total = len(entries)
    entries = [
        get_entry(
            entry,
            discussion.id,
            discussion.title,
            instance,
            verbose,
            entry_index,
            entries_total,
        )
        for entry_index, entry in enumerate(entries)
    ]
    columns = [
        DISCUSSION_ID,
        DISCUSSION_TITLE,
        "User ID",
        "User",
        "Email",
        "Timestamp",
        "Message",
    ]
    return DataFrame(entries, columns=columns)


def unpack_discussions(
    compress_path: Path, unpack_path: Path, verbose: bool
) -> Optional[Path]:
    archive_file = compress_path / DISCUSSIONS_TAR_NAME
    if not archive_file.is_file():
        return None
    discussions_path = compress_path / DISCUSSIONS_TAR_STEM
    unpack_archive(archive_file, discussions_path)
    unpack_discussions_path = create_directory(
        unpack_path / UNPACK_DISCUSSIONS_DIRECTORY, clear=True
    )
    discussions_path.replace(unpack_discussions_path)
    if verbose:
        print_unpacked_file(unpack_discussions_path)
    return unpack_discussions_path


def fetch_discussions(
    course: Course,
    compress_path: Path,
    unpack_path: Path,
    unpack: bool,
    instance: Instance,
    verbose: bool,
):
    echo(") Exporting discussions...")
    discussion_topics = list(course.get_discussion_topics())
    total = len(discussion_topics)
    if verbose:
        descriptions = get_discussion_descriptions(discussion_topics, verbose)
        echo(") Exporting discussion entries...")
        discussion_entries = [
            get_discussion_entries(discussion, instance, verbose, index, total)
            for index, discussion in enumerate(discussion_topics)
        ]
    else:
        with progressbar(discussion_topics, length=total) as progress:
            descriptions = get_discussion_descriptions(discussion_topics, verbose)
            discussion_entries = [
                get_discussion_entries(discussion, instance, verbose)
                for discussion in progress
            ]
    discussions_path = create_directory(compress_path / DISCUSSIONS_TAR_STEM)
    descriptions_path = discussions_path / DISCUSSION_DESCRIPTIONS_COMPRESSED_FILE
    descriptions.to_csv(descriptions_path, index=False)
    discussion_entries_data = concat(discussion_entries)
    discussion_entries_path = discussions_path / DISCUSSION_ENTRIES_COMPRESSED_FILE
    discussion_entries_data.to_csv(discussion_entries_path, index=False)
    discussions_directory = str(discussions_path)
    make_archive(
        discussions_directory, TAR_COMPRESSION_TYPE, root_dir=discussions_directory
    )
    if unpack:
        unpacked_path = unpack_discussions(compress_path, unpack_path, verbose=False)
        if verbose:
            print_unpacked_file(unpacked_path)
    else:
        rmtree(discussions_path)
