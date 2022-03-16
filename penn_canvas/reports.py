from os import remove
from pathlib import Path
from time import sleep
from zipfile import ZipFile

from canvasapi.account import Account
from requests import get
from typer import Exit, echo

from penn_canvas.helpers import (
    CURRENT_TERM_DISPLAY,
    CURRENT_YEAR,
    CURRENT_YEAR_AND_TERM,
    MAIN_ACCOUNT_ID,
    REPORTS,
    TODAY_AS_Y_M_D,
    create_directory,
    get_account,
)


def create_report(
    report_type: str,
    parameters: dict,
    base_path=REPORTS,
    filename_replacement="",
    account: int | Account = MAIN_ACCOUNT_ID,
) -> Path | None:
    account = get_account(account)
    report_types = [report.report for report in account.get_reports()]
    if report_type not in report_types:
        echo(f'- ERROR: Unkown report type "{report_type}"')
        echo("-Available report types are:")
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
        return None
    else:
        try:
            filename: str = report.attachment["filename"]
            url = report.attachment["url"]
            report_path = base_path / filename
            with open(report_path, "wb") as stream:
                response = get(url, stream=True)
                for chunk in response.iter_content(chunk_size=128):
                    stream.write(chunk)
            if report.attachment["mime_class"] == "zip":
                export_path = base_path / filename.replace(".zip", "")
                with ZipFile(report_path) as unzipper:
                    unzipper.extractall(export_path)
                remove(report_path)
            elif filename_replacement:
                report_path = report_path.replace(base_path / f"{filename_replacement}")
            return report_path
        except Exception as error:
            echo(f"- ERROR: {error}")
            report.delete_report()
            return None


def create_provisioning_report(
    courses=True,
    users=True,
    term_name=f"{CURRENT_YEAR_AND_TERM} (Banner {CURRENT_TERM_DISPLAY} {CURRENT_YEAR})",
    base_path=REPORTS,
    account: int | Account = MAIN_ACCOUNT_ID,
):
    account = get_account(account)
    filename_term = filename_replacement = ""
    parameters = dict()
    if term_name:
        enrollment_terms = [
            {"name": enrollment_term.name, "id": enrollment_term.id}
            for enrollment_term in account.get_enrollment_terms()
        ]
        enrollment_term_ids = dict()
        for term in enrollment_terms:
            enrollment_term_ids[term["name"]] = term["id"]
        try:
            enrollment_term_id = enrollment_term_ids.get(term_name)
            parameters["enrollment_term_id"] = enrollment_term_id
            filename_term = str(enrollment_term_id)
        except Exception:
            echo(f"- ERROR: Enrollment term not found: {term_name}")
            echo("- Available enrollment terms are:")
            for enrollment_term in enrollment_terms:
                echo(f"\t{enrollment_term['name']}")
            raise Exit()
    if courses:
        parameters["courses"] = courses
    if users:
        parameters["users"] = users
    filename_term = f"_{filename_term}" if filename_term else ""
    if courses != users:
        filename_replacement = (
            "courses{filename_term}" if courses else "users{filename_term}"
        )
    elif courses is False and users is False:
        filename_replacement = f"provisioning{filename_term}"
    base_path = create_directory(base_path / TODAY_AS_Y_M_D)
    create_report(
        "provisioning_csv", parameters, base_path, filename_replacement, account
    )
