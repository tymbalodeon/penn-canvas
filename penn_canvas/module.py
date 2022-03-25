from typer import echo

from .api import get_canvas
from .style import color


def module_main(test, course_id):
    canvas = get_canvas(test)
    course = canvas.get_course(course_id)
    echo(f") Getting modules for course {color(course.name, 'yellow')}...")
    modules = [module for module in course.get_modules()]
    if not modules:
        echo(color("No modules found.", "yellow"))
    else:
        for module in modules:
            relocked_module = module.relock()
            echo(f"- {color('RE-LOCKED', 'green')} module: {color(relocked_module)}")
    echo("FINISHED")
