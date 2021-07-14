from datetime import datetime
from pathlib import Path

import pandas
import typer

from .helpers import colorize_path, get_canvas, get_command_paths, make_csv_paths

CURRENT_YEAR = datetime.now().strftime("%Y")
INPUT, RESULTS = get_command_paths("group_enrollments", input_dir=True)
RESULT_PATH = RESULTS / "result.csv"
HEADERS = ["course id, group set, group, pennkey, status"]


def find_enrollments_report():
    typer.echo(") Finding group enrollments report...")

    if not INPUT.exists():
        Path.mkdir(INPUT, parents=True)
        error = typer.style(
            "- ERROR: Group enrollments input directory not found.",
            fg=typer.colors.YELLOW,
        )
        typer.echo(
            f"{error} \n- Creating one for you at: {colorize_path(INPUT)}\n\tPlease"
            " add a group enrollment file matching the current year to this"
            " directory and then run this script again.\n- (If you need detailed"
            " instructions, run this command with the '--help' flag.)"
        )
        raise typer.Exit(1)
    else:
        CURRENT_REPORT = ""
        CSV_FILES = Path(INPUT).glob("*.csv")

        for report in CSV_FILES:
            if CURRENT_YEAR in report.name:
                CURRENT_REPORT = report

        if not CURRENT_REPORT:
            typer.secho(
                "- ERROR: A group enrollments file matching the current year was not"
                " found.",
                fg=typer.colors.YELLOW,
            )
            typer.echo(
                "- Please add a group enrollments file matching the current year to the"
                " following directory and then run this script again:"
                f" {colorize_path(str(INPUT))}\n- (If you need detailed instructions,"
                " run this command with the"
                " '--help' flag.)"
            )
            raise typer.Exit(1)
        else:
            DATA = pandas.read_csv(CURRENT_REPORT)
            TOTAL = len(DATA.index)
            return DATA, TOTAL


def make_find_group_name(group_name):
    def find_group_name(group):
        return group.name == group_name

    return find_group_name


def create_group_enrollments(data, canvas, verbose, total=0):
    for row in data:
        course_id, group_set_name, group_name, penn_key = row
        course = canvas.get_course(course_id)

        try:
            filter_group_set = make_find_group_name(group_set_name)
            group_set = next(
                filter(
                    filter_group_set,
                    course.get_group_categories(),
                ),
                None,
            )

            if not group_set:
                typer.echo(f") Creating group set {group_set_name}...")
                group_set = course.create_group_category(group_set_name)

            filter_group = make_find_group_name(group_name)
            group = next(filter(filter_group, group_set.get_groups()), None)

            if not group:
                typer.echo(f") Creating group {group_name}...")
                group = group_set.create_group(name=group_name)

            user = canvas.get_user(penn_key, "sis_login_id")
            group.create_membership(user)

            message = (
                f"{course_id}, {group_set_name}, {group_name}, {penn_key}, 'accepted'\n"
            )
            typer.echo(message)
            # outFile.write(message)
        except Exception:
            message = (
                f"{course_id}, {group_set_name}, {group_name}, {penn_key}, 'failed'\n"
            )
            typer.echo(message)
            # outFile.write(message)


def group_enrollments_main(test, verbose):
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)
    DATA, TOTAL = find_enrollments_report()
    make_csv_paths(RESULTS, RESULT_PATH, HEADERS)
    create_group_enrollments(DATA, CANVAS, verbose, TOTAL)
    typer.echo(TOTAL)
