from os import remove
from pathlib import Path
from shutil import rmtree
from time import sleep
from zipfile import ZipFile

from canvasapi.account import Account
from requests import get
from typer import Exit, echo

from penn_canvas.helpers import CURRENT_TERM_NAME, MAIN_ACCOUNT_ID, REPORTS, get_account


def validate_report_type(
    report_type, by_filename=False, account: int | Account = MAIN_ACCOUNT_ID
):
    if by_filename:
        report_types = {"courses", "users"}
    else:
        account = get_account(account)
        report_types = {report.report for report in account.get_reports()}
    if report_type not in report_types:
        echo(f'ERROR: Unkown report type "{report_type}"')
        echo("\nAvailable report types are:")
        for report_type in report_types:
            echo(f'\t"{report_type}"')
        raise Exit()


def create_report(
    report_type: str,
    parameters=dict(),
    base_path=REPORTS,
    filename_replacement="",
    account: int | Account = MAIN_ACCOUNT_ID,
) -> Path | None:
    account = get_account(account)
    validate_report_type(report_type, account=account)
    if not parameters:
        echo("- ERROR: Must include parameters.")
        raise Exit()
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
                paths = export_path.glob("*.csv")
                for path in paths:
                    path.replace(
                        base_path / f"{path.stem}{filename_replacement}{path.suffix}"
                    )
                remove(report_path)
                rmtree(export_path)
            elif filename_replacement:
                report_path = report_path.replace(base_path / f"{filename_replacement}")
            return report_path
        except Exception as error:
            echo(f"- ERROR: {error}")
            report.delete_report()
            return None


def create_provisioning_report(
    courses=False,
    users=False,
    term_name=CURRENT_TERM_NAME,
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
            filename_term = term_name
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
    else:
        filename_replacement = filename_term
    create_report(
        "provisioning_csv", parameters, base_path, filename_replacement, account
    )


def report_main(report_type: str, term_name="", force=False, verbose=False):
    validate_report_type(report_type, by_filename=True)
    term_display = f"_{term_name}" if term_name else term_name
    report_path = REPORTS / f"{report_type}{term_display}.csv"
    report = None
    if force or not report_path.is_file():
        if report_type == "courses":
            report = create_provisioning_report(courses=True, term_name=term_name)
        if report_type == "users":
            report = create_provisioning_report(users=True, term_name=term_name)
    else:
        report = report_path
    if verbose:
        print(report)
    return report
