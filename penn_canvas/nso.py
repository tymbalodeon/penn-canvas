from csv import writer
from datetime import datetime
from pathlib import Path

from cx_Oracle import connect
from natsort import natsorted
from pandas import Categorical, DataFrame, concat, isna, read_csv, read_excel
from typer import Abort, Exit, echo

from .helpers import (
    TODAY_AS_Y_M_D,
    YEAR,
    colorize,
    get_canvas,
    get_command_paths,
    get_data_warehouse_config,
    get_processed,
    get_start_index,
    handle_clear_processed,
    make_csv_paths,
    make_skip_message,
    toggle_progress_bar,
)

GRADUATION_YEAR = str(int(datetime.now().strftime("%Y")) + 4)
INPUT, RESULTS, PROCESSED = get_command_paths("NSO", processed=True)
FINAL_LIST_PATH = RESULTS / f"{YEAR}_nso_final_list.csv"
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
        error = colorize("- ERROR: NSO input directory not found.", "yellow")
        echo(
            f"{error}\n- Creating one for you at: {colorize(INPUT, 'green')}\n- Please"
            " add an NSO input file matching the graduation year of this year's"
            " incoming freshmen to this directory and then run this script again.\n-"
            " (If you need detailed instructions, run this command with the '--help'"
            " flag.)"
        )

        raise Exit(1)
    else:
        XLSX_FILES = [input_file for input_file in Path(INPUT).glob("*.xlsx")]
        CURRENT_FILE = next(
            (
                input_file
                for input_file in XLSX_FILES
                if GRADUATION_YEAR in input_file.name and "~$" not in input_file.name
            ),
            None,
        )

        if not CURRENT_FILE:
            error = colorize(
                "- ERROR: A nso file matching the graduation year of this"
                " year's incoming freshmen was not found.",
                "yellow",
            )
            echo(
                f"{error}\n- Please add a NSO input file matching the"
                " graduation year of this year's incoming freshmen to the following"
                " directory and then run this script again:"
                f" {colorize(INPUT, 'green')}\n- (If you need detailed instructions,"
                " run this command with the '--help' flag.)"
            )

            raise Exit(1)
        else:
            return CURRENT_FILE


def cleanup_data(input_file, start=0):
    echo(") Preparing NSO file...")

    data = read_excel(input_file, engine="openpyxl", sheet_name=None)

    try:
        facilitators = data[0]
        students = data[1]
    except Exception:
        colorize(
            "- ERROR: input file does not contain two sheets. A sheet for"
            " facilitators and a sheet for students is required. Please provide a"
            " valid input file and try again.",
            "yellow",
            True,
        )
    raise Abort()

    facilitators["Group Name"] = Categorical(
        facilitators["Group Name"],
        ordered=True,
        categories=natsorted(facilitators["Group Name"].unique()),
    )
    facilitators = facilitators.sort_values("Group Name")
    group_names = facilitators["Group Name"].to_list()
    group_numbers = [
        int(
            (
                "".join(
                    character for character in group_name if not character.isalpha()
                )
            ).strip()
        )
        for group_name in group_names
    ]
    number_of_groups = max(group_numbers)
    canvas_course_id = facilitators["Canvas Course ID"].drop_duplicates().tolist()[0]
    group_set_name = facilitators["Group Set Name"].drop_duplicates().tolist()[0]
    students = students["PennKey"].tolist()
    group_name_base = "".join(
        character
        for character in group_names[0]
        if character.isalpha() or character.isspace()
    )
    students = [
        [
            canvas_course_id,
            group_set_name,
            f"{group_name_base}{(index % number_of_groups) + 1}",
            student,
        ]
        for index, student in enumerate(students)
    ]

    students = DataFrame(
        students,
        columns=["Canvas Course ID", "Group Set Name", "Group Name", "User (Pennkey)"],
    )
    data = concat([facilitators, students], ignore_index=True)
    data.columns = data.columns.str.lower()
    data["user (pennkey)"] = data["user (pennkey)"].str.lower()
    data = data.astype("string", copy=False, errors="ignore")
    data[list(data)] = data[list(data)].apply(lambda column: column.str.strip())
    TOTAL = len(data.index)

    data = data.loc[start:TOTAL, :]

    return data, TOTAL


def process_result(test, result_path):
    result = read_csv(result_path)
    ALREADY_PROCESSED = result[result["status"] == "already processed"]
    ADDED = result[result["status"] == "added"]
    ENROLLED = result[result["status"] == "enrolled and added"]
    NOT_ENROLLED = result[result["status"] == "failed to enroll user in course"]
    NOT_IN_CANVAS = result[result["status"] == "user not found in canvas"]
    INVALID_PENNKEY = result[result["status"] == "invalid pennkey"]
    ERROR = result[
        (result["status"] != "already processed")
        & (result["status"] != "added")
        & (result["status"] != "enrolled and added")
        & (result["status"] != "failed to enroll user in course")
        & (result["status"] != "user not found in canvas")
        & (result["status"] != "invalid pennkey")
    ]
    result = concat([ENROLLED, NOT_ENROLLED, NOT_IN_CANVAS, INVALID_PENNKEY, ERROR])
    result.drop("index", axis=1, inplace=True)
    result.to_csv(result_path, index=False)
    final_list = concat([ALREADY_PROCESSED, ADDED, ENROLLED])
    final_list.drop(["index", "status"], axis=1, inplace=True)
    final_list["group name"] = Categorical(
        final_list["group name"],
        ordered=True,
        categories=natsorted(final_list["group name"].unique()),
    )
    final_list = final_list.sort_values("group name")
    final_list.to_csv(FINAL_LIST_PATH, index=False)

    if test:
        test_final_list = RESULTS / f"{FINAL_LIST_PATH}_test.csv"
        FINAL_LIST_PATH.rename(test_final_list)

    return (
        len(ALREADY_PROCESSED.index),
        len(ADDED.index),
        len(ENROLLED.index),
        len(NOT_ENROLLED.index),
        len(NOT_IN_CANVAS.index),
        len(INVALID_PENNKEY.index),
        len(ERROR.index),
    )


def print_messages(
    already_processed,
    added,
    enrolled,
    not_enrolled,
    not_in_canvas,
    invalid_pennkey,
    error,
    total,
    result_path,
):
    colorize("SUMMARY:", "yellow")
    echo(f"- Processed {colorize(total, 'magenta'):,} users.")
    added_count = colorize(added + enrolled, "green")
    echo(f"- Successfully added {added_count:,} users to groups.")

    errors = False

    if enrolled > 0:
        if enrolled > 1:
            user = "users"
        else:
            user = "user"

        message = colorize(
            f"Automatically enrolled {enrolled:,} {user} in the course.", "yellow"
        )
        echo(f"- {message}")

    if already_processed > 0:
        if already_processed > 1:
            user = "users"
        else:
            user = "user"

        message = colorize(
            f"{already_processed:,} {user} already added to group.", "yellow"
        )
        echo(f"- {message}")

    if not_enrolled > 0:
        if not_enrolled > 1:
            user = "users"
        else:
            user = "user"

        message = colorize(
            f"Found {not_enrolled:,} {user} not enrolled in the course.", "red"
        )
        echo(f"- {message}")
        errors = True

    if not_in_canvas > 0:
        if not_in_canvas > 1:
            user = "users"
            account = "Canvas accounts"
        else:
            user = "user"
            account = "a Canvas account"

        message = colorize(f"Found {not_in_canvas:,} {user} without {account}.", "red")
        echo(f"- {message}")
        errors = True

    if invalid_pennkey > 0:
        if invalid_pennkey > 1:
            user = "users"
            pennkey = "pennkeys"
        else:
            user = "user"
            pennkey = "pennkey"

        message = colorize(
            f"Found {invalid_pennkey:,} {user} with invalid {pennkey}.", "red"
        )
        echo(f"- {message}")
        errors = True

    if error > 0:
        if error > 1:
            user = "users"
        else:
            user = "user"

        message = colorize(f"Encountered an unknown error for {error:,} {user}.", "red")
        echo(f"- {message}")
        errors = True

    if errors:
        result_path = colorize(result_path, "green")
        echo(f"- Details recorded to: {result_path}")

    final_list_path = colorize(FINAL_LIST_PATH, "green")
    echo(f"- Final Group membership assignments recorded to: {final_list_path}")
    colorize("FINISHED", "yellow", True)


def nso_main(test, verbose, force, clear_processed):
    def create_group_membership(
        canvas, course_id, group_set_name, group_name, penn_key, enroll_in_course=False
    ):
        course = canvas.get_course(course_id)

        group_set = next(
            (
                group_set
                for group_set in course.get_group_categories()
                if group_set.name == group_set_name
            ),
            None,
        )
        if not group_set:
            if verbose:
                echo(f") Creating group set {group_set_name}...")
            group_set = course.create_group_category(group_set_name)

        group = next(
            (group for group in group_set.get_groups() if group.name == group_name),
            None,
        )

        if not group:
            if verbose:
                echo(f") Creating group {group_name}...")
            group = group_set.create_group(name=group_name)

        canvas_user = canvas.get_user(penn_key, "sis_login_id")
        group.create_membership(canvas_user)

        if enroll_in_course:
            return "enrolled and added", "cyan"
        else:
            return "added", "green"

    def create_memberships(user, canvas, verbose, args):
        total, processed_users = args
        index, course_id, group_set_name, group_name, penn_key = user

        if isna(penn_key):
            status = "invalid pennkey"
            color = "red"
        elif force and penn_key in processed_users:
            status = "already processed"
            color = "yellow"
        else:
            try:
                status, color = create_group_membership(
                    canvas, course_id, group_set_name, group_name, penn_key
                )
            except Exception as error:
                try:
                    course = canvas.get_course(course_id)
                    canvas_user = canvas.get_user(penn_key, "sis_login_id")
                    status = error
                    color = "red"

                    try:
                        course.get_user(canvas_user)
                    except Exception:
                        try:
                            course.enroll_user(canvas_user)
                            status, color = create_group_membership(
                                canvas,
                                course_id,
                                group_set_name,
                                group_name,
                                penn_key,
                                True,
                            )
                        except Exception:
                            status = "failed to enroll user in course"
                except Exception as error:
                    status = error
                    color = "red"

                    try:
                        if verbose:
                            penn_key_display = colorize(penn_key, "cyan")
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
            status_display = colorize(status_display, color)
            penn_key_display = colorize(penn_key, "magenta")
            echo(
                f"- ({index + 1}/{total}) {penn_key_display}, {group_set_name},"
                f" {group_name}: {status_display}"
            )

        if (
            status == "added" or status == "enrolled and added"
        ) and penn_key not in processed_users:
            with open(PROCESSED_PATH, "a+", newline="") as processed_file:
                writer(processed_file).writerow([penn_key])

    RESULT_PATH = (
        RESULTS / f"{YEAR}_nso_result_{TODAY_AS_Y_M_D}{'_test' if test else ''}.csv"
    )
    PROCESSED_PATH = (
        PROCESSED / f"nso_processed_users_{YEAR}{'_test' if test else ''}.csv"
    )
    data = find_nso_file()
    (
        DATA_WAREHOUSE_USER,
        DATA_WAREHOUSE_PASSWORD,
        DATA_WAREHOUSE_DSN,
    ) = get_data_warehouse_config()
    START = get_start_index(force, RESULT_PATH)
    data, TOTAL = cleanup_data(data, START)
    handle_clear_processed(clear_processed, PROCESSED_PATH)
    PROCESSED_USERS = get_processed(PROCESSED, PROCESSED_PATH)
    make_csv_paths(RESULTS, RESULT_PATH, HEADERS)
    make_skip_message(START, "user")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)

    echo(") Processing users...")

    toggle_progress_bar(
        data, create_memberships, CANVAS, verbose, args=(TOTAL, PROCESSED_USERS)
    )
    (
        already_processed,
        added,
        enrolled,
        not_enrolled,
        not_in_canvas,
        invalid_pennkey,
        error,
    ) = process_result(test, RESULT_PATH)
    print_messages(
        already_processed,
        added,
        enrolled,
        not_enrolled,
        not_in_canvas,
        invalid_pennkey,
        error,
        TOTAL,
        RESULT_PATH,
    )
