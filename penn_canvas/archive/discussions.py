from os import remove
from pathlib import Path
from shutil import make_archive, rmtree, unpack_archive
from typing import Optional

from canvasapi.course import Course
from canvasapi.discussion_topic import DiscussionEntry, DiscussionTopic
from pandas import DataFrame, read_csv
from pandas.core.reshape.concat import concat
from typer import echo, progressbar

from penn_canvas.api import Instance, get_user
from penn_canvas.helpers import (
    create_directory,
    format_timestamp,
    print_task_complete_message,
    write_file,
)
from penn_canvas.style import color, print_item

from .helpers import (
    CSV_COMPRESSION_TYPE,
    TAR_COMPRESSION_TYPE,
    TAR_EXTENSION,
    format_display_text,
    format_name,
    format_text,
    print_description,
    print_unpacked_file,
)

DISCUSSIONS_TAR_STEM = "discussions"
DISCUSSIONS_TAR_NAME = f"{DISCUSSIONS_TAR_STEM}.{TAR_EXTENSION}"
UNPACK_DISCUSSIONS_DIRECTORY = DISCUSSIONS_TAR_STEM.title()
UNPACK_DESCRIPTIONS_DIRECTORY = "Descriptions"
UNPACK_ENTRIES_DIRECTORY = "Entries"
ENTRIES_COMPRESSED_FILE = f"discussion_entries.{CSV_COMPRESSION_TYPE}"
DESCRIPTIONS_COMPRESSED_FILE = f"discussion_descriptions.{CSV_COMPRESSION_TYPE}"
DISCUSSION_ID = "Discussion ID"
DISCUSSION_TITLE = "Discussion Title"
USER_ID = "User ID"


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
    echo(") Fetching discussion descriptions..")
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
        USER_ID,
        "User Name",
        "Email",
        "Timestamp",
        "Message",
    ]
    return DataFrame(entries, columns=columns)


def unpack_descriptions(compress_path: Path, unpack_path: Path, verbose: bool):
    echo(") Unpacking discussion descriptions...")
    compressed_file = compress_path / DESCRIPTIONS_COMPRESSED_FILE
    if not compressed_file.is_file():
        return None
    descriptions_data = read_csv(compressed_file)
    descriptions_data.drop(DISCUSSION_ID, axis=1, inplace=True)
    descriptions_data.fillna("", inplace=True)
    descriptions_path = create_directory(unpack_path / UNPACK_DESCRIPTIONS_DIRECTORY)
    total = len(descriptions_data.index)
    for index, discussion_title, description in descriptions_data.itertuples():
        description_file = descriptions_path / f"{format_name(discussion_title)}.txt"
        text = f'"{discussion_title}"\n\n{description}'
        write_file(description_file, text)
        if verbose:
            print_description(index, total, discussion_title, description, prefix="\t*")
    if verbose:
        print_task_complete_message(descriptions_path)
    remove(compressed_file)
    return descriptions_path


def get_unpack_entries(entries_data: DataFrame, discussion_id: str) -> DataFrame:
    entries = entries_data[entries_data[DISCUSSION_ID] == discussion_id]
    entries = entries.drop([DISCUSSION_ID, USER_ID], axis=1)
    entries = entries.fillna("")
    entries = entries.reset_index(drop=True)
    return entries


def unpack_entries(compress_path: Path, unpack_path: Path, verbose: bool):
    echo(") Unpacking discussion entries...")
    compressed_file = compress_path / ENTRIES_COMPRESSED_FILE
    if not compressed_file.is_file():
        return None
    entries_data = read_csv(compressed_file)
    discussion_ids = entries_data[DISCUSSION_ID].unique()
    discussions = [
        get_unpack_entries(entries_data, discussion_id)
        for discussion_id in discussion_ids
    ]
    entries_path = create_directory(unpack_path / UNPACK_DESCRIPTIONS_DIRECTORY)
    total = len(discussions)
    for index, discussion in enumerate(discussions):
        if verbose:
            discussion_title = next(iter(discussion[DISCUSSION_TITLE].tolist()), "")
            print_item(index, total, color(discussion_title))
        entries_total = len(discussion.index)
        for (
            entry_index,
            title,
            user_name,
            email,
            timestamp,
            message,
        ) in discussion.itertuples():
            entry_file = entries_path / f"{format_name(title)}.txt"
            text = f"\n{user_name} ({email})\n{timestamp}\n\n{message}\n"
            write_file(entry_file, text)
            if verbose:
                print_description(entry_index, entries_total, title, text, prefix="\t*")
    if verbose:
        print_task_complete_message(entries_path)
    remove(compressed_file)
    return entries_path


def unpack_discussions(
    compress_path: Path, unpack_path: Path, force: bool, verbose: bool
) -> Optional[Path]:
    echo(") Unpacking discussions...")
    unpack_discussions_path = unpack_path / UNPACK_DISCUSSIONS_DIRECTORY
    archive_file = compress_path / DISCUSSIONS_TAR_NAME
    already_complete = not force and archive_file.exists()
    if already_complete:
        echo("Discussions already unpacked.")
        return None
    if not archive_file.is_file():
        return None
    discussions_path = compress_path / DISCUSSIONS_TAR_STEM
    unpack_archive(archive_file, discussions_path)
    unpack_discussions_path = create_directory(unpack_discussions_path, clear=True)
    unpack_descriptions_path = unpack_discussions_path / UNPACK_DESCRIPTIONS_DIRECTORY
    unpack_entries_path = unpack_discussions_path / UNPACK_ENTRIES_DIRECTORY
    unpack_descriptions(discussions_path, unpack_descriptions_path, verbose)
    unpack_entries(discussions_path, unpack_entries_path, verbose)
    rmtree(discussions_path)
    if verbose:
        print_unpacked_file(unpack_discussions_path)
    return unpack_discussions_path


def fetch_discussions(
    course: Course,
    compress_path: Path,
    unpack_path: Path,
    unpack: bool,
    force: bool,
    instance: Instance,
    verbose: bool,
):
    echo(") Fetching discussions...")
    archive_file = compress_path / DISCUSSIONS_TAR_NAME
    already_complete = not force and archive_file.is_file()
    if already_complete:
        echo("Discussions already fetched.")
    else:
        discussion_topics = list(course.get_discussion_topics())
        total = len(discussion_topics)
        if verbose:
            descriptions = get_discussion_descriptions(discussion_topics, verbose)
            echo(") Fetching discussion entries...")
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
        descriptions_path = discussions_path / DESCRIPTIONS_COMPRESSED_FILE
        descriptions.to_csv(descriptions_path, index=False)
        discussion_entries_data = concat(discussion_entries)
        discussion_entries_path = discussions_path / ENTRIES_COMPRESSED_FILE
        discussion_entries_data.to_csv(discussion_entries_path, index=False)
        discussions_directory = str(discussions_path)
        make_archive(
            discussions_directory, TAR_COMPRESSION_TYPE, root_dir=discussions_directory
        )
        rmtree(discussions_path)
    if unpack:
        unpacked_path = unpack_discussions(
            compress_path, unpack_path, force, verbose=False
        )
        if verbose:
            print_unpacked_file(unpacked_path)
