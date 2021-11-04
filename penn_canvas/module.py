from typer import echo

from .helpers import colorize, get_canvas


def module_main(test, course_id):
    canvas = get_canvas(test)
    course = canvas.get_course(course_id)

    echo(f") Getting modules for course {colorize(course.name, 'yellow')}...")

    modules = [module for module in course.get_modules()]

    if not modules:
        colorize("- No modules found.", "yellow", True)
    else:
        for module in modules:
            relocked_module = module.relock()
            echo(
                f"- {colorize('RE-LOCKED', 'green')} module:"
                f" {colorize(relocked_module)}"
            )

    echo("FINISHED")
