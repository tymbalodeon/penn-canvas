from os import remove
from pathlib import Path
from shutil import make_archive, rmtree, unpack_archive
from typing import Optional

from canvasapi.course import Course
from canvasapi.group import Group, GroupCategory
from canvasapi.user import User
from pandas import DataFrame, Series, concat, read_csv
from typer import echo, progressbar

from penn_canvas.helpers import (
    create_directory,
    download_file,
    print_task_complete_message,
)
from penn_canvas.style import color, print_item

from .helpers import (
    CSV_COMPRESSION_TYPE,
    TAR_COMPRESSION_TYPE,
    TAR_EXTENSION,
    extract_file,
    format_display_text,
    format_name,
    print_unpacked_file,
)

GROUPS = "groups"
GROUPS_COMPRESSED_FILE = f"groups.{CSV_COMPRESSION_TYPE}"
CATEGORY_ID = "Category ID"
CATEGORY_NAME = "Category Name"
GROUP_ID = "Group ID"
GROUP_NAME = "Group Name"
UNPACK_GROUP_DIRECTORY = GROUPS.title()
GROUPS_TAR_NAME = f"group_files.{TAR_EXTENSION}"
ALL_GROUPS_TAR_NAME = f"{GROUPS}.{TAR_EXTENSION}"
COLUMNS = [
    CATEGORY_ID,
    CATEGORY_NAME,
    GROUP_ID,
    GROUP_NAME,
    "Canvas User ID",
    "Name",
]


def get_group_user(
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
        get_group_user(user, category, group, verbose, user_index, user_total)
        for user_index, user in enumerate(users)
    ]
    return DataFrame(rows, columns=COLUMNS)


def download_files(
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
        download_file(group_files_path / f"{name}.{extension}", group_file.url)
        if verbose:
            print_item(
                file_index, file_total, color(display_name, "blue"), prefix="\t\t*"
            )


def get_category(
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
    echo(") Fetching group files...")
    group_files_path = create_directory(
        category_files_path / format_name(category.name)
    )
    for group_index, group in enumerate(groups):
        files_path = create_directory(group_files_path / format_name(group.name))
        download_files(group, files_path, verbose, group_index, group_total)
    return concat(group_data) if group_data else DataFrame(columns=COLUMNS)


def get_unpack_groups(series: Series) -> list[Series]:
    group_ids = series[GROUP_ID].unique()
    return [series[series[GROUP_ID] == group_id] for group_id in group_ids]


def unpack_groups(
    compress_path: Path, unpack_path: Path, force: bool, verbose: bool
) -> Optional[Path]:
    echo(") Unpacking groups...")
    groups_path = unpack_path / UNPACK_GROUP_DIRECTORY
    already_complete = not force and groups_path.exists()
    if already_complete:
        echo("Groups already unpacked.")
        return None
    archive_tar_path = compress_path / ALL_GROUPS_TAR_NAME
    if not archive_tar_path.is_file():
        return None
    extract_file(f"./{GROUPS_COMPRESSED_FILE}", archive_tar_path, compress_path)
    extract_file(f"./{GROUPS_TAR_NAME}", archive_tar_path, compress_path)
    extracted_csv = compress_path / GROUPS_COMPRESSED_FILE
    extracted_tar = compress_path / GROUPS_TAR_NAME
    unpack_archive(extracted_tar, create_directory(unpack_path / "Groups"))
    categories_data = read_csv(extracted_csv)
    category_ids = categories_data[CATEGORY_ID].unique()
    category_series = [
        categories_data[categories_data[CATEGORY_ID] == category_id]
        for category_id in category_ids
    ]
    groups = [get_unpack_groups(category) for category in category_series]
    groups_path = create_directory(groups_path)
    category_total = len(category_series)
    for category_index, categories in enumerate(groups):
        category = next(iter(categories))
        category_name = next(iter(category[CATEGORY_NAME].tolist()), "")
        if verbose:
            print_item(category_index, category_total, color(category_name))
        group_total = len(categories)
        for group_index, group in enumerate(categories):
            category_path = create_directory(groups_path / format_name(category_name))
            group_name = next(iter(group[GROUP_NAME].tolist()), "")
            group_path = category_path / f"{format_name(group_name)}.csv"
            group.to_csv(group_path, index=False)
            if verbose:
                print_item(
                    group_index, group_total, color(group_name, "cyan"), prefix="\t*"
                )
    if verbose:
        print_task_complete_message(groups_path)
    for extracted_file in [extracted_csv, extracted_tar]:
        remove(extracted_file)
    return groups_path


def fetch_groups(
    course: Course,
    compress_path: Path,
    unpack_path: Path,
    unpack: bool,
    force: bool,
    verbose: bool,
):
    echo(") Fetching groups...")
    archive_tar_path = compress_path / ALL_GROUPS_TAR_NAME
    already_complete = not force and archive_tar_path.is_file()
    if already_complete:
        echo("Groups already fetched.")
        if unpack:
            unpack_groups(compress_path, unpack_path, force, verbose=False)
        return
    category_objects = list(course.get_group_categories())
    total = len(category_objects)
    all_groups_path = create_directory(compress_path / "groups")
    category_files_path = create_directory(all_groups_path / "group_files")
    if verbose:
        categories = [
            get_category(category, category_files_path, verbose, index, total)
            for index, category in enumerate(category_objects)
        ]
    else:
        with progressbar(category_objects, length=total) as progress:
            categories = [
                get_category(category, category_files_path, verbose)
                for category in progress
            ]
    groups_path = all_groups_path / GROUPS_COMPRESSED_FILE
    groups_data = concat(categories) if categories else DataFrame(columns=COLUMNS)
    groups_data.to_csv(groups_path, index=False)
    group_files_archive_path = str(category_files_path)
    make_archive(
        group_files_archive_path,
        TAR_COMPRESSION_TYPE,
        root_dir=group_files_archive_path,
    )
    if unpack:
        unpack_groups_path = create_directory(
            unpack_path / UNPACK_GROUP_DIRECTORY, clear=True
        )
        category_files_path.replace(unpack_groups_path)
        unpacked_path = unpack_groups(compress_path, unpack_path, force, verbose=False)
        if verbose:
            print_unpacked_file(unpacked_path)
    else:
        rmtree(category_files_path)
    make_archive_path = str(all_groups_path)
    make_archive(make_archive_path, TAR_COMPRESSION_TYPE, root_dir=make_archive_path)
    rmtree(all_groups_path)
