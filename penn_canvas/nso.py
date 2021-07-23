from datetime import datetime
from pathlib import Path

import pandas
import typer
from cx_Oracle import connect, init_oracle_client

from .helpers import (
    colorize,
    colorize_path,
    get_canvas,
    get_command_paths,
    get_data_warehouse_config,
    get_start_index,
    make_csv_paths,
    make_skip_message,
    toggle_progress_bar,
)

lib_dir = Path.home() / "Downloads/instantclient_19_8"
config_dir = lib_dir / "network/admin"
init_oracle_client(
    lib_dir=str(lib_dir),
    config_dir=str(config_dir),
)

GRADUATION_YEAR = str(int(datetime.now().strftime("%Y")) + 4)
INPUT, RESULTS = get_command_paths("nso", input_dir=True)
RESULT_PATH = RESULTS / "result.csv"
HEADERS = [
    "index",
    "canvas course id",
    "group set name",
    "group name",
    "pennkey",
    "status",
]


def find_nso_file():
    typer.echo(") Finding NSO file...")

    if not INPUT.exists():
        Path.mkdir(INPUT, parents=True)
        error = typer.style(
            "- ERROR: NSO input directory not found.",
            fg=typer.colors.YELLOW,
        )
        typer.echo(
            f"{error}\n- Creating one for you at: {colorize_path(str(INPUT))}\n- Please"
            " add an NSO input file matching the graduation year of this year's"
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
                "- ERROR: A nso file matching the graduation year of this"
                " year's incoming freshmen was not found.",
                fg=typer.colors.YELLOW,
            )
            typer.echo(
                f"{error}\n- Please add a NSO input file matching the"
                " graduation year of this year's incoming freshmen to the following"
                " directory and then run this script again:"
                f" {colorize_path(str(INPUT))}\n- (If you need detailed instructions,"
                " run this command with the '--help' flag.)"
            )

            raise typer.Exit(1)
        else:
            return CURRENT_FILE, CURRENT_EXTENSION


def cleanup_data(input_file, extension, start=0):
    typer.echo(") Preparing NSO file...")

    if extension == ".csv":
        data = pandas.read_csv(input_file)
    else:
        data = pandas.read_excel(input_file, engine="openpyxl")

    data.columns = data.columns.str.lower()
    data["pennkey"] = data["pennkey"].str.lower()
    data = data.astype("string", copy=False)
    data[list(data)] = data[list(data)].apply(lambda column: column.str.strip())
    TOTAL = len(data.index)

    data = data.loc[start:TOTAL, :]

    return data, str(TOTAL)


def make_find_group_name(group_name):
    def find_group_name(group):
        return group.name == group_name

    return find_group_name


def process_result():
    result = pandas.read_csv(RESULT_PATH)
    NOT_ENROLLED = result[result["status"] == "user not enrolled in course"]
    NOT_IN_CANVAS = result[result["status"] == "user not found in canvas"]
    INVALID_PENNKEY = result[result["status"] == "invalid pennkey"]
    ERROR = result[result["status"] == "error"]
    NOT_ENROLLED_COUNT = str(len(NOT_ENROLLED.index))
    NOT_IN_CANVAS_COUNT = str(len(NOT_IN_CANVAS.index))
    INVALID_PENNKEY_COUNT = str(len(INVALID_PENNKEY.index))
    ERROR_COUNT = str(len(ERROR.index))
    result = pandas.concat([NOT_ENROLLED, NOT_IN_CANVAS, INVALID_PENNKEY, ERROR])
    result.drop("index", axis=1, inplace=True)
    result.to_csv(RESULT_PATH, index=False)

    return NOT_ENROLLED_COUNT, NOT_IN_CANVAS_COUNT, INVALID_PENNKEY_COUNT, ERROR_COUNT


def print_messages(not_enrolled, not_in_canvas, invalid_pennkey, error, total):
    typer.secho("SUMMARY:", fg=typer.colors.YELLOW)
    typer.echo(f"- Processed {colorize(total)} accounts.")
    TOTAL_ERRORS = (
        int(not_enrolled) + int(not_in_canvas) + int(invalid_pennkey) + int(error)
    )
    accepted_count = typer.style(
        str(int(total) - TOTAL_ERRORS),
        fg=typer.colors.GREEN,
    )
    typer.echo(f"- Successfully added {accepted_count} students to groups")

    errors = False

    if int(not_enrolled) > 0:
        if int(not_enrolled) > 1:
            student = "students"
        else:
            student = "student"

        message = typer.style(
            f"Found {not_enrolled} {student} not enrolled in the course.",
            fg=typer.colors.RED,
        )
        typer.echo(f"- {message}")
        errors = True

    if int(not_in_canvas) > 0:
        if int(not_in_canvas) > 1:
            student = "students"
            account = "Canvas accounts"
        else:
            student = "student"
            account = "a Canvas account"

        message = typer.style(
            f"Found {not_in_canvas} {student} without {account}.", fg=typer.colors.RED
        )
        typer.echo(f"- {message}")
        errors = True

    if int(invalid_pennkey) > 0:
        if int(invalid_pennkey) > 1:
            student = "students"
            pennkey = "pennkeys"
        else:
            student = "student"
            pennkey = "pennkey"

        message = typer.style(
            f"Found {invalid_pennkey} {student} with invalid {pennkey}.",
            fg=typer.colors.RED,
        )
        typer.echo(f"- {message}")
        errors = True

    if int(error) > 0:
        if int(error) > 1:
            student = "students"
        else:
            student = "student"

        message = typer.style(
            f"Encountered an unknown error for {error} {student}.",
            fg=typer.colors.RED,
        )
        typer.echo(f"- {message}")
        errors = True

    if errors:
        result_path = typer.style(f"{RESULT_PATH}", fg=typer.colors.GREEN)
        typer.echo(f"- Details recorded to result file: {result_path}")

    typer.secho("FINISHED", fg=typer.colors.YELLOW)


def nso_main(test, verbose, force):
    def create_enrollments(student, canvas, verbose, total=0):
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
        except Exception as error:
            try:
                course = canvas.get_course(course_id)
                canvas_user = canvas.get_user(penn_key, "sis_login_id")
                status = error

                try:
                    course.get_user(canvas_user)
                except Exception:
                    status = f"user not enrolled in course"

            except Exception as error:
                status = error

                try:
                    if verbose:
                        penn_key_display = typer.style(penn_key, fg=typer.colors.CYAN)
                        typer.echo(
                            ") Checking the Data Warehouse for pennkey:"
                            f" {penn_key_display}..."
                        )

                    cursor = connect(
                        DATA_WAREHOUSE_USER, DATA_WAREHOUSE_PASSWORD, DATA_WAREHOUSE_DSN
                    ).cursor()
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
                except Exception as error:
                    status = error

        data.at[index, "status"] = status
        data.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)

        if verbose:
            status_display = str(status).upper()

            if status_display == "ADDED":
                status_display = typer.style(status_display, fg=typer.colors.GREEN)
            else:
                status_display = typer.style(status_display, fg=typer.colors.RED)

            penn_key = typer.style(penn_key, fg=typer.colors.MAGENTA)
            typer.echo(
                f"- ({index + 1}/{total}) {penn_key}, {group_set_name}, {group_name}:"
                f" {status_display}"
            )

    data, EXTENSION = find_nso_file()
    (
        DATA_WAREHOUSE_USER,
        DATA_WAREHOUSE_PASSWORD,
        DATA_WAREHOUSE_DSN,
    ) = get_data_warehouse_config()
    START = get_start_index(force, RESULT_PATH)
    data, TOTAL = cleanup_data(data, EXTENSION, START)
    make_csv_paths(RESULTS, RESULT_PATH, HEADERS)
    make_skip_message(START, "student")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)

    typer.echo(") Processing students...")

    toggle_progress_bar(
        data,
        create_enrollments,
        CANVAS,
        verbose,
        args=TOTAL,
        index=True,
    )
    not_enrolled, not_in_canvas, invalid_pennkey, error = process_result()
    print_messages(not_enrolled, not_in_canvas, invalid_pennkey, error, TOTAL)
