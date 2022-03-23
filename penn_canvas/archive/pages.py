from pathlib import Path

from canvasapi.course import Course
from typer import echo

from penn_canvas.api import collect
from penn_canvas.archive.archive import format_name, strip_tags
from penn_canvas.helpers import create_directory
from penn_canvas.style import color, print_item


def archive_pages(course: Course, course_path: Path, verbose: bool):
    echo(") Exporting pages...")
    pages_path = create_directory(course_path / "Pages")
    pages = collect(course.get_pages())
    total = len(pages)
    for index, page in enumerate(pages):
        title = format_name(page.title)
        page_path = pages_path / f"{title}.txt"
        body = strip_tags(page.show_latest_revision().body)
        with open(page_path, "w") as page_file:
            page_file.write(body)
        if verbose:
            print_item(index, total, f"{color(title)}: {color(body[:40], 'yellow')}")
