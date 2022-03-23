from json import loads
from mimetypes import guess_extension
from pathlib import Path

from canvasapi.course import Course
from magic.magic import from_file
from requests import get
from typer import echo

from penn_canvas.api import collect
from penn_canvas.archive.archive import format_name, strip_tags
from penn_canvas.config import get_config_option
from penn_canvas.helpers import create_directory
from penn_canvas.style import color, print_item


def archive_modules(course: Course, course_path: Path, verbose: bool):
    echo(") Exporting modules...")
    modules_path = create_directory(course_path / "Modules")
    modules = collect(course.get_modules())
    module_total = len(modules)
    for module_index, module in enumerate(modules):
        module_name = format_name(module.name)
        if verbose:
            print_item(module_index, module_total, color(module_name, "blue"))
        module_path = create_directory(modules_path / module_name)
        items = collect(module.get_module_items())
        item_total = len(items)
        for item_index, item in enumerate(items):
            content = None
            extension = ".txt"
            body = ""
            try:
                url = item.url
            except Exception:
                try:
                    url = item.html_url
                except Exception:
                    url = ""
            if url:
                headers = {
                    "Authorization": (
                        f"Bearer {get_config_option('canvas_keys', 'canvas_prod_key')}"
                    )
                }
                response = get(url, headers=headers)
                try:
                    content = loads(response.content.decode("utf-8"))
                    if item.type == "File":
                        file_url = content["url"] if "url" in content else ""
                        if file_url:
                            try:
                                name, extension = item.filename.split(".")
                            except Exception:
                                try:
                                    name, extension = item.title.split(".")
                                except Exception:
                                    name = item.title
                                    extension = ""
                            name = format_name(name)
                            filename = (
                                f"{name}.{extension.lower()}"
                                if extension
                                else f"{name}"
                            )
                            file_path = module_path / filename
                            with open(file_path, "wb") as stream:
                                response = get(file_url, headers=headers, stream=True)
                                for chunk in response.iter_content(chunk_size=128):
                                    stream.write(chunk)
                            if not extension:
                                mime_type = from_file(str(file_path), mime=True)
                                file_path.rename(
                                    f"{file_path}{guess_extension(mime_type)}"
                                )
                        continue
                    body = content["body"] if "body" in content else ""
                except Exception:
                    body = (
                        f"[ExternalUrl]: {item.external_url}"
                        if item.type == "ExternalUrl"
                        else ""
                    )
            item_title = format_name(item.title)
            with open(module_path / f"{item_title}{extension}", "w") as item_file:
                if body:
                    file_content = strip_tags(body)
                elif url:
                    file_content = f"[{item.type}]"
                else:
                    file_content = "[missing url]"
                item_file.write(file_content)
            if verbose:
                print_item(
                    item_index,
                    item_total,
                    color(f"{item_title}: {file_content[:40]}", "yellow"),
                )
