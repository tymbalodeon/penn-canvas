from dataclasses import dataclass
from os import remove
from pathlib import Path
from re import search
from shutil import make_archive, rmtree, unpack_archive
from time import sleep
from typing import Optional
from zipfile import ZipFile

from canvasapi.course import Course
from loguru import logger
from typer import echo

from penn_canvas.api import Instance, get_canvas
from penn_canvas.archive.helpers import (
    TAR_COMPRESSION_TYPE,
    TAR_EXTENSION,
    print_unpacked_file,
)
from penn_canvas.helpers import create_directory, download_file
from penn_canvas.style import color

CONTENT_EXPORT_TYPES = ["common_cartridge", "zip"]
CONTENT_TAR_STEM = "content"
CONTENT_TAR_NAME = f"{CONTENT_TAR_STEM}.{TAR_EXTENSION}"
UNPACK_CONTENT_DIRECTORY = CONTENT_TAR_STEM.title()


@dataclass
class Export:
    course: Course
    export_type: str
    instance: Instance = Instance.PRODUCTION
    export_id: Optional[int] = None
    progress_id: Optional[str] = None
    workflow_state: Optional[str] = None

    def create_content_export(self):
        export = self.course.export_content(
            export_type=self.export_type, skip_notifications=True
        )
        self.export_id = export.id
        regex_search = search(r"\d*$", export.progress_url)
        self.progress_id = regex_search.group() if regex_search else None
        self.update_workflow_state()

    def update_workflow_state(self):
        canvas = get_canvas(self.instance, verbose=False)
        self.workflow_state = canvas.get_progress(self.progress_id).workflow_state


def format_export_type(export_type: str) -> str:
    return export_type.replace("_", " ").title()


def unzip_content(compress_path: Path):
    unzip_parent = compress_path.parent
    with ZipFile(compress_path) as unzipper:
        unzipper.extractall(unzip_parent)
    return unzip_parent


def is_running(exports: list[Export]) -> bool:
    states = [export.workflow_state for export in exports]
    running_states = {"created", "running", "queued"}
    running_progress = (state for state in states if state in running_states)
    return bool(next(running_progress, False))


def download_export_files(
    course: Course,
    exports: list[Export],
    compress_path: Path,
    unpack_path: Path,
    unpack: bool,
    verbose: bool,
):
    for export in exports:
        echo(f") Downloading {export.export_type} export files...")
        url = course.get_content_export(export.export_id).attachment["url"]
        file_name = f"{export.export_type}_content.zip"
        formatted_export_type = format_export_type(export.export_type)
        export_path = create_directory(compress_path / formatted_export_type)
        file_path = export_path / file_name
        download_file(file_path, url)
        if file_path.is_file():
            unzipped_path = unzip_content(file_path)
            remove(file_path)
            path_name = str(unzipped_path)
            make_archive(path_name, TAR_COMPRESSION_TYPE, root_dir=path_name)
            if unpack:
                unpack_path = unpack_path / export.export_type.replace("_", " ").title()
                unzipped_path.replace(unpack_path)
                if verbose:
                    print_unpacked_file(unzipped_path)
            else:
                try:
                    rmtree(unzipped_path)
                except Exception as error:
                    logger.error(f'Failed to remove {unzipped_path}: "{error}"')
                    rmtree(unzipped_path, ignore_errors=True)


def run_content_exports(
    course: Course,
    compress_path: Path,
    unpack_path: Path,
    unpack: bool,
    instance: Instance,
    verbose: bool,
):
    echo(") Running exports...")
    exports = [
        Export(course, export_type, instance) for export_type in CONTENT_EXPORT_TYPES
    ]
    for export in exports:
        export.create_content_export()
    attempts = 0
    running = is_running(exports)
    while running and attempts <= 180:
        for export in exports:
            export_display = color(export.export_type, "cyan")
            echo(f"\t* {export_display} {export.workflow_state}...")
        sleep(5)
        for export in exports:
            export.update_workflow_state()
        running = is_running(exports)
        attempts += 1
    failed_exports = [
        export for export in exports if export.workflow_state != "completed"
    ]
    exports = [export for export in exports if export.workflow_state == "completed"]
    if failed_exports:
        for export in failed_exports:
            message = color(
                f"ERROR: {export.export_type} failed. Please try again.", "red"
            )
            logger.error(message)
            echo(message)
    download_export_files(course, exports, compress_path, unpack_path, unpack, verbose)


def unpack_content(compress_path: Path, unpack_path: Path, force: bool, verbose: bool):
    echo(") Unpacking content...")
    archive_file = compress_path / CONTENT_TAR_NAME
    if not archive_file.is_file():
        return None
    content_path = unpack_path / UNPACK_CONTENT_DIRECTORY
    already_complete = not force and content_path.exists()
    if already_complete:
        echo("Content already unpacked.")
        return
    content_path = create_directory(unpack_path / UNPACK_CONTENT_DIRECTORY, clear=True)
    unpack_archive(archive_file, content_path)
    for tar_file in content_path.glob(f"*.{TAR_EXTENSION}"):
        unpack_archive(tar_file, content_path / tar_file.stem.replace(".tar", ""))
        remove(tar_file)
    if verbose:
        print_unpacked_file(content_path)


def fetch_content(
    course: Course,
    compress_path: Path,
    unpack_path: Path,
    unpack: bool,
    force: bool,
    instance: Instance,
    verbose: bool,
):
    echo(") Fetching content...")
    if unpack:
        unpack_content_path = unpack_path / UNPACK_CONTENT_DIRECTORY
    else:
        unpack_content_path = unpack_path
    archive_file = compress_path / CONTENT_TAR_NAME
    already_complete = not force and archive_file.is_file()
    if already_complete:
        echo("Content already fetched.")
        if unpack:
            unpack_content(compress_path, unpack_content_path, force, verbose)
        return
    content_path = create_directory(compress_path / CONTENT_TAR_STEM)
    run_content_exports(
        course, content_path, unpack_content_path, unpack, instance, verbose
    )
    content_directory = str(content_path)
    make_archive(content_directory, TAR_COMPRESSION_TYPE, root_dir=content_directory)
    rmtree(content_path)
