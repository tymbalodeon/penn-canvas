"""
    ~~~~ THE STEPS IN RUNNING THE UNCONFIRMED EMAILS ~~~~
0. Run Provisioning Report (with "users.csv" checked) and delete all columns but
    the canvas_user_id, save as ENROLLED
1. find_unconfirmed_emails(), save result as UNCONFIRMED
2. unconfirmed_email_check_school(), save result into REMEDY
3. Create a new file from the output of 2 and filter to the schools we can
    remediate
4. Run verify_email_list(), save errors into ERRORS
5. Check errors from output
6. Check the schools we can't remediate (from 3.) by hand to confirm we cant
    remediate. send list to the schools
"""

from pathlib import Path

import pandas
import typer

from .canvas_shared import find_sub_accounts, get_canvas

# TERM = "2021A"
# ENROLLED = "data/" + TERM + "_Enrolled.csv"
# UNCONFIRMED = "data/" + TERM + "_Unconfirmed.csv"
# REMEDY = "data/" + TERM + "_Remedy.csv"
# ERRORS = "data/Errors_Emails.csv"

EMAIL = Path.home() / "penn-canvas/email"
REPORTS = EMAIL / "reports"
ACCOUNTS = [
    "99243",
    "99237",
    "128877",
    "99241",
    "99244",
    "99238",
    "99239",
    "131428",
    "99240",
    "132153",
    "82192",
]


def find_users_report():
    typer.echo(") Finding users report...")

    if not REPORTS.exists():
        Path.mkdir(REPORTS, parents=True)
        typer.echo(
            "\tCanvas email reports directory not found. Creating one for you at:"
            f" {REPORTS}\n\tPlease add a Canvas Users Provisioning report to this"
            " directory and then run this script again.\n\t(If you need instructions"
            " for generating a Canvas Provisioning report, run this command with the"
            " '--help' flag.)"
        )
        raise typer.Exit(1)
    else:
        USERS_REPORT = REPORTS / "users.csv"

        if not USERS_REPORT.exists():
            typer.echo(
                "\tA Canvas Users Provisioning report  was not found.\n\tPlease add a"
                " Canvas Users Provisioning report to this directory and then run this"
                " script again.\n\t(If you need instructions for generating a Canvas"
                " Provisioning report, run this command with the '--help' flag.)"
            )
            raise typer.Exit(1)
        else:
            return USERS_REPORT


def cleanup_report(report):
    typer.echo(") Removing unused columns...")
    data = pandas.read_csv(report)
    data = data[["canvas_user_id"]]
    data.drop_duplicates(inplace=True)
    data = data.astype("string", copy=False)
    return data


def find_unconfirmed_emails(data, canvas, verbose):
    typer.echo(") Finding unconfirmed emails...")
    USERS = data.itertuples(index=False)
    UNCONFIRMED = list()

    for user in USERS:
        user_id = user.canvas_user_id
        user = canvas.get_user(user_id)
        communication_channels = user.get_communication_channels()

        try:
            email_status = communication_channels[0].workflow_state
        except:
            if verbose:
                error = typer.style("Error occured for user:", fg=typer.colors.YELLOW)
                typer.echo(f"- {error} {user_id}")
            UNCONFIRMED.append([user_id, "ERROR"])

        if email_status == "unconfirmed":
            if verbose:
                status = typer.style(f"{email_status}", fg=typer.colors.YELLOW)
                typer.echo(f"- Email status is {status} for {user_id}")
            UNCONFIRMED.append([user_id, email_status])
        elif verbose:
            status = typer.style(f"{email_status}", fg=typer.colors.GREEN)
            typer.echo(f"- Email status is {status} for user: {user_id}")

    return pandas.DataFrame(UNCONFIRMED, columns=["canvas user id", "email status"])


def check_school(data, canvas):
    typer.echo(") Checking enrollments for users with unconfirmed emails...")
    SUB_ACCOUNTS = []

    for account in ACCOUNTS:
        SUB_ACCOUNTS += find_sub_accounts(canvas, account)

    # outFile.write("%s,%s,%s\n" % ("canvas_user_id", "email_status", "can_remediate"))

    ROWS = data.itertuples(index=False)

    for row in ROWS:
        canvas_user_id, email_status = row
        user = canvas.get_user(canvas_user_id)
        user_enrollments = user.get_courses()
        account_ids = map(lambda x: x.account_id, user_enrollments)
        # can_fix = False

        for account_id in account_ids:
            try:
                if str(account_id) in SUB_ACCOUNTS:
                    print(account_id)
                    # can_fix = True
                    print("CAN FIX")
                    break
            except Exception as error:
                print("- Error encountered for user: {canvas_user_id}")
                print("\t ERROR: {error}")
            # check if the account id is in the list of sub accounts
            # if it is not_supported_school = False

        # we can remediate this user's account if the final column is False!
        # outFile.write("%s,%s,%s\n" % (canvas_user_id, email_status, can_fix))


# # red the enrollment file and verify the emails of all
# def verify_email_list(inputfile=ENROLLED, outputfile=ERRORS):
#     dataFile = open(inputfile, "r")
#     dataFile.readline()  # THIS SKIPS THE FIRST LINE

#     # first, identify the unique values
#     ids = []

#     print("Loading the canvas_user_id from %s" % (inputfile))

#     for line in dataFile:
#         canvas_user_id = line.replace("\n", "")

#         if canvas_user_id not in ids:
#             ids.append(canvas_user_id)

#     dataFile.close()

#     total = len(ids)

#     print("Loading the canvas_user_id already processed from %s" % (outputfile))

#     # load the outputfile to check if there's already records
#     outFile = open(outputfile, "r")
#     already_processed_ids = []

#     for line in outFile:
#         canvas_user_id, email_status = line.replace("\n", "").split(",")
#         already_processed_ids.append(canvas_user_id)

#     outFile.close()

#     # append to the output
#     outFile = open(outputfile, "a")
#     # outFile.write("%s,%s\n" % ('canvas_user_id', 'email_status'))

#     counter = 0
#     for canvas_user_id in ids:
#         counter += 1

#         if counter % 25 == 0:
#             print("%s/%s done" % (counter, total))

#         try:
#             if canvas_user_id not in already_processed_ids:
#                 is_verified = verify_first_email(int(canvas_user_id))

#                 if is_verified:
#                     outFile.write("%s, %s\n" % (canvas_user_id, "confirmed"))
#                 else:
#                     outFile.write("%s, %s\n" % (canvas_user_id, "needs check"))
#         except Exception as ex:
#             outFile.write("%s, error: %s\n" % (canvas_user_id, ex))

#     outFile.close()


# def check_dummy_email_deleted(user_id):
#     DUMMY = "test@gmail.com"
#     canvas = get_canvas(TESTING)

#     user = canvas.get_user(user_id)
#     communication_channels = user.get_communication_channels()
#     found = False
#     for comm_channel in communication_channels:
#         if comm_channel.address == DUMMY:
#             found = True
#             if comm_channel.workflow_state == "deleted":
#                 return True
#             else:
#                 return False  # ahh it is stll active!

#     if found:
#         print("\t Dummy email wasnt deleted for user %s" % (user_id))
#         return False
#     else:
#         return True


# def check_verified_email(user_id, address):
#     canvas = get_canvas(TESTING)
#     user = canvas.get_user(user_id)
#     communication_channels = user.get_communication_channels()

#     for comm_channel in communication_channels:
#         if comm_channel.address == address:
#             # return True if workflow
#             if comm_channel.workflow_state == "active":
#                 return True
#             else:
#                 return False
#     print("\t Couldn't find former email %s for user %s" % (address, user_id))
#     return False


# def verify_first_email(user_id):
#     canvas = get_canvas(TESTING)
#     user = canvas.get_user(user_id)
#     communication_channels = user.get_communication_channels()

#     for comm_channel in communication_channels:
#         # verify the first one by re-creating it but auto-verify the new one
#         if comm_channel.type == "email":
#             dummy_channel = user.create_communication_channel(
#                 communication_channel={"address": "test@gmail.com", "type": "email"},
#                 skip_confirmation=True,
#             )
#             # print(dummy_channel.to_json())
#             email = comm_channel.address
#             # print(comm_channel.to_json())
#             comm_channel.delete()
#             user.create_communication_channel(
#                 communication_channel={"address": email, "type": "email"},
#                 skip_confirmation=True,
#             )
#             dummy_channel.delete()

#             # check that email is verified
#             email_is_verified = check_verified_email(user_id, email)
#             if not email_is_verified:
#                 print("\t email not verified for user %s" % user_id)

#             # check that dummy is deleted
#             dummy_is_deleted = check_dummy_email_deleted(user_id)
#             if not dummy_is_deleted:
#                 print("\t dummy not deleted for user %s" % user_id)

#             if dummy_is_deleted and email_is_verified:
#                 return True
#             else:
#                 return False
#         break

#     return False


# find_unconfirmed_emails()
# unconfirmed_email_check_school()
# verify_email_list()


def email_main(test, verbose):
    report = find_users_report()
    report = cleanup_report(report)
    CANVAS = get_canvas(test)
    UNCONFIRMED = find_unconfirmed_emails(report, CANVAS, verbose)
    check_school(UNCONFIRMED, CANVAS)
    typer.echo("FINISHED")
