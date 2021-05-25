from canvas_shared import *

# baowei@upenn.edu
# 1/13/2021:
#   1. added the definition of input, result, remedy and errors files
# 1/5/2021:
#   1. changed to call get_canvas() to create the Canvas object

TERM = "2021A"
ENROLLED = "data/" + TERM + "_Enrolled.csv"
UNCONFIRMED = "data/" + TERM + "_Unconfirmed.csv"
REMEDY = "data/" + TERM + "_Remedy.csv"
ERRORS = "data/Errors_Emails.csv"

TESTING = False

"""
    ~~~~ THE STEPS IN RUNNING THE UNCONFIRMED EMAILS ~~~~
0. Run Provisioning Report ___ and delete all columns but the canvas_user_id, save as ENROLLED
1. find_unconfirmed_emails(), save result as UNCONFIRMED
2. unconfirmed_email_check_school(), save result into REMEDY
3. Create a new file from the output of 2 and filter to the schools we can remediate
4. Run verify_email_list(), save errors into ERRORS
5. Check errors from output
6. Check the schools we can't remediate (from 3.) by hand to confirm we cant remediate. send list to the schools
"""


def find_unconfirmed_emails(inputfile=ENROLLED, outputfile=UNCONFIRMED):
    canvas = get_canvas(TESTING)

    dataFile = open(inputfile, "r")
    dataFile.readline()  # THIS SKIPS THE FIRST LINE

    # first, identify the unique values
    ids = []

    for line in dataFile:
        canvas_user_id = line.replace("\n", "")

        if canvas_user_id not in ids:
            ids.append(canvas_user_id)

    dataFile.close()

    total = len(ids)

    outFile = open(outputfile, "a")
    outFile.write("%s,%s\n" % ("canvas_user_id", "email_status"))

    count = 0
    for canvas_user_id in ids:
        count += 1
        if count % 25 == 0:
            print("%s / %s complete" % (count, total))

        user = canvas.get_user(canvas_user_id)

        email_status = "NONE"
        communication_channels = user.get_communication_channels()

        for c in communication_channels:  # only need the first one
            email_status = c.workflow_state
            break

        if email_status == "NONE" or email_status == "unconfirmed":
            outFile.write("%s,%s\n" % (canvas_user_id, email_status))

    outFile.close()


def unconfirmed_email_check_school(inputfile=UNCONFIRMED, outputfile=REMEDY):
    # given the unconfirmed emails list, checks in the original file if they have multiple enrollments
    # if they have multiple enrollments, check if any all of the enrollments are in schools we do not support
    # if this is the case, write this user down in a separate file
    # otherwise, write them in a file that will then be remediated.

    canvas = get_canvas(TESTING)

    SUB_ACCOUNTS = []
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
    for a in ACCOUNTS:
        SUB_ACCOUNTS += find_accounts_subaccounts(canvas, int(a))
    print(SUB_ACCOUNTS)

    dataFile = open(inputfile, "r")
    dataFile.readline()  # THIS SKIPS THE FIRST LINE

    outFile = open(outputfile, "w+")
    outFile.write("%s,%s,%s\n" % ("canvas_user_id", "email_status", "can_remediate"))

    for line in dataFile:
        canvas_user_id, email_status = line.replace("\n", "").split(",")
        user = canvas.get_user(canvas_user_id)
        user_enrollments = user.get_courses()  # should we limit by term?
        can_fix = False
        for course in user_enrollments:
            try:
                if str(course.account_id) in SUB_ACCOUNTS:
                    can_fix = True
                    break  # will this stop from iterating through the rest of the list?
            except Exception as ex:
                print("\t error with user %s: %s" % (canvas_user_id, ex))
            # check if the account id is in the list of sub accounts
            # if it is not_supported_school = False

        # we can remediate this user's account if the final column is False!
        outFile.write("%s,%s,%s\n" % (canvas_user_id, email_status, can_fix))

    dataFile.close()
    outFile.close()


# red the enrollment file and verify the emails of all
def verify_email_list(inputfile=ENROLLED, outputfile=ERRORS):
    dataFile = open(inputfile, "r")
    dataFile.readline()  # THIS SKIPS THE FIRST LINE

    # first, identify the unique values
    ids = []

    print("Loading the canvas_user_id from %s" % (inputfile))

    for line in dataFile:
        canvas_user_id = line.replace("\n", "")

        if canvas_user_id not in ids:
            ids.append(canvas_user_id)

    dataFile.close()

    total = len(ids)

    print("Loading the canvas_user_id already processed from %s" % (outputfile))

    # load the outputfile to check if there's already records
    outFile = open(outputfile, "r")
    already_processed_ids = []

    for line in outFile:
        canvas_user_id, email_status = line.replace("\n", "").split(",")
        already_processed_ids.append(canvas_user_id)

    outFile.close()

    # append to the output
    outFile = open(outputfile, "a")
    # outFile.write("%s,%s\n" % ('canvas_user_id', 'email_status'))

    counter = 0
    for canvas_user_id in ids:
        counter += 1

        if counter % 25 == 0:
            print("%s/%s done" % (counter, total))

        try:
            if canvas_user_id not in already_processed_ids:
                is_verified = verify_first_email(int(canvas_user_id))

                if is_verified:
                    outFile.write("%s, %s\n" % (canvas_user_id, "confirmed"))
                else:
                    outFile.write("%s, %s\n" % (canvas_user_id, "needs check"))
        except Exception as ex:
            outFile.write("%s, error: %s\n" % (canvas_user_id, ex))

    outFile.close()


def check_dummy_email_deleted(user_id):
    DUMMY = "test@gmail.com"
    canvas = get_canvas(TESTING)

    user = canvas.get_user(user_id)
    communication_channels = user.get_communication_channels()
    found = False
    for comm_channel in communication_channels:
        if comm_channel.address == DUMMY:
            found = True
            if comm_channel.workflow_state == "deleted":
                return True
            else:
                return False  # ahh it is stll active!

    if found:
        print("\t Dummy email wasnt deleted for user %s" % (user_id))
        return False
    else:
        return True


def check_verified_email(user_id, address):
    canvas = get_canvas(TESTING)
    user = canvas.get_user(user_id)
    communication_channels = user.get_communication_channels()

    for comm_channel in communication_channels:
        if comm_channel.address == address:
            # return True if workflow
            if comm_channel.workflow_state == "active":
                return True
            else:
                return False
    print("\t Couldn't find former email %s for user %s" % (address, user_id))
    return False


def verify_first_email(user_id):
    canvas = get_canvas(TESTING)
    user = canvas.get_user(user_id)
    communication_channels = user.get_communication_channels()

    for comm_channel in communication_channels:
        # verify the first one by re-creating it but auto-verify the new one
        if comm_channel.type == "email":
            dummy_channel = user.create_communication_channel(
                communication_channel={"address": "test@gmail.com", "type": "email"},
                skip_confirmation=True,
            )
            # print(dummy_channel.to_json())
            email = comm_channel.address
            # print(comm_channel.to_json())
            comm_channel.delete()
            new_channel = user.create_communication_channel(
                communication_channel={"address": email, "type": "email"},
                skip_confirmation=True,
            )
            dummy_channel.delete()

            # check that email is verified
            email_is_verified = check_verified_email(user_id, email)
            if not email_is_verified:
                print("\t email not verified for user %s" % user_id)

            # check that dummy is deleted
            dummy_is_deleted = check_dummy_email_deleted(user_id)
            if not dummy_is_deleted:
                print("\t dummy not deleted for user %s" % user_id)

            if dummy_is_deleted and email_is_verified:
                return True
            else:
                return False
        break

    return False


# find_unconfirmed_emails()
# unconfirmed_email_check_school()
verify_email_list()
