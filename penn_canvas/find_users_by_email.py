from pathlib import Path

from pandas import concat, read_csv
from pandas.core.frame import DataFrame

from .api import get_data_warehouse_cursor
from .style import color, print_item

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
    "": "Student",
}


def find_users_by_email_main(emails_path):
    emails_path = Path(emails_path)
    try:
        emails = read_csv(emails_path)["Email"].tolist()
    except Exception:
        emails = read_csv(emails_path)["email"].tolist()
    rows = list()
    total = len(emails)
    for index, email in enumerate(emails):
        first = last = pos = dwemail = employed = last_degree = pennkey = ""
        last_degrees = list()
        email_search = f"%{email}%"
        cursor = get_data_warehouse_cursor()
        cursor.execute(
            """
            SELECT
                person.first_name,
                person.last_name,
                person.email_address,
                degree.last_degree_term,
                person.pennkey
            FROM dwadmin.person_all_v person
            JOIN dwadmin.degree_pursual_all_v degree
            ON degree.penn_id = person.penn_id
            WHERE person.email_address LIKE :email
            """,
            email=email_search,
        )
        for first_name, last_name, dw_email, deg, pkey in cursor:
            try:
                dw_email = dw_email.strip().lower()
            except Exception:
                dw_email = ""
            first = first_name
            last = last_name
            dwemail = dw_email
            pennkey = pkey
            last_degrees.append(deg)
        if not pennkey:
            pennkey = next(iter(email.split("@")), "")
            cursor.execute(
                """
                SELECT
                    person.first_name,
                    person.last_name,
                    person.email_address,
                    degree.last_degree_term
                FROM dwadmin.person_all_v person
                JOIN dwadmin.degree_pursual_all_v degree
                ON degree.penn_id = person.penn_id
                WHERE person.pennkey = :pennkey
                """,
                pennkey=pennkey,
            )
            for first_name, last_name, dw_email, deg in cursor:
                try:
                    dw_email = dw_email.strip().lower()
                except Exception:
                    dw_email = ""
                first = first_name
                last = last_name
                dwemail = dw_email
                last_degrees.append(deg)
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
        for first_name, last_name, position, dw_email, emp in cursor:
            try:
                dw_email = dw_email.strip().lower()
            except Exception:
                dw_email = ""
            first = first_name
            last = last_name
            pos = position
            dwemail = dw_email
            employed = emp
        years = [
            int("".join(character for character in degree if character.isnumeric()))
            for degree in last_degrees
            if degree
        ]
        last_degree = sorted(years)[-1] if years else ""
        first = first.strip().title()
        last = last.strip().title()
        pos = POSITIONS.get(pos, "")
        message = (
            f"{first} {last}, {email}, {color(pos)}, {dwemail}  employed: {employed},"
            f" last_degree: {color(last_degree, 'blue', use_comma=False)}"
        )
        print_item(index, total, message)
        rows.append(
            [
                first,
                last,
                email,
                pos,
                dwemail,
                employed,
                last_degree,
            ]
        )
    results = DataFrame(
        rows,
        columns=[
            "First Name",
            "Last Name",
            "Email",
            "Position",
            "DW Email",
            "Currently Employed",
            "Last Degree Term",
        ],
    )
    faculty = results[results["Position"] == "Faculty"]
    faculty = faculty.sort_values("Currently Employed", ascending=False)
    rest = results[results["Position"] != "Faculty"]
    rest = rest.sort_values("Currently Employed")
    results = concat([faculty, rest])
    results_path = emails_path.parent / f"{emails_path.stem}_DW.csv"
    results.to_csv(results_path, index=False)
