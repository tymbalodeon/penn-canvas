from pathlib import Path

from pandas import isna, read_csv
from typer import echo

from .helpers import (
    BOX_PATH,
    MONTH,
    TODAY_AS_Y_M_D,
    YEAR,
    colorize,
    find_input,
    get_canvas,
    get_command_paths,
    get_start_index,
    make_csv_paths,
    make_index_headers,
    make_skip_message,
    process_input,
    toggle_progress_bar,
)

COMMAND = "Storage"
INPUT_FILE_NAME = "Canvas Course Storage report"
REPORTS, RESULTS = get_command_paths(COMMAND)
RESULT_PATH = RESULTS / f"{TODAY_AS_Y_M_D}_storage_result.csv"
HEADERS = [
    "id",
    "sis id",
    "account id",
    "storage used in MB",
    "old quota",
    "new quota",
    "error",
]
SUB_ACCOUNTS = [
    "132477",
    "99243",
    "99237",
    "132280",
    "107448",
    "132413",
    "128877",
    "99241",
    "99244",
    "99238",
    "99239",
    "131752",
    "131428",
    "99240",
    "132153",
    "82192",
]


def cleanup_data(data):
    data = data[data["storage used in MB"] > 0].copy()
    data.sort_values(by=["storage used in MB"], inplace=True)
    data = data.astype("string", errors="ignore")

    return data[data["account id"].isin(SUB_ACCOUNTS)]


def check_percent_storage(course, canvas, verbose, total):
    index, canvas_id, sis_id, account_id, storage_used = course

    try:
        canvas_course = canvas.get_course(canvas_id)
        percentage_used = float(storage_used) / canvas_course.storage_quota_mb

        if verbose:
            if percentage_used >= 0.79:
                color = "yellow"
            else:
                color = "green"

            echo(
                f"- ({(index + 1):,}/{total}) {sis_id} ({canvas_id}):"
                f" {colorize(f'{int(percentage_used * 100)}%', color)}"
            )

        if percentage_used >= 0.79:
            if verbose:
                colorize("\t* INCREASE REQUIRED", "yellow", True)
            if isna(sis_id):
                if verbose:
                    message = colorize(
                        "- ACTION REQUIRED: A SIS ID must be added for course:"
                        f" {canvas_id}",
                        "yellow",
                    )
                    echo(f"({(index + 1):,}/{total}) {message}")

                return False, "missing sis id"
            else:
                return True, sis_id
        else:
            return False, None
    except Exception:
        if verbose:
            message = colorize(f"ERROR: {sis_id} ({canvas_id}) NOT FOUND", "red")
            echo(f"- (({index + 1):,}/{total}) {message}")
        return False, "course not found"


def increase_quota(sis_id, canvas, verbose, increase):
    if sis_id[:4] != "SRS_":
        middle = sis_id[:-5][-6:]
        sis_id = f"SRS_{sis_id[:11]}-{middle[:3]}-{middle[3:]} {sis_id[-5:]}"

    try:
        canvas_course = canvas.get_course(
            sis_id,
            use_sis_id=True,
        )
        subaccount_id = str(canvas_course.account_id)
        error = "none"
    except Exception:
        canvas_course = None
        subaccount_id = "ERROR"
        error = "course not found"

    if canvas_course:
        old_quota = canvas_course.storage_quota_mb
        new_quota = old_quota + increase
        old_quota = str(int(old_quota))
        new_quota = str(int(new_quota))

        try:
            canvas_course.update(course={"storage_quota_mb": new_quota})

            if verbose:
                echo(f"\t* Increased storage from {old_quota} MB to {new_quota} MB")
        except Exception:
            new_quota = "ERROR"

            if verbose:
                colorize(
                    f"\t* Failed to increase quota for Canvas course ID: {sis_id}",
                    "yellow",
                    True,
                )
    else:
        old_quota = "N/A"
        new_quota = "N/A"

    return [subaccount_id, sis_id, old_quota, new_quota, error]


def process_result():
    result = read_csv(RESULT_PATH, dtype=str)
    increased_count = len(result[result["error"] == "none"].index)
    result.drop(result[result["error"] == "increase not required"].index, inplace=True)
    error_count = len(result[result["error"] != "none"].index)

    if error_count == 0:
        result.drop(columns=["error"], inplace=True)

    result.fillna("N/A", inplace=True)
    result.drop(columns=["index", "account id", "storage used in MB"], inplace=True)
    result.rename(columns={"id": "subaccount id", "sis id": "course id"}, inplace=True)
    result.to_csv(RESULT_PATH, index=False)

    if BOX_PATH.exists():
        storage_shared_directory = BOX_PATH / "Storage_Quota_Monitoring"
        this_month_directory = next(
            (
                directory
                for directory in storage_shared_directory.iterdir()
                if YEAR in directory.name and MONTH in directory.name
            ),
            None,
        )

        try:
            if not this_month_directory:
                Path.mkdir(storage_shared_directory / f"{MONTH} {YEAR}")
                this_month_directory = next(
                    (
                        directory
                        for directory in storage_shared_directory.iterdir()
                        if YEAR in directory.name and MONTH in directory.name
                    ),
                    None,
                )

            box_result_path = this_month_directory / RESULT_PATH.name
            result.to_csv(box_result_path, index=False)
        except Exception as error:
            echo(f"- ERROR: {error}")

    return increased_count, error_count


def print_messages(total, increased, errors):
    colorize("SUMMARY:", "yellow", True)
    echo(f"- Processed {colorize(total, 'magenta')} courses.")
    echo(f"- Increased storage quota for {colorize(increased, 'yellow')} courses.")

    if errors > 0:
        echo(f"- {colorize(f'Failed to find {str(errors)} courses.', 'red')}")

    colorize("FINISHED", "yellow", True)


def storage_main(test, verbose, force, increase=1000):
    def check_and_increase_storage(course, canvas, verbose, args):
        index = course[0]
        canvas_id = course[1]
        sis_id = course[2]
        total, increase = args

        needs_increase, message = check_percent_storage(course, canvas, verbose, total)

        if needs_increase:
            row = increase_quota(message, canvas, verbose, increase)
        elif message is None:
            row = [canvas_id, sis_id, "N/A", "N/A", "increase not required"]
        else:
            row = ["ERROR", sis_id, "N/A", "N/A", message]

        report.loc[
            index,
            [
                "id",
                "sis id",
                "old quota",
                "new quota",
                "error",
            ],
        ] = row
        report.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)

    report, please_add_message, missing_file_message = find_input(
        COMMAND, INPUT_FILE_NAME, REPORTS
    )
    START = get_start_index(force, RESULT_PATH)
    report, TOTAL = process_input(
        report,
        INPUT_FILE_NAME,
        REPORTS,
        please_add_message,
        HEADERS[:4],
        cleanup_data,
        missing_file_message,
        START,
    )
    make_csv_paths(RESULTS, RESULT_PATH, make_index_headers(HEADERS))
    make_skip_message(START, "course")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)

    echo(") Processing courses...")

    toggle_progress_bar(
        report, check_and_increase_storage, CANVAS, verbose, args=(TOTAL, increase)
    )
    INCREASED_COUNT, ERROR_COUNT = process_result()
    print_messages(TOTAL, INCREASED_COUNT, ERROR_COUNT)
