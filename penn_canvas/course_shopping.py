from csv import writer

from pandas import concat, read_csv
from pandas.core.frame import DataFrame
from typer import Exit, echo

from .helpers import (
    TODAY,
    YEAR,
    color,
    find_input,
    get_canvas,
    get_command_paths,
    get_processed,
    get_start_index,
    get_sub_accounts,
    make_csv_paths,
    make_index_headers,
    make_skip_message,
    process_input,
    toggle_progress_bar,
)


def remove_underscores(word):
    return word.replace("_", " ")


COMMAND = "Course Shopping"
INPUT_FILE_NAME = "Canvas Provisioning (Courses) report"
REPORTS, RESULTS, PROCESSED = get_command_paths(COMMAND, processed=True)
HEADERS = ["canvas_course_id", "course_id", "canvas_account_id", "status"]
CLEANUP_HEADERS = HEADERS[:4]
PROCESSED_HEADERS = [remove_underscores(header) for header in [HEADERS[0], HEADERS[-1]]]
SAS_ONL_ACCOUNT = "132413"
ADMIN_ACCOUNT = "131963"
WHARTON_ACCOUNT_ID = "81471"
SAS_ACCOUNT_ID = "99237"
SEAS_ACCOUNT_ID = "99238"
NURS_ACCOUNT_ID = "99239"
AN_ACCOUNT_ID = "99243"
IGNORED_SUBJECTS = ["MAPP", "IMPA", "DYNM"]
IGNORED_SITES = ["1529220"]
SAS_IGNORED_ACCOUNTS = [SAS_ONL_ACCOUNT, ADMIN_ACCOUNT]
WHARTON_ACCOUNT_ID = "81471"
SUB_ACCOUNT_EXCLUDE = "82603"


def cleanup_data(data, args):
    processed_courses, processed_errors, new = args
    data.drop_duplicates(subset=["canvas_course_id"], inplace=True)
    data.dropna(subset=["course_id"], inplace=True)
    data = data.astype("string", copy=False, errors="ignore")
    data = data[~data["canvas_course_id"].isin(processed_courses)]
    already_processed_count = len(processed_courses)
    if new:
        data = data[~data["canvas_course_id"].isin(processed_errors)]
        already_processed_count = already_processed_count + len(processed_errors)
    if already_processed_count:
        message = color(
            f"SKIPPING {already_processed_count:,} PREVIOUSLY PROCESSED"
            f" {'COURSE' if already_processed_count == 1 else 'COURSES'}...",
            "yellow",
        )
        echo(f") {message}")
    return data


def course_contains_srs(course_id):
    try:
        return course_id.startswith("SRS_")
    except Exception:
        return False


def section_contains_srs(canvas_course):
    try:
        srs_section = next(
            section
            for section in canvas_course.get_sections()
            if section.sis_section_id and section.sis_section_id.startswith("SRS_")
        )
        return bool(srs_section)
    except Exception:
        return course_contains_srs(canvas_course.id)


def print_messages(total):
    color("SUMMARY:", "yellow", True)
    echo(f"- Processed {color(total)} courses.")
    color("FINISHED", "yellow", True)


def process_result(result_path, processed_path):
    result = read_csv(result_path, dtype=str)
    processed = read_csv(processed_path, dtype=str)
    processed.sort_values("status", inplace=True)
    processed.to_csv(processed_path, index=False)
    result.drop(columns=["index"], inplace=True)
    renamed_headers = [header.replace("_", " ") for header in HEADERS[:5]]
    renamed_columns = {}
    for index, header in enumerate(renamed_headers):
        renamed_columns[HEADERS[index]] = header
    result.rename(columns=renamed_columns, inplace=True)
    result.fillna("N/A", inplace=True)
    result = result[result["status"] != "already enabled"]
    result.sort_values("course id", inplace=True)
    invalid_id = result[result["status"] == "invalid account id"]
    not_SRS = result[result["status"] == "not SRS"]
    course_opted_out = result[result["status"] == "course opted out"]
    school_opted_out = result[result["status"] == "school opted out"]
    course_not_found = result[result["status"] == "course not found"]
    ignored_subject = result[result["status"] == "ignored subject"]
    failed_to_parse = result[result["status"] == "failed to parse course code"]
    enabled = result[result["status"] == "enabled"]
    failed_to_enable = result[result["status"] == "failed to enable"]
    grad_course = result[result["status"] == "grad course"]
    errors = concat(
        [
            failed_to_enable,
            invalid_id,
            course_not_found,
            failed_to_parse,
        ]
    )
    processed = concat(
        [
            not_SRS,
            course_opted_out,
            school_opted_out,
            ignored_subject,
            grad_course,
            enabled,
        ]
    )
    result = concat([errors, processed])
    result.to_csv(result_path, index=False)


def course_shopping_main(test, disable, force, verbose, new):
    def enable_course_shopping(course, canvas, verbose):
        index, canvas_course_id, course_id, canvas_account_id, status = course
        if not canvas_account_id.isnumeric():
            status = "invalid account id"
        elif (
            not course_contains_srs(course_id)
            and canvas_account_id not in WHARTON_ACCOUNTS
        ):
            status = "not SRS"
        elif canvas_course_id in IGNORED_SITES:
            status = "course opted out"
        elif canvas_account_id not in SUB_ACCOUNTS:
            status = "school opted out"
        else:
            canvas_course = None
            try:
                canvas_course = canvas.get_course(canvas_course_id)
            except Exception:
                status = "course not found"
            if canvas_course:
                update = False
                try:
                    if canvas_account_id in WHARTON_ACCOUNTS:
                        course_id = course_id.replace("2021", "")
                        subject = "".join(
                            character for character in course_id if character.isalpha()
                        )
                        course_number = int(
                            "".join(
                                character
                                for character in course_id
                                if character.isnumeric()
                            )
                        )
                    else:
                        subject = course_id.split("-")[0][4:]
                        course_number = int(course_id.split("-")[1])
                    if (
                        canvas_account_id in SEAS_ACCOUNTS
                        or (canvas_account_id in NURS_ACCOUNTS and course_number <= 600)
                        or (
                            canvas_account_id in AN_ACCOUNTS
                            and course_number <= 500
                            and subject == "COMM"
                        )
                    ):
                        update = True
                    elif canvas_account_id in SAS_ACCOUNTS and course_number <= 500:
                        if subject in IGNORED_SUBJECTS:
                            echo("- Ignored subject.")
                            status = "ignored subject"
                        else:
                            update = True
                    elif canvas_account_id in WHARTON_ACCOUNTS:
                        if not section_contains_srs(canvas_course):
                            status = "not SRS"
                        elif canvas_course_id in WHARTON_IGNORED_COURSES:
                            status = "course opted out"
                        elif canvas_account_id == SUB_ACCOUNT_EXCLUDE:
                            status = "school opted out"
                        else:
                            update = True
                except Exception:
                    status = "failed to parse course code"
                if update:
                    try:
                        canvas_course.update(course={"is_public_to_auth_users": True})
                        status = "enabled"
                    except Exception:
                        status = "failed to enable"
                else:
                    status = "grad course"
        report.at[index, HEADERS] = [
            canvas_course_id,
            course_id,
            canvas_account_id,
            status,
        ]
        report.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)
        if verbose:
            echo(
                f"- ({(index + 1):,}/{TOTAL})"
                f" {color(course_id, 'magenta')}:"
                f" {color(status.upper(), 'green') if status == 'enabled' else color(status, 'yellow')}"
            )
        if status in {
            "not SRS",
            "course opted out",
            "school opted out",
            "ignored subject",
            "enabled",
            "grad course",
        }:
            if canvas_course_id in PROCESSED_ERRORS:
                processed_errors_csv = read_csv(PROCESSED_ERRORS_PATH)
                processed_errors_csv = processed_errors_csv[
                    processed_errors_csv["canvas course id"] != canvas_course_id
                ]
                processed_errors_csv.to_csv(PROCESSED_ERRORS_PATH, index=False)
            with open(PROCESSED_PATH, "a+", newline="") as processed_file:
                writer(processed_file).writerow([canvas_course_id, status])
        elif canvas_course_id not in PROCESSED_ERRORS:
            with open(PROCESSED_ERRORS_PATH, "a+", newline="") as processed_file:
                writer(processed_file).writerow([canvas_course_id, status])

    def disable_course_shopping(processed_path, result_path, canvas, verbose):
        processed = read_csv(processed_path)
        processed = processed[processed["status"] == "enabled"]
        if processed.empty:
            echo("- No courses to disable.")
            Exit()
        if not result_path.is_file():
            with open(result_path, "w+") as result_file:
                result_file.write(
                    f"{','.join(make_index_headers(PROCESSED_HEADERS))}\n"
                )
        total = len(processed.index)
        for course in processed.itertuples():
            index, canvas_course_id = course[:2]
            course_display = canvas_course_id
            try:
                canvas_course = canvas.get_course(canvas_course_id)
                canvas_course.update(
                    course={
                        "is_public": False,
                        "is_public_to_auth_users": False,
                        "public_syllabus": False,
                        "public_syllabus_to_auth": False,
                    }
                )
                status = "disabled"
                course_display = canvas_course.name
            except Exception:
                status = "failed to disable"
            with open(result_path, "a") as writer:
                writer.write(f"{index},{canvas_course_id},{status}\n")
            processed = read_csv(processed_path)
            processed = processed[processed["canvas course id"] != canvas_course_id]
            processed.to_csv(processed_path, index=False)
            if verbose:
                echo(
                    f"- ({(index + 1):,}/{total})"
                    f" {color(course_display, 'magenta')}:"
                    f" {color(status.upper(), 'green') if status == 'disabled' else color(status, 'yellow')}"
                )
        result = read_csv(result_path)
        result.drop(columns=["index"], inplace=True)
        result.to_csv(result_path, index=False)

    PROCESSED_PATH = (
        PROCESSED
        / f"{YEAR}_course_shopping_processed_courses{'_test' if test else ''}.csv"
    )
    PROCESSED_ERRORS_PATH = (
        PROCESSED
        / f"{YEAR}_course_shopping_processed_errors{'_test' if test else ''}.csv"
    )
    PROCESSED_COURSES = get_processed(PROCESSED, PROCESSED_PATH, PROCESSED_HEADERS)
    PROCESSED_ERRORS = get_processed(
        PROCESSED, PROCESSED_ERRORS_PATH, PROCESSED_HEADERS
    )
    TOTAL = ""
    report = DataFrame()
    RESULT_PATH = (
        RESULTS
        / f"{YEAR}_course_shopping_{'disabled' if disable else 'enabled'}_{TODAY}{'_test' if test else ''}.csv"
    )
    if not disable:
        reports, missing_file_message = find_input(INPUT_FILE_NAME, REPORTS)
        START = get_start_index(force, RESULT_PATH, RESULTS)
        cleanup_data_args = (PROCESSED_COURSES, PROCESSED_ERRORS, new)
        report, TOTAL = process_input(
            reports,
            INPUT_FILE_NAME,
            REPORTS,
            CLEANUP_HEADERS,
            cleanup_data,
            missing_file_message,
            cleanup_data_args,
            START,
        )
        make_csv_paths(
            RESULTS,
            RESULT_PATH,
            make_index_headers(HEADERS),
        )
        make_skip_message(START, "course")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)
    SAS_ACCOUNTS = get_sub_accounts(CANVAS, SAS_ACCOUNT_ID)
    for account in SAS_IGNORED_ACCOUNTS:
        SAS_ACCOUNTS.remove(account)
    SEAS_ACCOUNTS = get_sub_accounts(CANVAS, SEAS_ACCOUNT_ID)
    NURS_ACCOUNTS = get_sub_accounts(CANVAS, NURS_ACCOUNT_ID)
    AN_ACCOUNTS = get_sub_accounts(CANVAS, AN_ACCOUNT_ID)
    WHARTON_ACCOUNTS = get_sub_accounts(CANVAS, WHARTON_ACCOUNT_ID)
    SUB_ACCOUNTS = (
        SAS_ACCOUNTS + SEAS_ACCOUNTS + NURS_ACCOUNTS + AN_ACCOUNTS + WHARTON_ACCOUNTS
    )
    WHARTON_IGNORED_PATH = REPORTS / "wharton_ignored_courses.csv"
    if WHARTON_IGNORED_PATH.is_file():
        WHARTON_IGNORED_COURSES = read_csv(WHARTON_IGNORED_PATH)[
            "canvas course id"
        ].tolist()
    else:
        WHARTON_IGNORED_COURSES = []
    echo(") Processing courses...")
    if disable:
        disable_course_shopping(PROCESSED_PATH, RESULT_PATH, CANVAS, verbose)
    else:
        toggle_progress_bar(report, enable_course_shopping, CANVAS, verbose)
        process_result(RESULT_PATH, PROCESSED_PATH)
        print_messages(TOTAL)
