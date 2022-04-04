from pathlib import Path
from typing import Optional

from canvasapi.course import Course
from canvasapi.page import Page
from pandas import read_csv
from pandas.core.frame import DataFrame
from typer import echo

from penn_canvas.helpers import create_directory, print_task_complete_message, write
from penn_canvas.style import color, print_item

from .helpers import (
    CSV_COMPRESSION_TYPE,
    format_display_text,
    format_name,
    print_unpacked_file,
    strip_tags,
)

PAGES_COMPRESSED_FILE = f"pages.{CSV_COMPRESSION_TYPE}"


def display_page(index: int, total: int, title: str, body: str):
    body_text = color(format_display_text(body), "yellow")
    message = f"{color(title)}: {body_text}"
    print_item(index, total, message)


def process_page(page: Page, verbose: bool, index=0, total=0):
    title = page.title.strip()
    body = strip_tags(page.show_latest_revision().body)
    if verbose:
        display_page(index, total, title, body)
    return [title, body]


def unpack_pages(
    compress_path: Path, unpack_path: Path, verbose: bool
) -> Optional[Path]:
    echo(") Unpacking pages...")
    compressed_file = compress_path / PAGES_COMPRESSED_FILE
    if not compressed_file.is_file():
        return None
    pages_data = read_csv(compressed_file)
    pages_path = create_directory(unpack_path / "Pages")
    total = len(pages_data)
    for index, page in enumerate(pages_data.itertuples(index=False)):
        title, body = page
        title = format_name(title)
        pages_file = pages_path / f"{title}.txt"
        write(pages_file, f'"{title}"\n\n{body}')
        if verbose:
            display_page(index, total, title, body)
            print_task_complete_message(pages_path)
    return pages_path


def archive_pages(
    course: Course, compress_path: Path, unpack_path: Path, unpack: bool, verbose: bool
):
    echo(") Exporting pages...")
    pages = list(course.get_pages())
    total = len(pages)
    pages = [
        process_page(page, verbose, index, total) for index, page in enumerate(pages)
    ]
    pages_data = DataFrame(pages, columns=["Title", "Body"])
    pages_path = compress_path / PAGES_COMPRESSED_FILE
    pages_data.to_csv(pages_path, index=False)
    if unpack:
        unpacked_path = unpack_pages(compress_path, unpack_path, verbose=False)
        if verbose:
            print_unpacked_file(unpacked_path)
