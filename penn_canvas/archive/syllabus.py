from pathlib import Path
from typing import Optional

from canvasapi.course import Course
from pandas import DataFrame, read_csv
from typer import echo

from penn_canvas.helpers import print_task_complete_message, write_file
from penn_canvas.style import color

from .helpers import (
    CSV_COMPRESSION_TYPE,
    format_display_text,
    print_unpacked_file,
    strip_tags,
)

SYLLABUS_COMPRESSION_FILE = f"syllabus.{CSV_COMPRESSION_TYPE}"


def print_syllabus(syllabus):
    echo(f"\t{color(format_display_text(syllabus, limit=60), 'cyan')}")


def unpack_syllabus(
    compress_path: Path, unpack_path: Path, verbose: bool
) -> Optional[Path]:
    echo(") Unpacking syllabus...")
    compressed_file = compress_path / SYLLABUS_COMPRESSION_FILE
    if not compressed_file.is_file():
        return None
    data_frame = read_csv(compressed_file)
    syllabus = next(iter(data_frame["syllabus"].tolist()), "")
    syllabus_file = unpack_path / "Syllabus.txt"
    write_file(syllabus_file, syllabus)
    if verbose:
        print_syllabus(syllabus)
        print_task_complete_message(syllabus_file)
    return syllabus_file


def fetch_syllabus(
    course: Course,
    compress_path: Path,
    unpack_path: Path,
    unpack: bool,
    verbose: bool,
):
    echo(") Exporting syllabus...")
    syllabus = course.syllabus_body
    if syllabus:
        syllabus = strip_tags(syllabus)
        syllabus_data = DataFrame([syllabus], columns=["syllabus"])
        syllabus_file = compress_path / SYLLABUS_COMPRESSION_FILE
        syllabus_data.to_csv(syllabus_file, index=False)
        if verbose:
            print_syllabus(syllabus)
        if unpack:
            unpacked_file = unpack_syllabus(compress_path, unpack_path, verbose=False)
            if verbose:
                print_unpacked_file(unpacked_file)
