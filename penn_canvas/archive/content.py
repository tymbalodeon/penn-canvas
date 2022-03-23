from pathlib import Path
from re import search
from time import sleep
from zipfile import ZipFile

from canvasapi.course import Course
from requests import get
from typer import echo

from penn_canvas.api import Instance, get_canvas
from penn_canvas.helpers import create_directory
from penn_canvas.style import color

CONTENT_EXPORT_TYPES = ["zip", "common_cartridge"]


def unzip_content(course_path: Path, verbose: bool):
    paths = [course_path / content_type for content_type in CONTENT_EXPORT_TYPES]
    content_path = create_directory(course_path / "Content")
    for path in paths:
        if verbose:
            echo(f") Unzipping {color(path, 'blue')}")
        with ZipFile(path) as unzipper:
            unzipper.extractall(content_path)


def archive_content(
    course: Course,
    course_directory: Path,
    instance: Instance,
    verbose: bool,
):
    echo(") Exporting content...")
    for export_type in CONTENT_EXPORT_TYPES:
        echo(f') Starting "{export_type}" export...')
        export = course.export_content(export_type=export_type, skip_notifications=True)
        regex_search = search(r"\d*$", export.progress_url)
        progress_id = regex_search.group() if regex_search else None
        canvas = get_canvas(instance)
        workflow_state = canvas.get_progress(progress_id).workflow_state
        while workflow_state in {"running", "created"}:
            if verbose:
                echo(f"- {workflow_state}...")
            sleep(5)
            workflow_state = canvas.get_progress(progress_id).wofklow_state
        if workflow_state == "failed":
            echo("- EXPORT FAILED")
        url = course.get_content_export(export).attachment["url"]
        response = get(url, stream=True)
        file_name = f"{export_type}_content.zip"
        content_path = create_directory(course_directory / "Content")
        export_path = create_directory(
            content_path / export_type.replace("_", " ").title()
        )
        file_path = export_path / file_name
        with open(file_path, "wb") as stream:
            for chunk in response.iter_content(chunk_size=128):
                stream.write(chunk)
