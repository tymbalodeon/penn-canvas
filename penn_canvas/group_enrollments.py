import os
from datetime import datetime
from pathlib import Path

import pandas
import typer

from .helpers import (
    check_if_complete,
    check_previous_output,
    colorize,
    colorize_path,
    get_canvas,
    get_command_paths,
    get_data_warehouse_cursor,
    make_csv_paths,
    toggle_progress_bar,
)

GRADUATION_YEAR = str(int(datetime.now().strftime("%Y")) + 4)
INPUT, RESULTS = get_command_paths("group_enrollments", input_dir=True)
RESULT_PATH = RESULTS / "result.csv"
HEADERS = [
    "index",
    "canvas course id",
    "group set name",
    "group name",
    "pennkey",
    "status",
]


def find_enrollments_file():
    typer.echo(") Finding group enrollments file...")

    if not INPUT.exists():
        Path.mkdir(INPUT, parents=True)
        error = typer.style(
            "- ERROR: Group enrollments input directory not found.",
            fg=typer.colors.YELLOW,
        )
        typer.echo(
            f"{error}\n- Creating one for you at: {colorize_path(str(INPUT))}\n\tPlease"
            " add a group enrollment file matching the graduation year of this year's"
            " incoming freshmen to this directory and then run this script again.\n-"
            " (If you need detailed instructions, run this command with the '--help'"
            " flag.)"
        )

        raise typer.Exit(1)
    else:
        CURRENT_FILE = ""
        EXTENSIONS = ["*.csv", "*.xlsx"]

        INPUT_FILES = list()

        for extension in EXTENSIONS:
            INPUT_FILES.extend(Path(INPUT).glob(extension))

        for input_file in INPUT_FILES:
            if GRADUATION_YEAR in input_file.name:
                CURRENT_FILE = input_file
                CURRENT_EXTENSION = input_file.suffix

        if not CURRENT_FILE:
            error = typer.style(
                "- ERROR: A group enrollments file matching the graduation year of this"
                " year's incoming freshmen was not found.",
                fg=typer.colors.YELLOW,
            )
            typer.echo(
                f"{error}\n- Please add a group enrollments file matching the"
                " graduation year of this year's incoming freshmen to the following"
                " directory and then run this script again:"
                f" {colorize_path(str(INPUT))}\n- (If you need detailed instructions,"
                " run this command with the '--help' flag.)"
            )

            raise typer.Exit(1)
        else:
            return CURRENT_FILE, CURRENT_EXTENSION


def cleanup_data(input_file, extension, force, start=0):
    typer.echo(") Preparing enrollments file...")

    if extension == ".csv":
        data = pandas.read_csv(input_file)
    else:
        data = pandas.read_excel(input_file, engine="openpyxl")

    data.columns = data.columns.str.lower()
    data["pennkey"] = data["pennkey"].str.lower()
    data = data.astype("string", copy=False)
    data[list(data)] = data[list(data)].apply(lambda column: column.str.strip())
    TOTAL = len(data.index)

    if not force:
        check_if_complete(start, TOTAL)

    data = data.loc[start:TOTAL, :]

    return data, str(TOTAL)


def make_find_group_name(group_name):
    def find_group_name(group):
        return group.name == group_name

    return find_group_name


def process_result():
    result = pandas.read_csv(RESULT_PATH)
    result = result[
        (result["status"] == "user not enrolled in course")
        | (result["status"] == "user not found in canvas")
        | (result["status"] == "invalid pennkey")
        | (result["status"] == "error")
    ]
    result = result.sort_values(by=["status"])
    failed_count = len(result.index)
    result.drop("index", axis=1, inplace=True)
    result.to_csv(RESULT_PATH, index=False)

    return str(failed_count)


def print_messages(failed_count, total):
    typer.secho("SUMMARY:", fg=typer.colors.CYAN)
    typer.echo(f"- Processed {colorize(total)} accounts.")
    accepted_count = typer.style(
        str(int(total) - int(failed_count)), fg=typer.colors.GREEN
    )
    typer.echo(f"- Successfully added {accepted_count} students to groups")

    if int(failed_count) > 0:
        typer.secho(
            f"- Failed to add {failed_count} students to a Group.",
            fg=typer.colors.RED,
        )
        result_path = typer.style(f"{RESULT_PATH}", fg=typer.colors.GREEN)
        typer.echo(f"- Details recorded to result file: {result_path}")

    typer.secho("FINISHED", fg=typer.colors.CYAN)


def group_enrollments_main(test, verbose, force):
    data, EXTENSION = find_enrollments_file()
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)

    if force:
        START = 0

        if RESULT_PATH.exists():
            os.remove(RESULT_PATH)
    else:
        START = check_previous_output(RESULT_PATH)

    data, TOTAL = cleanup_data(data, EXTENSION, force, START)
    make_csv_paths(RESULTS, RESULT_PATH, HEADERS)
    CURSOR = get_data_warehouse_cursor()

    def create_group_enrollments(student, canvas, verbose, args):
        cursor, total = args

        index, course_id, group_set_name, group_name, penn_key = student

        try:
            course = canvas.get_course(course_id)
            group_set_filter = make_find_group_name(group_set_name)
            group_set = next(
                filter(
                    group_set_filter,
                    course.get_group_categories(),
                ),
                None,
            )

            if not group_set:
                if verbose:
                    typer.echo(f") Creating group set {group_set_name}...")
                group_set = course.create_group_category(group_set_name)

            group_filter = make_find_group_name(group_name)
            group = next(filter(group_filter, group_set.get_groups()), None)

            if not group:
                if verbose:
                    typer.echo(f") Creating group {group_name}...")
                group = group_set.create_group(name=group_name)

            canvas_user = canvas.get_user(penn_key, "sis_login_id")
            group.create_membership(canvas_user)

            status = "added"
        except Exception:
            try:
                course = canvas.get_course(course_id)
                canvas_user = canvas.get_user(penn_key, "sis_login_id")

                try:
                    course.get_user(canvas_user)
                except Exception:
                    status = "user not enrolled in course"
            except Exception:
                try:
                    cursor.execute(
                        """
                        SELECT
                            pennkey
                        FROM dwadmin.person_all_v
                        WHERE pennkey= :penn_key
                        """,
                        penn_key=penn_key,
                    )

                    status = "invalid pennkey"

                    for student in cursor:
                        if len(student) > 0:
                            status = "user not found in canvas"
                            break
                except Exception:
                    status = "error"

        data.at[index, "status"] = status
        data.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)

        if verbose:
            status_display = status.upper()

            if status_display == "ADDED":
                status_display = typer.style(status_display, fg=typer.colors.GREEN)
            else:
                status_display = typer.style(status_display, fg=typer.colors.RED)

            penn_key = typer.style(penn_key, fg=typer.colors.MAGENTA)
            typer.echo(
                f"- ({index + 1}/{total}) {penn_key}, {group_set_name}, {group_name}:"
                f" {status_display}"
            )

    typer.echo(") Processing students...")
    toggle_progress_bar(
        data,
        create_group_enrollments,
        CANVAS,
        verbose,
        args=(CURSOR, TOTAL),
        index=True,
    )
    failed_count = process_result()
    print_messages(failed_count, TOTAL)
