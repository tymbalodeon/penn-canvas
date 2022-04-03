from pathlib import Path

from canvasapi.course import Course
from canvasapi.group import Group, GroupCategory
from canvasapi.user import User
from pandas import DataFrame, concat
from requests import get
from typer import echo, progressbar

from penn_canvas.style import color, print_item

from .helpers import COMPRESSION_TYPE, format_display_text

GROUPS_COMPRESSED_FILE = f"groups.{COMPRESSION_TYPE}"
COLUMNS = ["Category", "Group", "Canvas User ID", "Name"]


def get_user_row(
    user: User, category_id: str, group_id: str, verbose: bool, index: int, total: int
) -> list[str]:
    if verbose:
        print_item(index, total, color(user, "cyan"), prefix="\t\t*")
    return [category_id, group_id, user.id, user.name]


def get_group_users(
    group: Group, category_id: str, verbose: bool, index: int, total: int
) -> DataFrame:
    if verbose:
        print_item(
            index, total, color(format_display_text(group.name), "yellow"), prefix="\t-"
        )
    users = list(group.get_users())
    user_total = len(users)
    rows = [
        get_user_row(user, category_id, group.id, verbose, user_index, user_total)
        for user_index, user in enumerate(users)
    ]
    return DataFrame(rows, columns=COLUMNS)


def archive_files(group: Group, compress_path: Path, verbose: bool, index, total):
    if verbose:
        print_item(
            index, total, color(format_display_text(group.name), "yellow"), prefix="\t-"
        )
    files = list(group.get_files())
    file_total = len(files)
    for file_index, group_file in enumerate(files):
        display_name = group_file.display_name
        try:
            name, extension = display_name.split(".")
        except Exception:
            name = group_file.filename
            extension = "txt"
        with open(
            compress_path / f"{name}.{extension}",
            "wb",
        ) as stream:
            response = get(group_file.url, stream=True)
            for chunk in response.iter_content(chunk_size=128):
                stream.write(chunk)
        if verbose:
            print_item(
                file_index, file_total, color(display_name, "blue"), prefix="\t\t*"
            )


def archive_category(
    category: GroupCategory, compress_path: Path, verbose: bool, index=0, total=0
) -> DataFrame:
    if verbose:
        print_item(index, total, color(category))
    echo(") Getting group users...")
    groups = list(category.get_groups())
    group_total = len(groups)
    group_data = [
        get_group_users(group, category.id, verbose, group_index, group_total)
        for group_index, group in enumerate(groups)
    ]
    echo(") Exporting group files...")
    for group_index, group in enumerate(groups):
        archive_files(group, compress_path, verbose, group_index, group_total)
    return concat(group_data) if group_data else DataFrame(columns=COLUMNS)


def archive_groups(course: Course, compress_path: Path, verbose: bool):
    echo(") Exporting groups...")
    category_objects: list[GroupCategory] = list(course.get_group_categories())
    total = len(category_objects)
    if verbose:
        categories = [
            archive_category(category, compress_path, verbose, index, total)
            for index, category in enumerate(category_objects)
        ]
    else:
        with progressbar(category_objects, length=total) as progress:
            categories = [
                archive_category(category, compress_path, verbose)
                for category in progress
            ]
    groups_path = compress_path / GROUPS_COMPRESSED_FILE
    groups_data = concat(categories) if categories else DataFrame(columns=COLUMNS)
    groups_data.to_csv(groups_path, index=False)
