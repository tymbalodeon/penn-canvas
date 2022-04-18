from json import loads
from pathlib import Path
from shutil import make_archive, rmtree, unpack_archive
from typing import Optional

from canvasapi.course import Course
from canvasapi.module import Module, ModuleItem
from loguru import logger
from requests import get
from typer import echo, progressbar

from penn_canvas.api import Instance, get_canvas_key
from penn_canvas.helpers import create_directory, write_file
from penn_canvas.style import color, print_item

from .helpers import (
    TAR_COMPRESSION_TYPE,
    TAR_EXTENSION,
    format_display_text,
    format_name,
    print_unpacked_file,
    strip_tags,
)

MODULES_TAR_STEM = "modules"
MODULES_TAR_NAME = f"{MODULES_TAR_STEM}.{TAR_EXTENSION}"
UNPACK_MODULES_DIRECTORY = MODULES_TAR_STEM.title()


def get_item_url(item: ModuleItem) -> str:
    try:
        return item.url
    except Exception:
        try:
            return item.html_url
        except Exception:
            return ""


def get_item_text(content: dict, item_type: str) -> str:
    body = "body"
    description = "description"
    message = "message"
    if body in content and content[body]:
        return content[body]
    elif description in content and content[description]:
        return content[description]
    elif message in content and content[message]:
        return content[message]
    else:
        return f"[{item_type} {content['id']}]"


def get_item_body(url: str, item_type: str, instance: Instance) -> str:
    if not url:
        return ""
    key = get_canvas_key(instance)
    headers = {"Authorization": f"Bearer {key}"}
    response = get(url, headers=headers)
    try:
        content = loads(response.content.decode("utf-8"))
    except Exception as error:
        logger.error(error)
        try:
            content = loads(response.content.decode("latin1"))
        except Exception as error:
            logger.error(error)
            content = {"id": ""}
    return get_item_text(content, item_type)


def get_module_item(
    item: ModuleItem,
    module_path: Path,
    instance: Instance,
    verbose: bool,
    index: int,
    total: int,
):
    url = get_item_url(item)
    body = get_item_body(url, item.type, instance)
    content = strip_tags(body) if body else "[missing url]"
    item_title = format_name(item.title)
    write_file(module_path / f"{item_title}.txt", content)
    if verbose:
        title_display = color(format_display_text(item_title), "yellow")
        content_display = color(format_display_text(content), "cyan")
        message = f"{title_display}: {content_display}"
        print_item(index, total, message, prefix="\t*")


def get_module(
    module: Module,
    modules_path: Path,
    instance: Instance,
    verbose: bool,
    index=0,
    total=0,
):
    module_name = format_name(module.name)
    if verbose:
        print_item(index, total, color(module_name))
    module_path = create_directory(modules_path / module_name)
    items = list(module.get_module_items())
    item_total = len(items)
    for item_index, item in enumerate(items):
        get_module_item(item, module_path, instance, verbose, item_index, item_total)


def unpack_modules(
    compress_path: Path, unpack_path: Path, verbose: bool
) -> Optional[Path]:
    echo(") Unpacking modules...")
    archive_file = compress_path / MODULES_TAR_NAME
    if not archive_file.is_file():
        return None
    unpack_modules_path = create_directory(
        unpack_path / UNPACK_MODULES_DIRECTORY, clear=True
    )
    unpack_archive(archive_file, unpack_modules_path)
    if verbose:
        print_unpacked_file(unpack_modules_path)
    return unpack_modules_path


def fetch_modules(
    course: Course,
    compress_path: Path,
    unpack_path: Path,
    unpack: bool,
    instance: Instance,
    verbose: bool,
):
    echo(") Exporting modules...")
    modules_path = create_directory(compress_path / "modules")
    modules = list(course.get_modules())
    total = len(modules)
    if verbose:
        for index, module in enumerate(modules):
            get_module(module, modules_path, instance, verbose, index, total)
    else:
        with progressbar(modules, length=total) as progress:
            for module in progress:
                get_module(module, modules_path, instance, verbose)
    modules_directory = str(modules_path)
    make_archive(modules_directory, TAR_COMPRESSION_TYPE, root_dir=modules_directory)
    if unpack:
        unpack_groups_path = create_directory(
            unpack_path / UNPACK_MODULES_DIRECTORY, clear=True
        )
        modules_path.replace(unpack_groups_path)
        unpacked_path = unpack_modules(compress_path, unpack_path, verbose=False)
        if verbose:
            print_unpacked_file(unpacked_path)
    else:
        rmtree(modules_path)
