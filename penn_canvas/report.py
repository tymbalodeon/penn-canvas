from dataclasses import dataclass
from enum import Enum
from functools import cached_property
from os import remove
from pathlib import Path
from shutil import rmtree
from time import sleep
from typing import Any, Iterable, Literal, Optional
from zipfile import ZipFile

from canvasapi.account import Account, AccountReport
from loguru import logger
from pandas.io.parsers.readers import read_csv
from typer import Exit, echo, style

from .api import (
    Instance,
    format_instance_name,
    get_account,
    get_enrollment_term_id,
    get_main_account_id,
    validate_instance_name,
)
from .helpers import (
    CURRENT_YEAR_AND_TERM,
    REPORTS,
    create_directory,
    download_file,
    get_reports_directory,
    make_list,
    switch_logger_file,
)
from .style import color, pluralize

LOGS = create_directory(get_reports_directory() / "Logs")


class ReportType(Enum):
    COURSES = "courses"
    USERS = "users"
    STORAGE = "storage"
    PROVISIONING = "provisioning"
    PUBLIC_COURSES = "public_courses"


def get_report_type_string(report_type: ReportType | str) -> str:
    if isinstance(report_type, ReportType):
        return report_type.value
    else:
        return report_type


def get_available_cli_report_type_names() -> list[str]:
    report_types: list[ReportType | str] = [report_type for report_type in ReportType]
    report_types = report_types + ["weekly"]
    return [
        f"{get_report_type_string(report_type)} "
        f"({get_canvas_report_type_name(report_type)})"
        for report_type in report_types
    ]


def get_available_cli_report_types() -> list[str]:
    report_types = [report_type.value for report_type in ReportType]
    return report_types + ["weekly"]


def get_available_canvas_report_types(
    account_id: int | Account = get_main_account_id(),
    instance_name: str | Instance = Instance.PRODUCTION,
) -> set[str]:
    instance = validate_instance_name(instance_name)
    if not account_id:
        account_id = get_main_account_id(instance)
    account = get_account(account_id, instance=instance)
    return {report.report for report in account.get_reports()}


def print_report_type(report_type: ReportType):
    instance_name = report_type.name.replace("_", " ")
    echo(f"INSTANCE: {style(instance_name, bold=True)} Canvas")


def validate_report_type(report_name, verbose=False):
    if isinstance(report_name, ReportType):
        report_type = report_name
    else:
        cli_report_types = get_available_cli_report_types()
        canvas_report_types = get_available_canvas_report_types()
        if report_name not in cli_report_types:
            echo(f'ERROR: Invalid report type "{report_name}"')
            echo("\nReport types implemented in the CLI are:")
            for report_type in get_available_cli_report_type_names():
                echo(f'\t"{report_type}"')
            echo("\nReport types available in Canvas are:")
            for report_type in canvas_report_types:
                echo(f'\t"{report_type}"')
            raise Exit()
        report_type = ReportType(report_name)
    if verbose:
        print_report_type(report_type)
    return report_type


def get_canvas_report_type_name(report_type: ReportType | str) -> str:
    return {
        ReportType.COURSES: "provisioning_csv",
        ReportType.USERS: "provisioning_csv",
        ReportType.STORAGE: "course_storage_csv",
        ReportType.PROVISIONING: "provisioning_csv",
        ReportType.PUBLIC_COURSES: "public_courses_csv",
        "weekly": "provisioning_csv + course_storage_csv",
    }.get(report_type, "provisioning_csv")


@dataclass
class Report:
    report_type: ReportType
    account: Optional[int] = None
    instance: Instance = Instance.PRODUCTION
    term: Optional[str] = CURRENT_YEAR_AND_TERM
    account_report_type: str = ""
    account_report: Optional[AccountReport] = None
    force: bool = False
    report_paths: Optional[Path | list[Path]] = None

    def __post_init__(self):
        if self.account is None:
            self.account = get_main_account_id(self.instance)
        self.account_report_type = get_canvas_report_type_name(self.report_type)

    @cached_property
    def parameters(self):
        parameters_object = dict()
        if (
            self.report_type == ReportType.COURSES
            or self.report_type == ReportType.PROVISIONING
        ):
            parameters_object["courses"] = True
        if (
            self.report_type == ReportType.USERS
            or self.report_type == ReportType.PROVISIONING
        ):
            parameters_object["users"] = True
        if self.term:
            parameters_object["enrollment_term_id"] = get_enrollment_term_id(self.term)
        return parameters_object

    @cached_property
    def file_name(self) -> str:
        instance = format_instance_name(self.instance)
        term = f"_{self.term}" if self.term else ""
        if self.report_type != ReportType.PROVISIONING:
            return f"{self.report_type.value}{term}{instance}"
        else:
            return f"{term}{instance}"

    def create_account_report(self):
        account = get_account(self.account, instance=self.instance)
        if self.parameters:
            account_report = account.create_report(
                self.account_report_type, parameters=self.parameters
            )
        else:
            account_report = account.create_report(self.account_report_type)
        self.account_report = account_report

    def update_account_report(self):
        if not self.account_report:
            return
        account = get_account(self.account, instance=self.instance)
        self.account_report = account.get_report(
            self.account_report.report, self.account_report.id
        )


def get_report_statuses(reports: list[Report]) -> list[str]:
    return [report.account_report.status for report in reports if report.account_report]


def get_progress_status(reports: list[Report]) -> Optional[str]:
    statuses = get_report_statuses(reports)
    return next(
        (status for status in statuses if status in {"created", "running"}), None
    )


def download_report(
    report: Report, base_path: Path, verbose: bool
) -> Optional[Path | list[Path]]:
    if not report.account_report:
        return None
    file_name_replacement = report.file_name
    account_report = report.account_report
    report_paths: Path | list[Path]
    try:
        filename: str = account_report.attachment["filename"]
        url = account_report.attachment["url"]
        report_path = base_path / filename
        download_file(report_path, url)
        if account_report.attachment["mime_class"] == "zip":
            export_path = base_path / filename.replace(".zip", "")
            with ZipFile(report_path) as unzipper:
                unzipper.extractall(export_path)
            paths = [
                path.replace(
                    base_path / f"{path.stem}{file_name_replacement}{path.suffix}"
                )
                for path in export_path.glob("*.csv")
            ]
            remove(report_path)
            rmtree(export_path)
            report_paths = paths
        else:
            report_paths = report_path.replace(
                base_path / f"{report.file_name}{report_path.suffix}"
            )
        return report_paths
    except Exception as error:
        logger.error(error)
        if verbose:
            echo(f"ERROR: {error}")
        account_report.delete_report()
        return None


def print_report_paths(report_paths: list[Path]):
    for path in report_paths:
        echo(f'REPORT: {color(path, "blue")}')


def get_report_display(report: Report) -> str:
    term_display = f" {report.term}" if report.term else " (all terms)"
    return color(f"{report.report_type.name}{term_display}", "blue")


def get_report_displays(reports: list[Report]) -> str:
    report_displays = [get_report_display(report) for report in reports]
    return ", ".join(report_displays)


def flatten(irregular_nested_list: list[list | Any]) -> Iterable:
    for sub_list in irregular_nested_list:
        if isinstance(sub_list, list):
            for item in sub_list:
                yield item
        else:
            yield sub_list


def flatten_paths(paths: list[Path | list[Path]]) -> list[Path]:
    return list(flatten(paths))


def create_reports(
    reports: Report | list[Report],
    base_path=REPORTS,
    verbose=False,
) -> list[Path]:
    reports = make_list(reports)
    for report in reports:
        if report.report_type == ReportType.PROVISIONING:
            report_paths = [
                base_path / f"users{report.file_name}.csv",
                base_path / f"courses{report.file_name}.csv",
            ]
            existing_paths = all(path.exists() for path in report_paths)
        else:
            report_path = base_path / f"{report.file_name}.csv"
            existing_paths = report_path.exists()
            report_paths = report_path
        if report.force or not existing_paths:
            report.create_account_report()
        else:
            report.report_paths = report_paths
    report_paths = [report.report_paths for report in reports]
    if all(report_paths):
        completed_paths_list = [
            report.report_paths for report in reports if report.report_paths
        ]
        completed_paths = flatten_paths(completed_paths_list)
        if verbose:
            print_report_paths(completed_paths)
        return completed_paths
    reports_to_run = [report for report in reports if not report.report_paths]
    completed_reports = [report for report in reports if report.report_paths]
    if completed_reports:
        completed_report_displays = get_report_displays(completed_reports)
        echo(
            f"{color('Using cached report for', 'yellow')}: {completed_report_displays}"
        )
    report_displays = [get_report_display(report) for report in reports_to_run]
    reports_to_run_display = get_report_displays(reports_to_run)
    pluralized_report = pluralize("report", len(report_displays))
    echo(f") Generating {reports_to_run_display} {pluralized_report}...")
    attempts = 0
    status = get_progress_status(reports_to_run)
    while status and attempts <= 180:
        for report in reports_to_run:
            account_report = report.account_report
            progress = account_report.status if account_report else ""
            report_type = (
                account_report.report if account_report else report.report_type.name
            )
            term_display = f" {report.term}" if report.term else ""
            report_display = color(f"{report_type}{term_display}", "cyan")
            echo(f"\t* {report_display} {progress}...")
        sleep(5)
        for report in reports_to_run:
            report.update_account_report()
        status = get_progress_status(reports_to_run)
        attempts += 1
    failed_reports = [
        report
        for report in reports_to_run
        if report.account_report and report.account_report.status != "complete"
    ]
    if failed_reports:
        for report in failed_reports:
            account_report = report.account_report
            if verbose:
                try:
                    last_run_text = (
                        account_report.last_run["paramters"]["extra_text"]
                        if account_report
                        else ""
                    )
                    echo(f"ERROR: {last_run_text}")
                except Exception as error:
                    logger.error(error)
                    echo(
                        "ERROR: The report failed to generate a file. Please try again."
                    )
            if account_report:
                account_report.delete_report()
    if verbose:
        echo("COMPLETE")
    for report in reports_to_run:
        report.report_paths = download_report(report, base_path, verbose)
    completed_paths_list = [
        report.report_paths for report in reports_to_run if report.report_paths
    ]
    completed_paths = flatten_paths(completed_paths_list)
    if verbose:
        print_report_paths(completed_paths)
    return completed_paths


def get_report(
    report: str | Literal["weekly"] | ReportType = ReportType.PROVISIONING,
    term=CURRENT_YEAR_AND_TERM,
    force=False,
    instance_name: str | Instance = Instance.PRODUCTION,
    verbose=False,
) -> list[Path]:
    instance = validate_instance_name(instance_name, verbose=verbose)
    switch_logger_file(LOGS, "report", instance.name)
    if report == "weekly":
        storage_report = Report(
            ReportType.STORAGE,
            instance=instance,
            term=term,
            force=force,
        )
        provisioning_report = Report(
            ReportType.PROVISIONING,
            instance=instance,
            term=term,
            force=force,
        )
        return create_reports([storage_report, provisioning_report], verbose=verbose)
    else:
        report_type = validate_report_type(report)
        return create_reports(
            Report(report_type, instance=instance, term=term, force=force),
            verbose=verbose,
        )


def get_single_report(report_object: Report, verbose: bool) -> Path:
    reports = create_reports(report_object, verbose=verbose)
    try:
        return next(report for report in reports)
    except Exception:
        echo("ERROR: Failed to get report")
        raise Exit()


def get_course_ids_from_reports(terms, instance, force_report, verbose):
    if verbose:
        term_displays = ", ".join(style(term, bold=True) for term in terms)
        echo(f"{pluralize('TERM', len(terms))}: {term_displays}")
    report_objects = [
        Report(ReportType.COURSES, instance=instance, term=term, force=force_report)
        for term in terms
    ]
    report_paths = create_reports(report_objects, verbose=verbose)
    return [
        course_id_list
        for path in report_paths
        for course_id_list in read_csv(path)["canvas_course_id"].tolist()
    ]


def report_main(
    report_type: str | ReportType,
    term_name: str,
    force: bool,
    instance: str | Instance,
    verbose: bool,
):
    get_report(report_type, term_name, force, instance, verbose)
