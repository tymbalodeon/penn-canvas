"""
~~~~~~~~~~~~ COURSE SHOPPING ~~~~~~~~~~~~~~~~
get a provisioning report of all courses
1. delete all columns but: canvas_id, sis_id, short_name, account_id, status
2. delete all rows with blank sis_ids !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!1
3. compare with master and remove and previously seen courses
4. create one file for WH (sis_id !startwith SRS_) and one for rest
5. run enable_course_shopping() on non wharton file
6. run WHARTON_enable_course_shopping() on wharton file
7. upload each file results to pennbox
8. add newly enabled to MASTER
9. upload new version of MASTER

"""

from csv import writer
from datetime import datetime

from pandas import concat, read_csv
from typer import echo

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

HEADERS = ["canvas_course_id", "course_id", "canvas_account_id", "status"]
CLEANUP_HEADERS = [header.replace(" ", "_") for header in HEADERS[:4]]
PROCESSED_HEADERS = [HEADERS[0], HEADERS[-1]]


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
            f" {'USER' if already_processed_count == 1 else 'USERS'}...",
            "yellow",
        )
        echo(f") {message}")
    return data


COMMAND = "Course Shopping"
INPUT_FILE_NAME = "Canvas Provisioning (Courses) report"
REPORTS, RESULTS, PROCESSED = get_command_paths(COMMAND, processed=True)
TIME = datetime.now().strftime("%d_%b_%Y")
canvas_id_in_master = []
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


def course_contains_srs(course_id):
    try:
        return course_id.startswith("SRS_")
    except Exception:
        return False


# def section_contains_srs(canvas, canvas_id):
#     course = canvas.get_course(canvas_id)
#     sections = course.get_sections()
#     srs_section = next(
#         filter(lambda section: section.sis_section_id.startswith("SRS_"), sections),
#         None,
#     )
#     return bool(srs_section)


# def load_master():
#     master = open(MASTER_FILE, "r")
#     master.readline()

#     for line in master:
#         sis_id, canvas_id, visibility_status, published, notes = line.strip().split(",")
#         if visibility_status.strip() == "public_to_auth_users":
#             canvas_id_in_master.append(canvas_id.strip())

#     master.close()


# def enable_wharton_course_shopping(inputfile, outputfile):
#     canvas = get_canvas(TESTING)

#     WHARTON_ACCOUNT_ID = 81471
#     WHARTON_ACCOUNTS = get_sub_accounts(canvas, WHARTON_ACCOUNT_ID)
#     SUB_ACCOUNT_EXCLUDE = 82603

#     dataFile = open(inputfile, "r")
#     dataFile.readline()

#     outFile = open(outputfile, "w+")
#     outFile.write("sis_id, canvas_id, visibility_status, published, notes\n")

#     for line in dataFile:
#         canvas_id, sis_id, short_name, account_id, status = line.replace(
#             "\n", ""
#         ).split(",")

#         if len(sis_id) > 0 and canvas_id not in canvas_id_in_master:
#             notes = ""
#             canvas_course = None

#             try:
#                 canvas_course = canvas.get_course(canvas_id)
#                 published = status
#             except Exception:
#                 notes = "couldnt find course"
#                 published = "ERROR"

#             if canvas_course:
#                 if not account_id.isnumeric():
#                     print("\t Invalid account_id %s", account_id)
#                 elif (
#                     int(account_id) not in WHARTON_ACCOUNTS
#                 ):  # then we should not update this site!!!!
#                     print("\t school not participating")
#                     notes += "/ NOT WHARTON"
#                     outFile.write(
#                         "%s, %s, %s, %s, %s\n"
#                         % (sis_id, canvas_id, status, published, notes)
#                     )

#                 else:  # account id in WHARTON_ACCOUNTS
#                     update = False
#                     try:
#                         # see if the course is connected to SRS
#                         print("\t", canvas_id, sis_id, short_name, account_id, status)
#                         update = False

#                         in_SRS = section_contains_srs(canvas, canvas_id)
#                         if in_SRS == False:
#                             print("\t not in SRS")
#                             notes += "\ not liked to SRS"
#                             update = False
#                         elif (
#                             int(canvas_id) in WH_EXCLUDE
#                             or account_id == SUB_ACCOUNT_EXCLUDE
#                         ):
#                             print("\t single site to ignore")
#                             notes += "\ in exclude list"
#                             update = False
#                         else:  # we know the course is connected to SRS and not a special ignore site
#                             update = True
#                     except:
#                         print("ERROR WITH COURSE: ", sis_id, canvas_id)
#                         outFile.write(
#                             "%s, %s, %s, %s, %s\n"
#                             % (sis_id, canvas_id, "err", "err", "err")
#                         )

#                     if update:
#                         print("\t\tshould update course")
#                         try:
#                             canvas_course.update(
#                                 course={"is_public_to_auth_users": True}
#                             )
#                             status = "public_to_auth_users"
#                         except:
#                             status = "ERROR"

#                         print(sis_id, canvas_id, status, published, notes)

#                     outFile.write(
#                         "%s, %s, %s, %s, %s\n"
#                         % (sis_id, canvas_id, status, published, notes)
#                     )

#                     # add this line to master file
#                     master = open(MASTER_FILE, "a")
#                     master.write(
#                         "%s, %s, %s, %s, %s\n"
#                         % (sis_id, canvas_id, status, published, notes)
#                     )
#                     master.close()
#         """

#                 # NEED TO SWAP ALL THE FALSES TO TRUES
#                 # Check if in Wharton
#                 if int(account_id) in WHARTON_ACCOUNTS:
#                     # check if linked to SRS -- use helper function
#                     in_SRS = linked_to_SRS(course_id)
#                     # STILL NEED TO MAKE CASE FOR EXECUTIVE MBA
#                     if in_SRS == True:
#                         update = True
#                 else:
#                     #CHeck if course's sections are associated with SRS (
#         """

#     dataFile.close()
#     outFile.close()


def course_shopping_main(test, force, verbose, new):
    def enable_course_shopping(course, canvas, verbose):
        index, canvas_course_id, course_id, canvas_account_id, status = course
        if not canvas_account_id.isnumeric():
            status = "invalid account id"
        elif not course_contains_srs(course_id):
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
                    course_number = int(course_id.split("-")[1])
                    subject = course_id.split("-")[0][4:]
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
                except Exception:
                    status = "failed to parse course code"
                if canvas_course:
                    if update:
                        try:
                            canvas_course.update(
                                course={"is_public_to_auth_users": True}
                            )
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

    reports, missing_file_message = find_input(INPUT_FILE_NAME, REPORTS)
    RESULT_PATH = RESULTS / f"{YEAR}_course_shopping_enabled_{TODAY}.csv"
    START = get_start_index(force, RESULT_PATH, RESULTS)
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
    SUB_ACCOUNTS = SAS_ACCOUNTS + SEAS_ACCOUNTS + NURS_ACCOUNTS + AN_ACCOUNTS
    echo(") Processing courses...")
    toggle_progress_bar(report, enable_course_shopping, CANVAS, verbose)
    process_result(RESULT_PATH)
    print_messages(TOTAL)


def print_messages(total):
    color("SUMMARY:", "yellow", True)
    echo(f"- Processed {color(total)} courses.")
    color("FINISHED", "yellow", True)


def process_result(result_path):
    result = read_csv(result_path, dtype=str)
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


# def disable_course_shopping(inputfile=MASTER_FILE, outputfile=DISABLE_OUTFILE):
#     canvas = get_canvas()
#     dataFile = open(inputfile, "r")
#     dataFile.readline()
#     outFile = open(outputfile, "w+")
#     outFile.write("sis_id, canvas_id, visibility_status, published, notes\n")
#     forWH = False
#     if "WH_" in inputfile:
#         forWH = True
#     for line in dataFile:
#         sis_id, canvas_id, visibility_status, published, notes = line.replace(
#             "\n", ""
#         ).split(",")

#         if (not forWH and visibility_status.strip() == "public_to_auth_users") or (
#             forWH and "NOT WHARTON" not in notes
#         ):
#             try:
#                 canvas_course = canvas.get_course(canvas_id)
#                 canvas_course.update(
#                     course={
#                         "is_public": False,
#                         "is_public_to_auth_users": False,
#                         "public_syllabus": False,
#                         "public_syllabus_to_auth": False,
#                     }
#                 )
#                 status = "disabled"
#             except Exception as ex:
#                 notes = "Exception: %s" % (ex)
#                 status = "Exception"

#             print(sis_id, canvas_id, status, published, notes)
#             outFile.write(
#                 "%s, %s, %s, %s, %s\n" % (sis_id, canvas_id, status, published, notes)
#             )


# load_master()
# print(canvas_id_in_master)

# WHARTON_enable_course_shopping(INFILE, WH_OUTFILE)
# print("WHARTON completed")

# enable_course_shopping(INFILE, OUTFILE)
# print("All completed")

# disable_course_shopping(MASTER_FILE, DISABLE_OUTFILE)
# disable_course_shopping(WH_OUTFILE, WH_DISABLE_OUTFILE)#!/usr/bin/env python3
