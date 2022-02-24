from pathlib import Path

from pandas import read_csv, concat
from pandas.core.frame import DataFrame
from requests import get

from penn_canvas.style import print_item

from .config import get_config_option
from .helpers import MAIN_ACCOUNT_ID, get_canvas, get_data_warehouse_cursor, color

emails = []
prod_key = get_config_option("canvas_keys", "canvas_prod_key")
open_key = get_config_option("canvas_keys", "open_canvas_prod_key")
prod_base_url = get_config_option("canvas_urls", "canvas_prod_url")
open_base_url = get_config_option("canvas_urls", "open_canvas_url")
prod_headers = {"Authorization": f"Bearer {prod_key}"}
open_headers = {"Authorization": f"Bearer {open_key}"}
INSTANCES = {
    "prod": (prod_base_url, prod_headers, MAIN_ACCOUNT_ID),
    "open": (open_base_url, open_headers, 1),
}

POSITIONS = {
    "AP": "Administrative/Professional",
    "EX": "Executive Pay (not included in the Data Warehouse)",
    "FA": "Faculty",
    "NC": "No category",
    "NE": "Non-employees (courtesy appointments, etc.)",
    "SS": "Support Staff",
    "ST": "Student",
    "TS": "Temporary Staff",
    "US": "Unionized Staff",
}


def find_users_by_email_main(emails_path, instance):
    emails_path = Path(emails_path)
    emails = read_csv(emails_path)["Email"].tolist()
    rows = list()
    total = len(emails)
    for index, email in enumerate(emails):
        cursor = get_data_warehouse_cursor()
        pennkey = next(iter(email.split("@")), "")
        cursor.execute(
            """
        SELECT
            person.first_name,
            person.last_name,
            job.personnel_class,
            person.email_address,
            person.currently_employed
        FROM dwadmin.employee_general_v person
        JOIN dwadmin.job_class job
        ON job.job_class = person.pri_acad_appt_job_class
        WHERE person.pennkey = :pennkey
        """,
            pennkey=pennkey,
        )
        for first_name, last_name, position, dw_email, currently_employed in cursor:
            try:
                dw_email = dw_email.strip().lower()
            except Exception:
                dw_email = ""
            message = (
                f"{first_name} {last_name}, {email}, {color(position)}, {dw_email} "
                f" currently employed: {currently_employed}"
            )
            print_item(index, total, message)
            rows.append(
                [
                    first_name.title(),
                    last_name.title(),
                    email,
                    POSITIONS.get(position, ""),
                    dw_email,
                    currently_employed,
                ]
            )
    results = DataFrame(
        rows,
        columns=[
            "Email",
            "First Name",
            "Last Name",
            "Position",
            "DW Email",
            "Currently Employed",
        ],
    )
    faculty = results[results["Position"] == "FA"]
    faculty = faculty.sort_values("Currently Employed", ascending=False)
    rest = results[results["Position"] != "FA"]
    rest = rest.sort_values("Currently Employed")
    results = concat([faculty, rest])
    results_path = emails_path.parent / f"{emails_path.stem}_DW.csv"
    results.to_csv(results_path, index=False)


# def find_users_by_email_main(emails_path, instance):
#     instances = (
#         [INSTANCES[instance]] if instance else [value for value in INSTANCES.values()]
#     )
#     emails_path = Path(emails_path)
#     emails = read_csv(emails_path)["email"].tolist()
#     rows = list()
#     for url, headers, account_id in instances:
#         canvas_instance = "prod" if url == prod_base_url else "open"
#         print(canvas_instance.upper())
#         canvas = get_canvas(canvas_instance)
#         for email in emails:
#             search_url = f"{url}api/v1/accounts/{account_id}/users?search_term={email}"
#             response = get(search_url, headers=headers).json()
#             if response:
#                 response = response[0]
#                 name = response["name"]
#                 user = canvas.get_user(response["id"])
#                 enrollments = {enrollment.type for enrollment in user.get_enrollments()}
#                 roles = ", ".join(enrollments)
#                 rows.append([email, name, roles])
#                 print(email, name, roles)
#             else:
#                 print(email, response)
#                 rows.append([email, "not found", "not found"])
#     results = DataFrame(rows, columns=["Email", "Name", "Roles"])
#     results_path = emails_path.parent / f"{emails_path.stem}_results.csv"
#     results.to_csv(results_path)
