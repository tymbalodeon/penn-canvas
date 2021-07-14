import os
import sys
from datetime import datetime
from pathlib import Path

import typer

from .helpers import colorize_path, get_canvas, get_command_paths

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
            return CURRENT_REPORT


def find_group(name, groups):
    found = None
    for group in groups:
        if group.name == name:
            found = group
    return found


def create_group_enrollments(
    inputfile="groups.csv", outputfile="NSO_group_enrollments.csv", test=False
):
    canvas = get_canvas(test)
    my_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    file_path = os.path.join(my_path, "ACP/data", inputfile)
    dataFile = open(file_path, "r")
    dataFile.readline()
    outFile = open(os.path.join(my_path, "ACP/data", outputfile), "w+")
    outFile.write("canvas_course_id, group_set, group, pennkey, status\n")

    for line in dataFile:
        course_id, groupset_name, group_name, pennkey = line.replace("\n", "").split(
            ","
        )

        canvas_site = canvas.get_course(course_id)

        try:
            group_set = find_group(groupset_name, canvas_site.get_group_categories())

            if group_set is None:
                raise TypeError

        except Exception:
            print("creating group set: ", groupset_name)
            group_set = canvas_site.create_group_category(groupset_name)

        try:
            group = find_group(group_name, group_set.get_groups())
            if group is None:
                raise TypeError

        except Exception:
            print("creating group: ", group_name)
            group = group_set.create_group(name=group_name)

        try:
            user = canvas.get_user(pennkey, "sis_login_id")
            group.create_membership(user)

            message = (
                f"{course_id}, {groupset_name}, {group_name}, {pennkey}, 'accepted'\n"
            )
            print(message)
            outFile.write(message)
        except Exception:
            message = (
                f"{course_id}, {groupset_name}, {group_name}, {pennkey}, 'failed'\n"
            )
            typer.echo(message)
            outFile.write(message)


def group_enrollments_main(test, verbose):
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)
    report = find_enrollments_report()
    typer.echo("HELLO")
