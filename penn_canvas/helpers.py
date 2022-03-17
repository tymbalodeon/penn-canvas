from csv import writer
from datetime import datetime
from enum import Enum
from os import remove
from pathlib import Path
from pprint import PrettyPrinter
from shutil import copy, rmtree
from zipfile import ZipFile

from canvasapi import Canvas
from canvasapi.account import Account
from canvasapi.paginated_list import PaginatedList
from click.termui import style
from cx_Oracle import connect, init_oracle_client
from pandas import read_csv
from pytz import timezone, utc
from typer import Exit, confirm, echo, progressbar

from .config import get_penn_canvas_config
from .style import color

COMMAND_DIRECTORY_BASE = Path.home() / "penn-canvas"
BOX_PATH = Path.home() / "Library/CloudStorage/Box-Box"
BOX_CLI_PATH = BOX_PATH / "Penn Canvas CLI"
BASE_PATH = BOX_CLI_PATH if BOX_PATH.exists() else COMMAND_DIRECTORY_BASE
CURRENT_DATE = datetime.now()
YEAR = CURRENT_DATE.strftime("%Y")
MONTH = CURRENT_DATE.strftime("%B")
TODAY = CURRENT_DATE.strftime("%d_%b_%Y")
TODAY_AS_Y_M_D = datetime.strptime(TODAY, "%d_%b_%Y").strftime("%Y_%m_%d")
CURRENT_YEAR = CURRENT_DATE.year
CURRENT_MONTH = CURRENT_DATE.month
NEXT_YEAR = CURRENT_YEAR + 1
PREVIOUS_YEAR = CURRENT_YEAR - 1
MAIN_ACCOUNT_ID = 96678


def create_directory(new_directory: Path, parents=True) -> Path:
    if not new_directory.exists():
        Path.mkdir(new_directory, parents=parents)
    return new_directory


def remove_old_reports_directories(reports_path: Path):
    def is_old_reports_directory(path):
        if not path.is_dir():
            return False
        try:
            date = datetime.strptime(str(path).split("/")[-1], "%Y-%m-%d")
            return (CURRENT_DATE - date).days > 30
        except Exception:
            return True

    previous_paths = [
        path for path in reports_path.iterdir() if is_old_reports_directory(path)
    ]
    for path in previous_paths:
        rmtree(path)


def get_reports_directory() -> Path:
    base_path = BOX_CLI_PATH if BOX_PATH.exists() else COMMAND_DIRECTORY_BASE
    reports_path = create_directory(base_path / "REPORTS")
    remove_old_reports_directories(reports_path)
    return create_directory(reports_path / TODAY_AS_Y_M_D.replace("_", "-"))


REPORTS = get_reports_directory()

lib_dir = Path.home() / "Downloads/instantclient_19_8"
config_dir = lib_dir / "network/admin"
init_oracle_client(
    lib_dir=str(lib_dir),
    config_dir=str(config_dir),
)


class Term(Enum):
    SPRING = "10"
    SUMMER = "20"
    FALL = "30"


def get_term_by_month(month: int) -> Term:
    if month >= 9:
        return Term.FALL
    elif month >= 5:
        return Term.SUMMER
    else:
        return Term.SPRING


def get_current_term() -> Term:
    return {month: get_term_by_month(month) for month in range(1, 13)}.get(
        CURRENT_MONTH, Term.SPRING
    )


def get_term_display(term: Term) -> str:
    term_displays = {term: term.name.title() for term in Term}
    return term_displays.get(term, Term.SPRING.value)


def get_next_term() -> Term:
    return {
        Term.SPRING: Term.SUMMER,
        Term.SUMMER: Term.FALL,
        Term.FALL: Term.SPRING,
    }.get(get_current_term(), Term.SPRING)


def get_previous_term() -> Term:
    return {
        Term.SPRING: Term.FALL,
        Term.SUMMER: Term.SPRING,
        Term.FALL: Term.SUMMER,
    }.get(get_current_term(), Term.SPRING)


CURRENT_TERM = get_current_term()
CURRENT_TERM_DISPLAY = get_term_display(get_current_term())
NEXT_TERM = get_next_term()
PREVIOUS_TERM = get_previous_term()
CURRENT_YEAR_AND_TERM = (
    "2022A"
    if CURRENT_YEAR == 2022 and CURRENT_TERM == Term.SPRING
    else f"{CURRENT_YEAR}{CURRENT_TERM}"
)
CURRENT_TERM_NAME = (
    f"{CURRENT_YEAR_AND_TERM} (Banner {CURRENT_TERM_DISPLAY} {CURRENT_YEAR})"
)
NEXT_YEAR_AND_TERM = (
    f"{NEXT_YEAR if CURRENT_TERM == Term.FALL else CURRENT_YEAR}{NEXT_TERM}"
)
PREVIOUS_YEAR_AND_TERM = (
    f"{PREVIOUS_YEAR if CURRENT_TERM == Term.SPRING else CURRENT_YEAR}{PREVIOUS_TERM}"
)


def get_data_warehouse_cursor():
    user, password, dsn = get_penn_canvas_config("data_warehouse")
    return connect(user, password, dsn).cursor()


def confirm_global_protect_enabled():
    return confirm("HAVE YOU ENABLED THE GLOBAL PROTECT VPN?")


def make_index_headers(headers: list[str]) -> list[str]:
    return ["index"] + headers[:]


def make_csv_paths(csv_file: Path, headers: list[str]):
    if not csv_file.is_file():
        parent_directory = next(parent for parent in csv_file.parents)
        create_directory(parent_directory)
        with open(csv_file, "w", newline="") as result:
            writer(result).writerow(headers)


def get_command_paths(
    command_name: str,
    include_logs_directory=False,
    include_processed_directory=False,
    include_input_directory=False,
    include_completed_directory=False,
):
    base_path = BOX_CLI_PATH if BOX_PATH.exists() else COMMAND_DIRECTORY_BASE
    command_directory = base_path / f"{command_name}"
    paths = {"results": command_directory / "RESULTS"}
    if include_logs_directory:
        paths["logs"] = command_directory / "logs"
    if include_processed_directory:
        paths["processed"] = command_directory / ".processed"
    if include_input_directory:
        paths["input"] = command_directory / "Input"
    if include_completed_directory:
        paths["completed"] = command_directory / "Completed"
    for path in paths.values():
        create_directory(path)
    return paths


def print_task_complete_message(result_path: Path):
    color("TASK ALREADY COMPLETE", "yellow", True)
    result_path_display = color(result_path, "green")
    echo(f"- Output available at: {result_path_display}")
    echo(
        "- To re-run the task, overwriting previous results, run this command"
        " with the '--force' option"
    )
    color("FINISHED", "yellow", True)


def get_start_index(force: bool, result_path: Path) -> int:
    index = 0
    if force:
        if result_path.exists():
            remove(result_path)
        return index
    else:
        echo(") Checking for previous results...")
        if not result_path.is_file():
            return index
        INCOMPLETE = read_csv(result_path)
        if "index" in INCOMPLETE.columns:
            try:
                index = INCOMPLETE.at[INCOMPLETE.index[-1], "index"]
                INCOMPLETE.drop(
                    INCOMPLETE[INCOMPLETE["index"] == index].index, inplace=True
                )
                INCOMPLETE.to_csv(result_path, index=False)
            except Exception:
                return index
        else:
            print_task_complete_message(result_path)
            raise Exit()
        return index


def print_skip_message(start: int, item: str, current_report=False):
    if start == 0:
        return
    elif start == 1:
        item = f"{item.upper()}"
    else:
        item = f"{item.upper()}S"
    current_report_message = " from the current report" if current_report else ""
    message = color(
        f"SKIPPING {start:,} previously processed {item}{current_report_message}...",
        "yellow",
    )
    echo(f") {message}")


def handle_clear_processed(
    clear_processed: bool, processed_path: Path | list[Path], item_plural="users"
):
    if not isinstance(processed_path, list):
        processed_path = [processed_path]
    if clear_processed:
        message = color(
            f"You have asked to clear the list of {item_plural} already processed."
            " This list makes subsequent runs of the command faster. Are you sure"
            " you want to do this?",
            "yellow",
        )
        proceed = confirm(f"- {message}")
    else:
        proceed = False
    if proceed:
        echo(f") Clearing list of {item_plural} already processed...")
        for path in processed_path:
            if path.exists():
                remove(path)
    else:
        echo(f") Finding {item_plural} already processed...")


def print_missing_input_and_exit(
    input_file_name: str, please_add_message: str, date=True
) -> str:
    date_message = " matching today's date " if date else " "
    error = color(
        f"- ERROR: A {input_file_name}{date_message}was not found.",
        "yellow",
    )
    return f"{error}\n- {please_add_message}"


def find_input(
    input_file_name,
    input_directory,
    extension="*.csv",
    date=True,
    bulk_enroll=False,
    open_canvas=False,
):
    def get_input(path):
        ZIP_FILES = [
            input_file
            for input_file in Path(path).glob("*.zip")
            if "provisioning" in input_file.name
        ]
        if ZIP_FILES:
            for zip_file in ZIP_FILES:
                with ZipFile(zip_file) as unzipper:
                    unzipper.extractall(path)
                remove(zip_file)
        INPUT_FILES = [input_file for input_file in Path(path).glob(extension)]
        if bulk_enroll:
            return [
                input_file
                for input_file in INPUT_FILES
                if "bulk enroll" in input_file.name.lower() and YEAR in input_file.name
            ]
        elif open_canvas:
            return INPUT_FILES
        else:
            return [
                input_file
                for input_file in INPUT_FILES
                if datetime.today().date()
                == datetime.fromtimestamp(input_file.stat().st_ctime).date()
            ]

    echo(f") Finding {input_file_name}...")
    date_message = " matching today's date " if date else ""
    please_add_message = (
        "Please add a"
        f" {input_file_name}{date_message if date else ' '}to the following"
        " directory and then run this script again:"
        f" {color(input_directory,'green')}\n- (If you need instructions for"
        " generating one, run this command with the '--help' flag.)"
    )
    if not input_directory.exists():
        Path.mkdir(input_directory, parents=True)
        error = color("- ERROR: {command} Input directory not found.", "yellow")
        echo(
            f"{error} \n- Creating one for you at:"
            f" {color(input_directory, 'green')}\n- {please_add_message}"
        )
        raise Exit()
    if open_canvas:
        TODAYS_INPUT = get_input(input_directory)
    else:
        HOME = Path.home()
        TODAYS_INPUT = get_input(HOME / "Downloads")
        PATHS = [HOME / path for path in ["Desktop", "Documents"]]
        PATHS.append(input_directory)
        PATHS = iter(PATHS)
        while not TODAYS_INPUT:
            try:
                TODAYS_INPUT = get_input(next(PATHS))
            except Exception:
                TODAYS_INPUT = None
                break
    missing_file_message = print_missing_input_and_exit(
        input_file_name, please_add_message, date
    )
    if not TODAYS_INPUT:
        echo(missing_file_message)
        raise Exit()
    else:
        return TODAYS_INPUT, missing_file_message


def process_input(
    input_files,
    input_file_name,
    input_directory,
    headers,
    cleanup_data,
    missing_file_message,
    args=None,
    start=0,
    bulk_enroll=False,
    open_canvas=False,
):
    echo(f") Preparing {input_file_name}...")
    reports = iter(input_files)
    error = True
    abort = False
    report = None
    data = None
    while error:
        try:
            report = next(reports, None)
            if not report:
                error = False
                abort = True
                echo(missing_file_message)
            else:
                data = read_csv(report, encoding="latin1" if open_canvas else "utf-8")
                data = data.loc[:, headers]
                if TODAY not in report.name:
                    report = report.rename(
                        report.parents[0] / f"{report.stem}_{TODAY}{report.suffix}"
                    )
                if not report.parents[0] == input_directory:
                    copy(report, input_directory / report.name)
                    remove(report)
                error = False
        except Exception:
            error = True
    if abort:
        raise Exit()
    if args:
        data = cleanup_data(data, args)
    else:
        data = cleanup_data(data)
    if not bulk_enroll:
        data.reset_index(drop=True, inplace=True)
        TOTAL = len(data.index)
        data = data.loc[start:TOTAL, :]
        return (data, TOTAL, report) if open_canvas else (data, TOTAL)
    else:
        return data


def get_processed(processed_path, columns: str | list[str] = "pennkey") -> list[str]:
    if isinstance(columns, str):
        columns = [columns]
    if processed_path.is_file():
        result = read_csv(processed_path, dtype=str)
        return result[columns[0]].tolist()
    else:
        make_csv_paths(processed_path, columns)
        return list()


class Instance(Enum):
    PRODUCTION = "prod"
    TEST = "test"
    BETA = "beta"
    OPEN = "open"
    OPEN_TEST = "open_test"


def validate_instance_name(instance_name, verbose=False):
    if isinstance(instance_name, Instance):
        instance = instance_name
    else:
        instances = [instance.value for instance in Instance]
        if instance_name not in instances:
            echo(f'ERROR: Invalid instance name "{instance_name}"')
            echo("\nAvailable instances are:")
            for instance in instances:
                echo(f'\t"{instance}"')
            raise Exit()
        instance = Instance(instance_name)
    if verbose:
        print_instance(instance)
    return instance


def print_instance(instance: Instance):
    instance_name = instance.name.replace("_", " ")
    echo(f"INSTANCE: {style(instance_name, bold=True)} Canvas")


def format_instance_name(instance: Instance) -> str:
    return f"_{instance.name}"


def get_canvas(instance=Instance.PRODUCTION, verbose=True, override_key=None) -> Canvas:
    canvas_urls = get_penn_canvas_config("canvas_urls")
    canvas_keys = get_penn_canvas_config("canvas_keys")
    (
        canvas_prod_key,
        canvas_test_key,
        canvas_beta_key,
        open_canvas_key,
        open_canvas_test_key,
    ) = canvas_keys
    (
        canvas_prod_url,
        canvas_test_url,
        canvas_beta_url,
        open_canvas_url,
        open_canvas_test_url,
    ) = canvas_urls
    url = canvas_prod_url
    key = override_key or canvas_prod_key
    if instance == Instance.TEST:
        url = canvas_test_url
        key = override_key or canvas_test_key
    elif instance == Instance.BETA:
        url = canvas_beta_url
        key = override_key or canvas_beta_key
    elif instance == Instance.OPEN:
        url = open_canvas_url
        key = override_key or open_canvas_key
    elif instance == Instance.OPEN_TEST:
        url = open_canvas_test_url
        key = override_key or open_canvas_test_key
    canvas = Canvas(url, key)
    try:
        canvas.get_account(MAIN_ACCOUNT_ID)
        if verbose:
            print_instance(instance)
        return canvas
    except Exception:
        raise SystemExit("ERROR: Invalid access token")


def pprint(thing: object):
    if isinstance(thing, list):
        for item in thing[:5]:
            PrettyPrinter().pprint(vars(item))
    else:
        PrettyPrinter().pprint(vars(thing))


def collect(paginator: PaginatedList | list, function=None) -> list:
    if function:
        return [function(item) for item in paginator]
    else:
        return [item for item in paginator]


def get_account(
    account: int | Account = MAIN_ACCOUNT_ID,
    use_sis_id=False,
    instance=Instance.PRODUCTION,
    verbose=False,
) -> Account:
    if isinstance(account, Account):
        return account
    instance = validate_instance_name(instance)
    account_object = get_canvas(instance, verbose=verbose).get_account(
        account, use_sis_id=use_sis_id
    )
    if verbose:
        pprint(account)
    return account_object


def get_course(
    course_id: str | int,
    use_sis_id=False,
    instance=Instance.PRODUCTION,
    verbose=False,
    pretty_print=False,
):
    course = get_canvas(instance, verbose).get_course(course_id, use_sis_id)
    if pretty_print:
        pprint(course)
    return course


def get_section(
    section_id: str | int,
    use_sis_id=False,
    instance=Instance.PRODUCTION,
    verbose=False,
    pretty_print=False,
):
    section = get_canvas(instance, verbose).get_section(section_id, use_sis_id)
    if pretty_print:
        pprint(section)
    return section


def get_user(
    user_id: str | int,
    id_type=None,
    instance=Instance.PRODUCTION,
    verbose=False,
    pretty_print=False,
):
    user = get_canvas(instance, verbose).get_user(user_id, id_type=id_type)
    if pretty_print:
        pprint(user)
    return user


def get_sub_accounts(canvas, account_id):
    account = canvas.get_account(account_id)
    return [str(account_id)] + [
        str(account.id) for account in account.get_subaccounts(recursive=True)
    ]


def dynamic_to_csv(path, data_frame, condition):
    mode = "a" if condition else "w"
    data_frame.to_csv(path, mode=mode, header=not condition, index=False)


def drop_duplicate_errors(paths):
    for path in paths:
        read_csv(path).drop_duplicates().to_csv(path, index=False)


def add_headers_to_empty_files(paths, headers):
    for path in paths:
        try:
            read_csv(path)
        except Exception:
            with open(path, "w", newline="") as output_file:
                writer(output_file).writerow(headers)


def convert_to_est(timestamp):
    return utc.localize(timestamp).astimezone(timezone("US/Eastern"))


def format_timestamp(timestamp, localize=True):
    if timestamp:
        date = datetime.fromisoformat(timestamp.replace("Z", ""))
        if localize:
            date = convert_to_est(date)
        return date.strftime("%b %d, %Y (%I:%M:%S %p)")
    else:
        return None


def format_timedelta(timedelta):
    days = timedelta.days
    hours, remainder = divmod(timedelta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    days = f"{days} {'days' if days > 1 else 'day'}" if days else ""
    hours = f"{hours} {'hours' if hours > 1 else 'hour'}" if hours else ""
    minutes = f"{minutes} {'minutes' if minutes > 1 else 'minute'}" if minutes else ""
    seconds = f"{seconds} {'seconds' if seconds > 1 else 'second'}" if seconds else ""
    return ", ".join([time for time in [days, hours, minutes, seconds] if time])


def toggle_progress_bar(data, callback, canvas, verbose, args=None):
    def verbose_mode():
        for item in data.itertuples():
            callback(item, canvas, verbose, args)

    def progress_bar_mode():
        with progressbar(data.itertuples(), length=len(data.index)) as progress:
            for item in progress:
                callback(item, canvas, verbose, args)

    def verbose_mode_no_args():
        for item in data.itertuples():
            callback(item, canvas, verbose)

    def progress_bar_mode_no_args():
        with progressbar(data.itertuples(), length=len(data.index)) as progress:
            for item in progress:
                callback(item, canvas, verbose)

    if not args:
        if verbose:
            verbose_mode_no_args()
        else:
            progress_bar_mode_no_args()
    else:
        if verbose:
            verbose_mode()
        else:
            progress_bar_mode()


def get_external_tool_names(verbose=False):
    account = get_account()
    sub_accounts = collect(account.get_subaccounts(recursive=True))
    external_tool_names = list()
    for sub_account in sub_accounts:
        external_tool_names = external_tool_names + [
            tool.name.lower() for tool in collect(sub_account.get_external_tools())
        ]
    external_tool_names = sorted(set(external_tool_names))
    if verbose:
        print(*external_tool_names, sep="\n")
    return external_tool_names
