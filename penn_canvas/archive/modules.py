from json import loads
from mimetypes import guess_extension
from pathlib import Path
from typing import Optional

from canvasapi.course import Course
from canvasapi.module import Module, ModuleItem
from magic.magic import from_file
from requests import get
from typer import echo, progressbar

from penn_canvas.api import Instance, get_canvas_key
from penn_canvas.helpers import create_directory, download_file, write_file
from penn_canvas.style import color, print_item

from .helpers import format_display_text, format_name, strip_tags


def get_item_url(item: ModuleItem) -> str:
    try:
        return item.url
    except Exception:
        try:
            return item.html_url
        except Exception:
            return ""


def download_item_file(
    item: ModuleItem, url: str, headers: dict[str, str], module_path: Path
):
    try:
        name, extension = item.filename.split(".")
    except Exception:
        try:
            name, extension = item.title.split(".")
        except Exception:
            name = item.title
            extension = ""
    name = format_name(name)
    filename = f"{name}.{extension.lower()}" if extension else name
    file_path = module_path / filename
    download_file(module_path / filename, url, headers)
    if not extension:
        mime_type = from_file(str(file_path), mime=True)
        file_path.rename(f"{file_path}{guess_extension(mime_type)}")


def get_item_body(
    item: ModuleItem, url: str, module_path: Path, instance: Instance
) -> Optional[str]:
    key = get_canvas_key(instance)
    headers = {"Authorization": f"Bearer {key}"}
    response = get(url, headers=headers)
    try:
        content = loads(response.content.decode("utf-8"))
        if item.type != "File":
            return content["body"] if "body" in content else ""
        file_url = content["url"] if "url" in content else None
        if file_url:
            download_item_file(item, url, headers, module_path)
        return None
    except Exception:
        return (
            f"[ExternalUrl]: {item.external_url}" if item.type == "ExternalUrl" else ""
        )


def archive_item(
    item: ModuleItem,
    module_path: Path,
    instance: Instance,
    verbose: bool,
    index: int,
    total: int,
):
    url = get_item_url(item)
    if not url:
        return
    body = get_item_body(item, url, module_path, instance)
    item_title = format_name(item.title)
    if body:
        content = strip_tags(body)
    elif url:
        content = f"[{item.type}]"
    else:
        content = "[missing url]"
    write_file(module_path / f"{item_title}.txt", content)
    if verbose:
        title_display = color(format_display_text(item_title), "yellow")
        content_display = color(format_display_text(content), "cyan")
        message = f"{title_display}: {content_display}"
        print_item(index, total, message, prefix="\t*")


def archive_module(
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
        archive_item(item, module_path, instance, verbose, item_index, item_total)


def fetch_modules(
    course: Course, compress_path: Path, instance: Instance, verbose: bool
):
    echo(") Exporting modules...")
    modules_path = create_directory(compress_path / "Modules")
    modules = list(course.get_modules())
    total = len(modules)
    if verbose:
        for index, module in enumerate(modules):
            archive_module(module, modules_path, instance, verbose, index, total)
    else:
        with progressbar(modules, length=total) as progress:
            for module in progress:
                archive_module(module, modules_path, instance, verbose)
