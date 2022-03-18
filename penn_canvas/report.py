from os import remove
from pathlib import Path
from shutil import rmtree
from time import sleep
from zipfile import ZipFile

from canvasapi.account import Account
from requests import get
from typer import Exit, echo

from .api import (
    MAIN_ACCOUNT_ID,
    Instance,
    collect,
    format_instance_name,
    get_account,
    validate_instance_name,
)
from .helpers import CURRENT_YEAR_AND_TERM, REPORTS
from .style import color


def validate_report_type(
    report_type, by_filename=False, account: int | Account = MAIN_ACCOUNT_ID
):
    if by_filename:
        report_types = {"provisioning", "courses", "users", "storage", "course storage"}
    else:
        account = get_account(account)
        report_types = {report.report for report in account.get_reports()}
    if report_type not in report_types:
        echo(f'ERROR: Unkown report type "{report_type}"')
        echo("\nAvailable report types are:")
        for report_type in report_types:
            echo(f'\t"{report_type}"')
        raise Exit()


def get_enrollment_term_id(
    term_name, by_year=True, account: int | Account = MAIN_ACCOUNT_ID
):
    def raise_exception(enrollment_terms):
        echo(f"- ERROR: Enrollment term not found: {term_name}")
        echo("- Available enrollment terms are:")
        for enrollment_term in enrollment_terms:
            echo(f"\t{enrollment_term}")
        raise Exit()

    account = get_account(account)
    if by_year:
        try:
            enrollment_terms = collect(account.get_enrollment_terms())
            return next(term.id for term in enrollment_terms if term_name in term.name)
        except Exception:
            enrollment_terms = [term.name for term in account.get_enrollment_terms()]
            raise_exception(enrollment_terms)
    else:
        enrollment_terms = [
            {"name": enrollment_term.name, "id": enrollment_term.id}
            for enrollment_term in account.get_enrollment_terms()
        ]
        enrollment_term_ids = dict()
        for term in enrollment_terms:
            enrollment_term_ids[term["name"]] = term["id"]
        try:
            return enrollment_term_ids.get(term_name)
        except Exception:
            enrollment_terms = [term["name"] for term in account.get_enrollment_terms()]
            raise_exception(enrollment_terms)


def create_report(
    report_type: str,
    parameters=dict(),
    base_path=REPORTS,
    filename_replacement="",
    account: int | Account = MAIN_ACCOUNT_ID,
    instance=Instance.PRODUCTION,
    verbose=False,
) -> Path:
    instance = validate_instance_name(instance)
    validate_report_type(report_type, account=account)
    account = get_account(account, instance=instance)
    if parameters:
        report = account.create_report(report_type, parameters=parameters)
    else:
        report = account.create_report(report_type)
    status = report.status
    echo(f') Generating "{report_type}"...')
    while status in {"created", "running"}:
        echo("\t* Running...")
        sleep(5)
        report = account.get_report(report_type, report.id)
        status = report.status
    if status == "error":
        if verbose:
            try:
                echo(f"ERROR: {report.last_run['paramters']['extra_text']}")
            except Exception:
                echo("ERROR: The report failed to generate a file. Please try again.")
        report.delete_report()
        raise Exit()
    else:
        if verbose:
            echo("COMPLETE")
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
                report_path = report_path.replace(
                    base_path / f"{filename_replacement}{report_path.suffix}"
                )
            return report_path
        except Exception as error:
            if verbose:
                echo(f"ERROR: {error}")
            report.delete_report()
            raise Exit()


def create_provisioning_report(
    courses=False,
    users=False,
    term_name=CURRENT_YEAR_AND_TERM,
    base_path=REPORTS,
    account: int | Account = MAIN_ACCOUNT_ID,
    instance=Instance.PRODUCTION,
    verbose=False,
) -> Path:
    instance = validate_instance_name(instance)
    instance_display = format_instance_name(instance)
    filename_term = ""
    parameters = dict()
    if term_name:
        parameters["enrollment_term_id"] = get_enrollment_term_id(term_name)
        filename_term = term_name
    filename_term = f"_{filename_term}" if filename_term else ""
    if courses != users:
        filename_replacement = (
            f"courses{filename_term}" if courses else f"users{filename_term}"
        )
    else:
        courses = users = True
        filename_replacement = filename_term
    if courses:
        parameters["courses"] = courses
    if users:
        parameters["users"] = users
    return create_report(
        "provisioning_csv",
        parameters,
        base_path,
        f"{filename_replacement}{instance_display}",
        account,
        instance,
        verbose,
    )


def create_course_storage_report(
    term_name=CURRENT_YEAR_AND_TERM,
    base_path=REPORTS,
    account: int | Account = MAIN_ACCOUNT_ID,
    instance=Instance.PRODUCTION,
    verbose=False,
) -> Path:
    instance = validate_instance_name(instance)
    instance_display = format_instance_name(instance)
    filename_term = ""
    parameters = dict()
    if term_name:
        parameters["enrollment_term_id"] = get_enrollment_term_id(term_name)
        filename_term = term_name
    filename_term = f"_{filename_term}" if filename_term else ""
    filename_replacement = f"course_storage{filename_term}{instance_display}"
    return create_report(
        "course_storage_csv",
        parameters,
        base_path,
        filename_replacement,
        account,
        instance,
        verbose,
    )


def get_report(
    report_type: str,
    term_name=CURRENT_YEAR_AND_TERM,
    force=False,
    instance=Instance.PRODUCTION,
    verbose=False,
) -> Path:
    instance = validate_instance_name(instance)
    validate_report_type(report_type, by_filename=True)
    term_display = f"_{term_name}" if term_name else term_name
    instance_display = format_instance_name(instance)
    if report_type == "storage":
        report_type = "course_storage"
    report_path = REPORTS / f"{report_type}{term_display}{instance_display}.csv"
    if force or not report_path.is_file():
        if report_type == "provisioning":
            report_path = create_provisioning_report(
                courses=True,
                users=True,
                term_name=term_name,
                instance=instance,
                verbose=verbose,
            )
        elif report_type == "courses":
            report_path = create_provisioning_report(
                courses=True, term_name=term_name, instance=instance, verbose=verbose
            )
        elif report_type == "users":
            report_path = create_provisioning_report(
                users=True, term_name=term_name, instance=instance, verbose=verbose
            )
        elif "storage" in report_type:
            report_path = create_course_storage_report(
                term_name=term_name, instance=instance, verbose=verbose
            )
    if verbose:
        echo(f'REPORT: {color(report_path, "blue")}')
    return report_path


def report_main(report_type, term_name, force, instance, verbose):
    get_report(report_type, term_name, force, instance, verbose)
