from pathlib import Path

from canvasapi.course import Course
from canvasapi.discussion_topic import DiscussionEntry, DiscussionTopic
from pandas import DataFrame
from typer import echo, progressbar

from penn_canvas.api import Instance, get_user
from penn_canvas.helpers import create_directory, format_timestamp
from penn_canvas.style import color

from .helpers import format_name, strip_tags


def get_entry(
    entry: DiscussionEntry,
    instance: Instance,
    verbose: bool,
    discussion_index: int,
    total_discussions: int,
    entry_index: int,
    total_entries: int,
    discussion: DiscussionTopic,
    csv_style: bool,
) -> list | tuple:
    user = " ".join(entry.user["display_name"].split())
    user_id = entry.user["id"]
    canvas_user = get_user(user_id, instance=instance)
    email = canvas_user.email if csv_style else ""
    message = " ".join(strip_tags(entry.message.replace("\n", " ")).strip().split())
    timestamp = "" if csv_style else format_timestamp(entry.created_at)
    if verbose:
        user_display = color(user, "cyan")
        timestamp_display = color(timestamp, "yellow") if csv_style else ""
        email_display = color(email, "yellow") if not csv_style else ""
        discussion_display = color(discussion.title.strip(), "magenta")
        if entry_index == 0:
            echo(f"==== DISCUSSION {discussion_index + 1} ====")
        echo(
            f"- [{discussion_index + 1}/{total_discussions}]"
            f" ({entry_index + 1}/{total_entries}) {discussion_display}"
            f" {user_display}"
            f" {timestamp_display if csv_style else email_display}"
            f" {message[:40]}..."
        )
    return [user, email, message] if csv_style else (user, timestamp, message)


def archive_discussion(
    discussion: DiscussionTopic,
    course_directory: Path,
    use_timestamp: bool,
    instance,
    verbose: bool,
    index=0,
    total=0,
    csv_style=False,
):
    discussion_name = format_name(discussion.title)
    DISCUSSION_DIRECTORY = create_directory(course_directory / "Discussions")
    discussion_path = create_directory(DISCUSSION_DIRECTORY / discussion_name)
    description_path = discussion_path / f"{discussion_name}_DESCRIPTION.txt"
    entries = list(discussion.get_topic_entries())
    if verbose and not entries:
        echo(f"==== DISCUSSION {index + 1} ====")
        echo("- NO ENTRIES")
    entries = [
        get_entry(
            entry,
            instance,
            verbose,
            index,
            total,
            entry_index,
            len(entries),
            discussion,
            csv_style,
        )
        for entry_index, entry in enumerate(entries)
    ]
    try:
        description = " ".join(
            strip_tags(discussion.message.replace("\n", " ")).strip().split()
        )
    except Exception:
        description = ""
    columns = ["User", "Email", "Timestamp", "Post"]
    if not use_timestamp:
        columns.remove("Timestamp")
    if csv_style:
        entries_data_frame = DataFrame(entries, columns=columns)
        posts_path = discussion_path / f"{discussion_name}_POSTS.csv"
        entries_data_frame.to_csv(posts_path, index=False)
    else:
        posts_path = discussion_path / f"{discussion_name}_POSTS.txt"
        with open(posts_path, "w") as posts_file:
            for user, timestamp, message in entries:
                posts_file.write(f"\n{user}\n{timestamp}\n\n{message}\n")
    with open(description_path, "w") as description_file:
        description_file.write(description)


def fetch_discussions(
    course: Course,
    course_path: Path,
    use_timestamp: bool,
    instance: Instance,
    verbose: bool,
):
    echo(") Exporting discussions...")
    discussions = list(course.get_discussion_topics())
    total = len(discussions)
    if verbose:
        for index, discussion in enumerate(discussions):
            archive_discussion(
                discussion,
                course_path,
                use_timestamp,
                instance,
                verbose,
                index=index,
                total=total,
            )
    else:
        with progressbar(discussions, length=total) as progress:
            for discussion in progress:
                archive_discussion(
                    discussion, course_path, use_timestamp, instance, verbose
                )
