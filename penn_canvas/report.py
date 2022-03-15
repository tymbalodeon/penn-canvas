from pathlib import Path
from time import sleep

from canvasapi.account import Account
from requests import get
from typer import echo

from penn_canvas.helpers import (
    CURRENT_YEAR_AND_TERM,
    MAIN_ACCOUNT_ID,
    REPORTS,
    get_account,
)


def create_report(
    report_type: str,
    parameters: dict,
    base_path=REPORTS,
    account: int | Account = MAIN_ACCOUNT_ID,
) -> Path | None:
    account = get_account(account)
    report_types = [report.report for report in account.get_reports()]
    if report_type not in report_types:
        echo(f'Unkown report type: "{report_type}"')
        echo("Available report types are:")
        for report_type in report_types:
            echo(f"\t{report_type}")
    report = account.create_report(report_type, parameters=parameters)
    while report.status in {"created", "running"}:
        echo(f"{report_type} {report.status}...")
        sleep(5)
        report = account.get_report(report_type, report.id)
    if report.status == "error":
        try:
            echo(f"- ERROR: {report.last_run['paramters']['extra_text']}")
        except Exception:
            echo("- ERROR: The report failed to generate a file. Please try again.")
        report.delete_report()
    else:
        try:
            filename = report.attachment["filename"]
            url = report.attachment["url"]
            report_path = base_path / filename
            with open(report_path, "wb") as stream:
                response = get(url, stream=True)
                for chunk in response.iter_content(chunk_size=128):
                    stream.write(chunk)
            return report_path
        except Exception as error:
            echo(f"- ERROR: {error}")
            report.delete_report()


def create_provisioning_report(
    courses=True,
    users=True,
    enrollment_term=CURRENT_YEAR_AND_TERM,
    base_path=REPORTS,
    account: int | Account = MAIN_ACCOUNT_ID,
):
    account = get_account(account)
    parameters = dict()
    if courses:
        parameters["courses"] = courses
    if users:
        parameters["users"] = users
    if enrollment_term:
        enrollment_terms = [
            {"name": enrollment_term.name, "id": enrollment_term.id}
            for enrollment_term in account.get_enrollment_terms()
        ]
        enrollment_term_ids = dict()
        for enrollment_term in enrollment_terms:
            enrollment_term_ids[enrollment_term["name"]] = enrollment_term["id"]
        try:
            enrollment_term_id = enrollment_term_ids.get(enrollment_term)
            parameters["enrollment_term_id"] = enrollment_term_id
        except Exception:
            echo("- ERROR: Enrollment term not found: {enrollment_term}")
            echo("Available enrollment terms are:")
            for enrollment_term in enrollment_terms:
                echo(f"\t{enrollment_term['name']}")
    create_report("provisioning_csv", parameters, base_path, account)
