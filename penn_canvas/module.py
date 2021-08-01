from typer import echo

from .helpers import colorize, get_canvas


def module_main(test, course_id, module_id):
    canvas = get_canvas(test)
    course = canvas.get_course(course_id)
    modules = course.get_modules()
    module = next(filter(lambda module: module.id == module_id, modules), None)

    module_id = colorize(module_id, "magenta")
    course_id = colorize(course_id, "magenta")

    if module:
        module.relock()
        echo(f"- Module {module_id} re-locked for course {course_id}.")
    else:
        echo(f"- Module {module_id} not found for course {course_id}.")
