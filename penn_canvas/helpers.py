from csv import writer
from datetime import datetime
from os import remove
from pathlib import Path
from pprint import PrettyPrinter
from shutil import copy
from zipfile import ZipFile

from canvasapi import Canvas
from canvasapi.account import Account
from cx_Oracle import connect, init_oracle_client
from pandas import read_csv
from pytz import timezone, utc
from typer import Exit, confirm, echo, progressbar, style

from .config import get_penn_canvas_config
from .style import color

COMMAND_DIRECTORY_BASE = Path.home() / "penn-canvas"
BOX_PATH = Path.home() / "Library/CloudStorage/Box-Box"
BOX_CLI_PATH = BOX_PATH / "Penn Canvas CLI"
YEAR = datetime.now().strftime("%Y")
MONTH = datetime.now().strftime("%B")
TODAY = datetime.now().strftime("%d_%b_%Y")
TODAY_AS_Y_M_D = datetime.strptime(TODAY, "%d_%b_%Y").strftime("%Y_%m_%d")
CURRENT_DATE = datetime.now()
CURRENT_YEAR = CURRENT_DATE.year
CURRENT_MONTH = CURRENT_DATE.month
NEXT_YEAR = CURRENT_YEAR + 1
PREVIOUS_YEAR = CURRENT_YEAR - 1
MAIN_ACCOUNT_ID = 96678

lib_dir = Path.home() / "Downloads/instantclient_19_8"
config_dir = lib_dir / "network/admin"
init_oracle_client(
    lib_dir=str(lib_dir),
    config_dir=str(config_dir),
)


SPRING, SUMMER, FALL = "A", "B", "C"


def get_term_by_month(month):
    if month >= 9:
        return FALL
    elif month >= 5:
        return SUMMER
    else:
        return SPRING


def get_current_term():
    return {month: get_term_by_month(month) for month in range(1, 13)}.get(
        CURRENT_MONTH, "A"
    )


CURRENT_TERM = get_current_term()


def get_next_term():
    return {SPRING: SUMMER, SUMMER: FALL, FALL: SPRING}.get(get_current_term())


def get_previous_term():
    return {SPRING: FALL, SUMMER: SPRING, FALL: SUMMER}.get(get_current_term())


NEXT_TERM = get_next_term()
PREVIOUS_TERM = get_previous_term()
CURRENT_YEAR_AND_TERM = f"{CURRENT_YEAR}{CURRENT_TERM}"
NEXT_YEAR_AND_TERM = f"{NEXT_YEAR if CURRENT_TERM == FALL else CURRENT_YEAR}{NEXT_TERM}"
PREVIOUS_YEAR_AND_TERM = (
    f"{PREVIOUS_YEAR if CURRENT_TERM == SPRING else CURRENT_YEAR}{PREVIOUS_TERM}"
)


def get_data_warehouse_cursor():
    user, password, dsn = get_penn_canvas_config("data_warehouse")
    return connect(user, password, dsn).cursor()


def confirm_global_protect_enabled():
    return confirm("HAVE YOU ENABLED THE GLOBAL PROTECT VPN?")


def make_index_headers(headers):
    return ["index"] + headers[:]


def make_csv_paths(csv_dir, csv_file, headers):
    if not csv_dir.exists():
        Path.mkdir(csv_dir)
    if not csv_file.is_file():
        with open(csv_file, "w", newline="") as result:
            writer(result).writerow(headers)


def get_command_paths(
    command, logs=False, processed=False, no_input=False, completed=False
):
    box_exists = BOX_PATH.exists()
    base_path = BOX_CLI_PATH if box_exists else COMMAND_DIRECTORY_BASE
    command_directory = base_path / f"{command}"
    input_directory = command_directory / "Input"
    paths = [input_directory, (command_directory / "RESULTS")]
    if logs:
        paths.append(command_directory / "logs")
    if processed:
        paths.append(command_directory / ".processed")
    if no_input:
        paths.remove(input_directory)
    if completed:
        paths.append(command_directory / "Completed")
    for path in paths:
        if not path.exists():
            Path.mkdir(path, parents=True)
    return tuple(paths)


def get_completed_result(result_directory):
    csv_files = [result for result in Path(result_directory).glob("*.csv")]
    return next(
        (
            result
            for result in csv_files
            if TODAY_AS_Y_M_D in result.name and "ACTIVATED" in result.name
        ),
        None,
    )


def print_task_complete_message(result_path):
    color("TASK ALREADY COMPLETE", "yellow", True)
    result_path_display = color(result_path, "green")
    echo(f"- Output available at: {result_path_display}")
    echo(
        "- To re-run the task, overwriting previous results, run this command"
        " with the '--force' option"
    )
    color("FINISHED", "yellow", True)


def check_previous_output(result_path, result_directory):
    echo(") Checking for previous results...")
    index = 0
    if result_path.is_file():
        INCOMPLETE = read_csv(result_path)
        if "index" in INCOMPLETE.columns:
            try:
                index = INCOMPLETE.at[INCOMPLETE.index[-1], "index"]
                INCOMPLETE.drop(
                    INCOMPLETE[INCOMPLETE["index"] == index].index, inplace=True
                )
                INCOMPLETE.to_csv(result_path, index=False)
            except Exception:
                index = 0
        else:
            print_task_complete_message(result_path)
            raise Exit()
    elif result_directory:
        completed_result = get_completed_result(result_directory)
        if completed_result:
            print_task_complete_message(completed_result)
            raise Exit()
    return index


def get_start_index(force, result_path, result_directory=None):
    if force:
        if result_path.exists():
            remove(result_path)
        return 0
    else:
        return check_previous_output(result_path, result_directory)


def make_skip_message(start, item):
    if start == 0:
        return
    elif start == 1:
        item = f"{item.upper()}"
    else:
        item = f"{item.upper()}S"
    message = color(f"SKIPPING {start:,} PREVIOUSLY PROCESSED {item}...", "yellow")
    echo(f") {message}")


def handle_clear_processed(clear_processed, processed_path, item_plural="users"):
    if type(processed_path) != list:
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


def print_missing_input_and_exit(input_file_name, please_add_message, date=True):
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


def get_processed(processed_directory, processed_path, columns="pennkey"):
    if type(columns) != list:
        columns = [columns]
    if processed_path.is_file():
        result = read_csv(processed_path, dtype=str)
        return result[columns[0]].tolist()
    else:
        make_csv_paths(processed_directory, processed_path, columns)
        return list()


def get_canvas(instance="prod", verbose=True, override_key=False):
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
    instance_name = "PRODUCTION"
    if instance == "test":
        url = canvas_test_url
        key = override_key or canvas_test_key
        instance_name = "TEST"
    elif instance == "beta":
        url = canvas_beta_url
        key = override_key or canvas_beta_key
        instance_name = "BETA"
    elif instance == "open":
        url = open_canvas_url
        key = override_key or open_canvas_key
        instance_name = "OPEN"
    elif instance == "open_test":
        url = open_canvas_test_url
        key = override_key or open_canvas_test_key
        instance_name = "TEST OPEN"
    if verbose:
        echo(f") Accessing {style(instance_name, bold=True)} Canvas...")
    return Canvas(url, key)


def pprint(thing):
    if isinstance(thing, list):
        for item in thing[:5]:
            PrettyPrinter().pprint(vars(item))
    else:
        PrettyPrinter().pprint(vars(thing))


def collect(paginator):
    return [item for item in paginator]


def get_account(
    account=MAIN_ACCOUNT_ID, use_sis_id=False, instance="prod", verbose=False
) -> Account:
    account = get_canvas(instance).get_account(account, use_sis_id=use_sis_id)
    if verbose:
        pprint(account)
    return account


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
        if read_csv(path).empty:
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
