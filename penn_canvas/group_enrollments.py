from csv import writer
from datetime import datetime
from pathlib import Path

import pandas
import typer

from .helpers import (
    check_previous_output,
    colorize_path,
    get_canvas,
    get_command_paths,
    make_csv_paths,
    toggle_progress_bar,
)

CURRENT_YEAR = datetime.now().strftime("%Y")
INPUT, RESULTS = get_command_paths("group_enrollments", input_dir=True)
RESULT_PATH = RESULTS / "result.csv"
HEADERS = ["course id, group set, group, pennkey, status"]


def find_enrollments_file():
    typer.echo(") Finding group enrollments file...")

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
        CURRENT_FILE = ""
        CSV_FILES = Path(INPUT).glob("*.csv")

        for csv_file in CSV_FILES:
            if CURRENT_YEAR in csv_file.name:
                CURRENT_FILE = csv_file

        if not CURRENT_FILE:
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
            return CURRENT_FILE


def cleanup_data(data, start=0):
    typer.echo(") Preparing enrollments file...")

    data = pandas.read_csv(data)
    data.drop_duplicates(inplace=True)
    data = data.astype("string", copy=False)

    TOTAL = len(data.index)
    data = data.loc[start:TOTAL, :]

    return data, str(TOTAL)


def make_find_group_name(group_name):
    def find_group_name(group):
        return group.name == group_name

    return find_group_name


def create_group_enrollments(student, canvas, verbose, total=0):
    index, course_id, group_set_name, group_name, penn_key = student
    index += 1
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
            if verbose:
                typer.echo(f") Creating group set {group_set_name}...")
            group_set = course.create_group_category(group_set_name)

        filter_group = make_find_group_name(group_name)
        group = next(filter(filter_group, group_set.get_groups()), None)

        if not group:
            if verbose:
                typer.echo(f") Creating group {group_name}...")
            group = group_set.create_group(name=group_name)

        student = canvas.get_user(penn_key, "sis_login_id")
        group.create_membership(student)

        accepted = typer.secho("ACCEPTED", fg=typer.colors.GREEN)
    except Exception:
        accepted = typer.secho("FAILED", fg=typer.colors.RED)

    if verbose:
        typer.echo(
            f"- ({index}/{total}) {course_id}, {group_set_name}, {group_name},"
            f" {penn_key}: {accepted}'"
        )

    ROW = [course_id, group_set_name, group_name, penn_key, accepted]

    with open(RESULT_PATH, "a", newline="") as result:
        writer(result).writerow(ROW)


def group_enrollments_main(test, verbose):
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)
    data = find_enrollments_file()
    START = check_previous_output(RESULT_PATH)
    data, TOTAL = cleanup_data(data, START)
    make_csv_paths(RESULTS, RESULT_PATH, HEADERS)
    typer.echo(") Processing students...")
    toggle_progress_bar(
        data, create_group_enrollments, CANVAS, verbose, args=TOTAL, index=True
    )
    typer.echo(TOTAL)
