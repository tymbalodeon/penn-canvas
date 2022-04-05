from pathlib import Path
from re import search
from shutil import make_archive, rmtree
from time import sleep
from zipfile import ZipFile

from canvasapi.course import Course
from requests import get
from typer import echo

from penn_canvas.api import Instance, get_canvas
from penn_canvas.archive.helpers import TAR_COMPRESSION_TYPE
from penn_canvas.helpers import create_directory
from penn_canvas.style import color

CONTENT_EXPORT_TYPES = ["zip", "common_cartridge"]
CONTENT_DIRECTORY_NAME = "Content"


def format_export_type(export_type: str) -> str:
    return export_type.replace("_", " ").title()


def unpack_content(course_path: Path, verbose: bool):
    if verbose:
        echo(f") Unzipping {color(course_path, 'blue')}")
    unzip_parent = course_path.parent
    with ZipFile(course_path) as unzipper:
        unzipper.extractall(unzip_parent)
    return unzip_parent


def fetch_content(
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
        canvas = get_canvas(instance, verbose=False)
        workflow_state = canvas.get_progress(progress_id).workflow_state
        while workflow_state in {"running", "created", "queued"}:
            if verbose:
                export_type_display = color(f"{export_type} export", "cyan")
                echo(f"\t* {export_type_display} {workflow_state}...")
            sleep(5)
            workflow_state = canvas.get_progress(progress_id).workflow_state
        if workflow_state == "failed":
            echo("- color(EXPORT FAILED, 'red')")
        url = course.get_content_export(export).attachment["url"]
        response = get(url, stream=True)
        file_name = f"{export_type}_content.zip"
        content_path = create_directory(course_directory / CONTENT_DIRECTORY_NAME)
        formatted_export_type = format_export_type(export_type)
        export_path = create_directory(content_path / formatted_export_type)
        file_path = export_path / file_name
        with open(file_path, "wb") as stream:
            for chunk in response.iter_content(chunk_size=128):
                stream.write(chunk)
        if file_path.is_file():
            unzipped_path = unpack_content(file_path, verbose)
            path_name = str(unzipped_path)
            make_archive(path_name, TAR_COMPRESSION_TYPE, root_dir=path_name)
            rmtree(path_name)
