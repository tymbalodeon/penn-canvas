import typer
from canvasapi import Canvas

from .helpers import get_canvas


def module_main(test, course_id, module_id):
    canvas = get_canvas(test)
    course = canvas.get_course(course_id)
    modules = course.get_modules()
    module = next(filter(lambda module: module.id == module_id, modules), None)

    module_id = typer.style(module_id, fg=typer.colors.MAGENTA)
    course_id = typer.style(course_id, fg=typer.colors.MAGENTA)

    if module:
        module.relock()
        typer.echo(f"- Module {module_id} re-locked for course {course_id}.")
    else:
        typer.echo(f"- Module {module_id} not found for course {course_id}.")
