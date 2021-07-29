from csv import writer
from datetime import datetime
from os import remove
from pathlib import Path

from cx_Oracle import connect, init_oracle_client
from pandas import concat, read_csv, read_excel
from typer import Exit, colors, confirm, echo, secho, style

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

TODAY = datetime.now().strftime("%d_%b_%Y")
YEAR = datetime.now().strftime("%Y")
TODAY_AS_Y_M_D = datetime.strptime(TODAY, "%d_%b_%Y").strftime("%Y_%m_%d")
GRADUATION_YEAR = str(int(datetime.now().strftime("%Y")) + 4)
INPUT, RESULTS, PROCESSED = get_command_paths("nso", input_dir=True, processed=True)
RESULT_PATH = RESULTS / f"{TODAY_AS_Y_M_D}_nso_result.csv"
PROCESSED_PATH = PROCESSED / f"nso_processed_users_{YEAR}.csv"
HEADERS = [
    "index",
    "canvas course id",
    "group set name",
    "group name",
    "pennkey",
    "status",
]


def find_nso_file():
    echo(") Finding NSO file...")

    if not INPUT.exists():
        Path.mkdir(INPUT, parents=True)
        error = style(
            "- ERROR: NSO input directory not found.",
            fg=colors.YELLOW,
        )
        echo(
            f"{error}\n- Creating one for you at: {colorize_path(str(INPUT))}\n- Please"
            " add an NSO input file matching the graduation year of this year's"
            " incoming freshmen to this directory and then run this script again.\n-"
            " (If you need detailed instructions, run this command with the '--help'"
            " flag.)"
        )

        raise Exit(1)
    else:
        CURRENT_FILE = ""
        EXTENSIONS = ["*.csv", "*.xlsx"]

        INPUT_FILES = list()

        for extension in EXTENSIONS:
            INPUT_FILES.extend(
                [input_file for input_file in Path(INPUT).glob(extension)]
            )

        for input_file in INPUT_FILES:
            if GRADUATION_YEAR in input_file.name:
                CURRENT_FILE = input_file
                CURRENT_EXTENSION = input_file.suffix

        if not CURRENT_FILE:
            error = style(
                "- ERROR: A nso file matching the graduation year of this"
                " year's incoming freshmen was not found.",
                fg=colors.YELLOW,
            )
            echo(
                f"{error}\n- Please add a NSO input file matching the"
                " graduation year of this year's incoming freshmen to the following"
                " directory and then run this script again:"
                f" {colorize_path(str(INPUT))}\n- (If you need detailed instructions,"
                " run this command with the '--help' flag.)"
            )

            raise Exit(1)
        else:
            return CURRENT_FILE, CURRENT_EXTENSION


def cleanup_data(input_file, extension, start=0):
    echo(") Preparing NSO file...")

    if extension == ".csv":
        data = read_csv(input_file)
    else:
        data = read_excel(input_file, engine="openpyxl")

    data.columns = data.columns.str.lower()
    data["user (pennkey)"] = data["user (pennkey)"].str.lower()
    data = data.astype("string", copy=False, errors="ignore")
    data[list(data)] = data[list(data)].apply(lambda column: column.str.strip())
    TOTAL = len(data.index)

    data = data.loc[start:TOTAL, :]

    return data, str(TOTAL)


def handle_clear_processed(clear_processed, processed_path):
    if clear_processed:
        proceed = confirm(
            "You have asked to clear the list of users already processed."
            " This list makes subsequent runs of the command faster. Are you sure"
            " you want to do this?"
        )
    else:
        proceed = False

    if proceed:
        echo(") Clearing list of users already processed...")

        if processed_path.exists():
            remove(processed_path)
    else:
        echo(") Finding users already processed...")


def make_find_group_name(group_name):
    def find_group_name(group):
        return group.name == group_name

    return find_group_name


def get_processed_users(processed_path):
    if processed_path.is_file():
        result = read_csv(processed_path)
        result = result.astype("string", copy=False, errors="ignore")
        return result["pennkey"].tolist()
    else:
        make_csv_paths(PROCESSED, processed_path, ["pennkey"])
        return list()


def process_result():
    result = read_csv(RESULT_PATH)
    NOT_ENROLLED = result[result["status"] == "user not enrolled in course"]
    NOT_IN_CANVAS = result[result["status"] == "user not found in canvas"]
    INVALID_PENNKEY = result[result["status"] == "invalid pennkey"]
    ERROR = result[result["status"] == "error"]
    NOT_ENROLLED_COUNT = str(len(NOT_ENROLLED.index))
    NOT_IN_CANVAS_COUNT = str(len(NOT_IN_CANVAS.index))
    INVALID_PENNKEY_COUNT = str(len(INVALID_PENNKEY.index))
    ERROR_COUNT = str(len(ERROR.index))
    result = concat([NOT_ENROLLED, NOT_IN_CANVAS, INVALID_PENNKEY, ERROR])
    result.drop("index", axis=1, inplace=True)
    result.to_csv(RESULT_PATH, index=False)

    return NOT_ENROLLED_COUNT, NOT_IN_CANVAS_COUNT, INVALID_PENNKEY_COUNT, ERROR_COUNT


def print_messages(not_enrolled, not_in_canvas, invalid_pennkey, error, total):
    secho("SUMMARY:", fg=colors.YELLOW)
    echo(f"- Processed {colorize(total)} users.")
    TOTAL_ERRORS = (
        int(not_enrolled) + int(not_in_canvas) + int(invalid_pennkey) + int(error)
    )
    accepted_count = style(
        str(int(total) - TOTAL_ERRORS),
        fg=colors.GREEN,
    )
    echo(f"- Successfully added {accepted_count} users to groups.")

    errors = False

    if int(not_enrolled) > 0:
        if int(not_enrolled) > 1:
            user = "users"
        else:
            user = "user"

        message = style(
            f"Found {not_enrolled} {user} not enrolled in the course.",
            fg=colors.RED,
        )
        echo(f"- {message}")
        errors = True

    if int(not_in_canvas) > 0:
        if int(not_in_canvas) > 1:
            user = "users"
            account = "Canvas accounts"
        else:
            user = "user"
            account = "a Canvas account"

        message = style(
            f"Found {not_in_canvas} {user} without {account}.", fg=colors.RED
        )
        echo(f"- {message}")
        errors = True

    if int(invalid_pennkey) > 0:
        if int(invalid_pennkey) > 1:
            user = "users"
            pennkey = "pennkeys"
        else:
            user = "user"
            pennkey = "pennkey"

        message = style(
            f"Found {invalid_pennkey} {user} with invalid {pennkey}.",
            fg=colors.RED,
        )
        echo(f"- {message}")
        errors = True

    if int(error) > 0:
        if int(error) > 1:
            user = "users"
        else:
            user = "user"

        message = style(
            f"Encountered an unknown error for {error} {user}.",
            fg=colors.RED,
        )
        echo(f"- {message}")
        errors = True

    if errors:
        result_path = style(f"{RESULT_PATH}", fg=colors.GREEN)
        echo(f"- Details recorded to result file: {result_path}")

    secho("FINISHED", fg=colors.YELLOW)


def nso_main(test, verbose, force, clear_processed):
    def create_enrollments(user, canvas, verbose, args):
        total, processed_users = args
        index, course_id, group_set_name, group_name, penn_key = user

        if force and penn_key in processed_users:
            status = "already processed"
        else:
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
                        echo(f") Creating group set {group_set_name}...")
                    group_set = course.create_group_category(group_set_name)

                group_filter = make_find_group_name(group_name)
                group = next(filter(group_filter, group_set.get_groups()), None)

                if not group:
                    if verbose:
                        echo(f") Creating group {group_name}...")
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
                        status = "user not enrolled in course"
                except Exception as error:
                    status = error

                    try:
                        if verbose:
                            penn_key_display = style(penn_key, fg=colors.CYAN)
                            echo(
                                ") Checking the Data Warehouse for pennkey:"
                                f" {penn_key_display}..."
                            )

                        cursor = connect(
                            DATA_WAREHOUSE_USER,
                            DATA_WAREHOUSE_PASSWORD,
                            DATA_WAREHOUSE_DSN,
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

                        for user in cursor:
                            if len(user) > 0:
                                status = "user not found in canvas"
                                break
                    except Exception as error:
                        status = error

        data.at[index, "status"] = status
        data.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)

        if verbose:
            status_display = str(status).upper()

            if status_display == "ADDED":
                status_display = style(status_display, fg=colors.GREEN)
            elif status_display == "ALREADY PROCESSED":
                status_display = style(status_display, fg=colors.YELLOW)
            else:
                status_display = style(status_display, fg=colors.RED)

            penn_key_display = style(penn_key, fg=colors.MAGENTA)
            echo(
                f"- ({index + 1}/{total}) {penn_key_display}, {group_set_name},"
                f" {group_name}: {status_display}"
            )

        if status == "added" and penn_key not in processed_users:
            with open(PROCESSED_PATH, "a+", newline="") as processed_file:
                writer(processed_file).writerow([penn_key])

    data, EXTENSION = find_nso_file()
    (
        DATA_WAREHOUSE_USER,
        DATA_WAREHOUSE_PASSWORD,
        DATA_WAREHOUSE_DSN,
    ) = get_data_warehouse_config()
    START = get_start_index(force, RESULT_PATH)
    data, TOTAL = cleanup_data(data, EXTENSION, START)
    handle_clear_processed(clear_processed, PROCESSED_PATH)
    PROCESSED_USERS = get_processed_users(PROCESSED_PATH)
    make_csv_paths(RESULTS, RESULT_PATH, HEADERS)
    make_skip_message(START, "user")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)

    echo(") Processing users...")

    toggle_progress_bar(
        data,
        create_enrollments,
        CANVAS,
        verbose,
        args=(TOTAL, PROCESSED_USERS),
        index=True,
    )
    not_enrolled, not_in_canvas, invalid_pennkey, error = process_result()
    print_messages(not_enrolled, not_in_canvas, invalid_pennkey, error, TOTAL)
