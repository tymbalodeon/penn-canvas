from pathlib import Path
from shutil import make_archive, rmtree
from typing import Optional

from canvasapi.course import Course
from canvasapi.group import Group, GroupCategory
from canvasapi.user import User
from pandas import DataFrame, Series, concat, read_csv
from requests import get
from typer import echo, progressbar

from penn_canvas.helpers import create_directory, print_task_complete_message
from penn_canvas.style import color, print_item

from .helpers import (
    CSV_COMPRESSION_TYPE,
    TAR_COMPRESSION_TYPE,
    format_display_text,
    format_name,
    print_unpacked_file,
)

GROUPS_COMPRESSED_FILE = f"groups.{CSV_COMPRESSION_TYPE}"
CATEGORY_ID = "Category ID"
CATEGORY_NAME = "Category Name"
GROUP_ID = "Group ID"
GROUP_NAME = "Group Name"
UNPACK_GROUP_DIRECTORY = "Groups"
COLUMNS = [
    CATEGORY_ID,
    CATEGORY_NAME,
    GROUP_ID,
    GROUP_NAME,
    "Canvas User ID",
    "Name",
]


def get_user_row(
    user: User,
    category: GroupCategory,
    group: Group,
    verbose: bool,
    index: int,
    total: int,
) -> list[str]:
    if verbose:
        print_item(index, total, color(user, "cyan"), prefix="\t\t*")
    return [category.id, category.name, group.id, group.name, user.id, user.name]


def get_group_users(
    group: Group, category: GroupCategory, verbose: bool, index: int, total: int
) -> DataFrame:
    if verbose:
        print_item(
            index, total, color(format_display_text(group.name), "yellow"), prefix="\t-"
        )
    users = list(group.get_users())
    user_total = len(users)
    rows = [
        get_user_row(user, category, group, verbose, user_index, user_total)
        for user_index, user in enumerate(users)
    ]
    return DataFrame(rows, columns=COLUMNS)


def archive_files(
    group: Group, group_files_path: Path, verbose: bool, index: int, total: int
):
    if verbose:
        print_item(
            index, total, color(format_display_text(group.name), "yellow"), prefix="\t-"
        )
    files = list(group.get_files())
    file_total = len(files)
    if not file_total:
        rmtree(group_files_path)
        return
    for file_index, group_file in enumerate(files):
        display_name = group_file.display_name
        try:
            name, extension = display_name.split(".")
        except Exception:
            name = group_file.filename
            extension = "txt"
        with open(
            group_files_path / f"{name}.{extension}",
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
    category: GroupCategory, category_files_path: Path, verbose: bool, index=0, total=0
) -> DataFrame:
    if verbose:
        print_item(index, total, color(category))
    echo(") Getting group users...")
    groups = list(category.get_groups())
    group_total = len(groups)
    group_data = [
        get_group_users(group, category, verbose, group_index, group_total)
        for group_index, group in enumerate(groups)
    ]
    echo(") Exporting group files...")
    group_files_path = create_directory(
        category_files_path / format_name(category.name)
    )
    for group_index, group in enumerate(groups):
        files_path = create_directory(group_files_path / format_name(group.name))
        archive_files(group, files_path, verbose, group_index, group_total)
    return concat(group_data) if group_data else DataFrame(columns=COLUMNS)


def get_groups_to_unpack(series: Series) -> list[Series]:
    group_ids = series[GROUP_ID].unique()
    return [series[series[GROUP_ID] == group_id] for group_id in group_ids]


def unpack_groups(
    compress_path: Path, unpack_path: Path, verbose: bool
) -> Optional[Path]:
    echo(") Unpacking groups...")
    compressed_file = compress_path / GROUPS_COMPRESSED_FILE
    if not compressed_file.is_file():
        return None
    categories_data = read_csv(compressed_file)
    category_ids = categories_data[CATEGORY_ID].unique()
    categories = [
        categories_data[categories_data[CATEGORY_ID] == category_ids]
        for category_ids in category_ids
    ]
    groups = [get_groups_to_unpack(category) for category in categories]
    groups_path = create_directory(unpack_path / UNPACK_GROUP_DIRECTORY)
    category_total = len(categories_data)
    for category_index, categories in enumerate(groups):
        group_total = len(categories)
        for group_index, group in enumerate(categories):
            category_name = next(iter(group[CATEGORY_NAME].tolist()), "")
            category_path = create_directory(groups_path / format_name(category_name))
            if verbose:
                print_item(category_index, category_total, color(category_name))
            group_name = next(iter(group[GROUP_NAME].tolist()), "")
            group_path = category_path / f"{format_name(group_name)}.csv"
            group.to_csv(group_path, index=False)
            if verbose:
                print_item(group_index, group_total, color(group_name))
    if verbose:
        print_task_complete_message(groups_path)
    return groups_path


def fetch_groups(
    course: Course, compress_path: Path, unpack_path: Path, unpack: bool, verbose: bool
):
    echo(") Exporting groups...")
    category_objects = list(course.get_group_categories())
    total = len(category_objects)
    category_files_path = create_directory(compress_path / "group_files")
    if verbose:
        categories = [
            archive_category(category, category_files_path, verbose, index, total)
            for index, category in enumerate(category_objects)
        ]
    else:
        with progressbar(category_objects, length=total) as progress:
            categories = [
                archive_category(category, category_files_path, verbose)
                for category in progress
            ]
    groups_path = compress_path / GROUPS_COMPRESSED_FILE
    groups_data = concat(categories) if categories else DataFrame(columns=COLUMNS)
    groups_data.to_csv(groups_path, index=False)
    group_files = str(category_files_path)
    make_archive(group_files, TAR_COMPRESSION_TYPE, root_dir=group_files)
    if unpack:
        unpack_groups_path = create_directory(
            unpack_path / UNPACK_GROUP_DIRECTORY, clear=True
        )
        category_files_path.replace(unpack_groups_path)
        unpacked_path = unpack_groups(compress_path, unpack_path, verbose=False)
        if verbose:
            print_unpacked_file(unpacked_path)
    else:
        rmtree(category_files_path)
