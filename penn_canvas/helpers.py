from csv import writer
from datetime import datetime
from os import remove
from cx_Oracle import init_oracle_client
from pathlib import Path
from shutil import copy

from canvasapi import Canvas
from pandas import read_csv
from typer import Abort, Exit, colors, confirm, echo, progressbar, prompt, secho, style

CANVAS_URL_PROD = "https://canvas.upenn.edu"
CANVAS_URL_TEST = "https://upenn.test.instructure.com"
CANVAS_URL_OPEN = "https://upenn-catalog.instructure.com"
CONFIG_DIRECTORY = Path.home() / ".config"
CONFIG_PATH = CONFIG_DIRECTORY / "penn-canvas"
COMMAND_DIRECTORY_BASE = Path.home() / "penn-canvas"
BOX_PATH = Path.home() / "Box"
BOX_CLI_PATH = BOX_PATH / "Penn Canvas CLI"
YEAR = datetime.now().strftime("%Y")
MONTH = datetime.now().strftime("%B")
TODAY = datetime.now().strftime("%d_%b_%Y")
TODAY_AS_Y_M_D = datetime.strptime(TODAY, "%d_%b_%Y").strftime("%Y_%m_%d")
MAIN_ACCOUNT_ID = 96678


def make_config():
    if not CONFIG_DIRECTORY.exists():
        Path.mkdir(CONFIG_DIRECTORY, parents=True)

    (
        production,
        development,
        open_canvas,
        data_warehouse_user,
        data_warehouse_password,
        data_warehouse_dsn,
    ) = read_config(CONFIG_PATH)

    use_production = confirm("Input an Access Token for PRODUCTION?")

    if use_production:
        production = prompt(
            "Please enter your Access Token for the PRODUCTION instance of Penn Canvas",
            hide_input=True,
        )

    use_development = confirm("Input an Access Token for DEVELOPMENT?")

    if use_development:
        development = prompt(
            "Please enter your Access Token for the TEST instance of Penn Canvas",
            hide_input=True,
        )

    use_open = confirm("Input an Access Token for OPEN canvas?")

    if use_open:
        open_canvas = prompt(
            "Please enter your Access Token for OPEN Canvas",
            hide_input=True,
        )

    use_data_warehouse = confirm("Input DATA WAREHOUSE credentials?")

    if use_data_warehouse:
        data_warehouse_user = prompt("Please enter your DATA WAREHOUSE USER")
        data_warehouse_password = prompt(
            "Please enter your DATA WAREHOUSE PASSWORD",
            hide_input=True,
        )
        data_warehouse_dsn = prompt("Please enter your DATA WAREHOUSE DSN")

    with open(CONFIG_PATH, "w+") as config:
        config.write(f"CANVAS_KEY_PROD={production}")
        config.write(f"\nCANVAS_KEY_DEV={development}")
        config.write(f"\nCANVAS_KEY_OPEN={open_canvas}")
        config.write(f"\nDATA_WAREHOUSE_USER={data_warehouse_user}")
        config.write(f"\nDATA_WAREHOUSE_PASSWORD={data_warehouse_password}")
        config.write(f"\nDATA_WAREHOUSE_DSN={data_warehouse_dsn}")


def display_config():
    if confirm(
        "This command will display sensitive information on your screen. Are you sure"
        " you want to proceed?"
    ):
        (
            production,
            development,
            open_canvas,
            data_warehouse_user,
            data_warehouse_password,
            data_warehouse_dsn,
        ) = check_config(CONFIG_PATH)

        config_value_color = "yellow"
        production = colorize(f"{production}", config_value_color)
        development = colorize(f"{development}", config_value_color)
        open_canvas = colorize(f"{open_canvas}", config_value_color)
        data_warehouse_user = colorize(f"{data_warehouse_user}", config_value_color)
        data_warehouse_password = colorize(
            f"{data_warehouse_password}", config_value_color
        )
        data_warehouse_dsn = colorize(f"{data_warehouse_dsn}", config_value_color)
        config_path = colorize(f"{CONFIG_PATH}", "green")

        echo(
            f"\nCONFIG: {config_path}\n"
            f"\nCANVAS_KEY_PROD: {production}"
            f"\nCANVAS_KEY_DEV: {development}"
            f"\nCANVAS_KEY_OPEN: {open_canvas}"
            f"\nDATA_WAREHOUSE_USER: {data_warehouse_user}"
            f"\nDATA_WAREHOUSE_PASSWORD: {data_warehouse_password}"
            f"\nDATA_WAREHOUSE_DSN: {data_warehouse_dsn}"
        )


def check_config(config):
    if not config.exists():
        error = colorize(
            "- ERROR: No config file ($HOME/.config/penn-canvas) exists for"
            " Penn-Canvas.",
            "yellow",
        )
        create = confirm(f"{error} \n- Would you like to create one?")

        if not create:
            echo(
                ") NOT creating...\n"
                "- Please create a config file at: $HOME/.config/penn-canvas"
                "\n- Place your Canvas Access Tokens in this file using the following"
                " format:"
                "\n\tCANVAS_KEY_PROD=your-canvas-prod-key-here"
                "\n\tCANVAS_KEY_DEV=your-canvas-test-key-here"
                "\n\tCANVAS_KEY_OPEN=your-open-canvas-key-here"
            )
            raise Abort()
        else:
            make_config()

    return read_config(config)


def read_config(config):
    production = ""
    development = ""
    open_canvas = ""
    data_warehouse_user = ""
    data_warehouse_password = ""
    data_warehouse_dsn = ""

    if config.is_file():
        with open(CONFIG_PATH, "r") as config:
            LINES = config.read().splitlines()

            for line in LINES:
                if "CANVAS_KEY_PROD" in line:
                    production = line.replace("CANVAS_KEY_PROD=", "")
                elif "CANVAS_KEY_DEV" in line:
                    development = line.replace("CANVAS_KEY_DEV=", "")
                elif "CANVAS_KEY_OPEN" in line:
                    open_canvas = line.replace("CANVAS_KEY_OPEN=", "")
                elif "DATA_WAREHOUSE_USER" in line:
                    data_warehouse_user = line.replace("DATA_WAREHOUSE_USER=", "")
                elif "DATA_WAREHOUSE_PASSWORD" in line:
                    data_warehouse_password = line.replace(
                        "DATA_WAREHOUSE_PASSWORD=", ""
                    )
                elif "DATA_WAREHOUSE_DSN" in line:
                    data_warehouse_dsn = line.replace("DATA_WAREHOUSE_DSN=", "")

    return (
        production,
        development,
        open_canvas,
        data_warehouse_user,
        data_warehouse_password,
        data_warehouse_dsn,
    )


def get_data_warehouse_config():
    echo(") Reading Data Warehouse credentials from config file...")

    return check_config(CONFIG_PATH)[3:]


def init_data_warehouse():
    lib_dir = Path.home() / "Downloads/instantclient_19_8"
    config_dir = lib_dir / "network/admin"
    init_oracle_client(
        lib_dir=str(lib_dir),
        config_dir=str(config_dir),
    )


def make_index_headers(headers):
    INDEX_HEADERS = headers[:]
    INDEX_HEADERS.insert(0, "index")

    return INDEX_HEADERS


def make_csv_paths(csv_dir, csv_file, headers):
    if not csv_dir.exists():
        Path.mkdir(csv_dir)

    if not csv_file.is_file():
        with open(csv_file, "w", newline="") as result:
            writer(result).writerow(headers)


def get_command_paths(command, logs=False, processed=False):
    BOX = BOX_PATH.exists()
    BASE = BOX_CLI_PATH if BOX else COMMAND_DIRECTORY_BASE
    COMMAND_DIRECTORY = BASE / f"{command}"
    PATHS = [(COMMAND_DIRECTORY / "Input"), (COMMAND_DIRECTORY / "RESULTS")]

    if logs:
        PATHS.append(COMMAND_DIRECTORY / "logs")

    if processed:
        PATHS.append(COMMAND_DIRECTORY / ".processed")

    for path in PATHS:
        if not path.exists():
            Path.mkdir(path, parents=True)

    return tuple(PATHS)


def get_completed_result(result_directory):
    CSV_FILES = [result for result in Path(result_directory).glob("*.csv")]

    return next(
        (
            result
            for result in CSV_FILES
            if TODAY_AS_Y_M_D in result.name and "ACTIVATED" in result.name
        ),
        None,
    )


def print_task_complete_message(result_path):
    colorize("TASK ALREADY COMPLETE", "yellow", True)
    result_path_display = colorize(result_path, "green")
    echo(f"- Output available at: {result_path_display}")
    echo(
        "- To re-run the task, overwriting previous results, run this command"
        " with the '--force' option"
    )
    colorize("FINISHED", "yellow", True)


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

    message = colorize(f"SKIPPING {start:,} PREVIOUSLY PROCESSED {item}...", "yellow")
    echo(f") {message}")


def handle_clear_processed(clear_processed, processed_path, item_plural="users"):
    if type(processed_path) != list:
        processed_path = [processed_path]

    if clear_processed:
        message = colorize(
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
    if date:
        date_message = " matching today's date "

    error = colorize(
        f"- ERROR: A {input_file_name}{date_message if date else ' '}was not found.",
        "yellow",
    )

    return f"{error}\n- {please_add_message}"


def find_input(
    command,
    input_file_name,
    input_directory,
    extension="*.csv",
    date=True,
    bulk_enroll=False,
):
    def get_input(path):
        INPUT_FILES = [input_file for input_file in Path(path).glob(extension)]

        if bulk_enroll:
            return [
                input_file
                for input_file in INPUT_FILES
                if "bulk enroll" in input_file.name.lower() and YEAR in input_file.name
            ]
        else:
            return [
                input_file for input_file in INPUT_FILES if TODAY in input_file.name
            ]

    echo(f") Finding {input_file_name}...")

    if date:
        date_message = " matching today's date "

    please_add_message = (
        "Please add a"
        f" {input_file_name}{date_message if date else ' '}to the following"
        " directory and then run this script again:"
        f" {colorize(input_directory,'green')}\n- (If you need instructions for"
        " generating one, run this command with the '--help' flag.)"
    )

    if not input_directory.exists():
        Path.mkdir(input_directory, parents=True)
        error = colorize("- ERROR: {command} Input directory not found.", "yellow")
        echo(
            f"{error} \n- Creating one for you at:"
            f" {colorize(input_directory, 'green')}\n- {please_add_message}"
        )

        raise Exit(1)

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

        raise Exit(1)
    else:
        return TODAYS_INPUT, please_add_message, missing_file_message


def process_input(
    input_files,
    input_file_name,
    input_directory,
    please_add_message,
    headers,
    cleanup_data,
    missing_file_message,
    args=None,
    start=0,
    bulk_enroll=False,
):
    echo(f") Preparing {input_file_name}...")

    reports = iter(input_files)
    error = True
    abort = False

    while error:
        try:
            report = next(reports, None)

            if not report:
                error = False
                abort = True
                echo(missing_file_message)
            else:
                data = read_csv(report)
                data = data.loc[:, headers]

                if not report.parents[0] == input_directory:
                    copy(report, input_directory / report.name)
                    remove(report)

                error = False
        except Exception:
            error = True

    if abort:
        raise Exit(1)

    if args:
        data = cleanup_data(data, args)
    else:
        data = cleanup_data(data)

    if not bulk_enroll:
        data.reset_index(drop=True, inplace=True)
        TOTAL = len(data.index)
        data = data.loc[start:TOTAL, :]

        return data, f"{TOTAL:,}"
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


def get_canvas(instance="test"):
    echo(") Reading Canvas Access Tokens from config file...")

    production, development, open_canvas = check_config(CONFIG_PATH)[0:3]
    url = CANVAS_URL_TEST
    access_token = development

    if instance == "prod":
        url = CANVAS_URL_PROD
        access_token = production
    elif instance == "open":
        url = CANVAS_URL_OPEN
        access_token = open_canvas

    return Canvas(url, access_token)


def colorize(text, color="magenta", echo=False):
    typer_colors = {
        "blue": colors.BLUE,
        "cyan": colors.CYAN,
        "green": colors.GREEN,
        "magenta": colors.MAGENTA,
        "red": colors.RED,
        "yellow": colors.YELLOW,
    }

    text = f"{text:,}" if type(text) == int else str(text)

    if echo:
        return secho(text, fg=typer_colors[color])
    else:
        return style(text, fg=typer_colors[color])


def dynamic_to_csv(path, data_frame, condition, columns):
    mode = "a" if condition else "w"
    data_frame.to_csv(path, mode=mode, header=not condition, index=False)


def drop_duplicate_errors(paths):
    for path in paths:
        read_csv(path).drop_duplicates().to_csv(path, index=False)


def add_headers_to_empty_files(data_frames, headers):
    for path, data_frame in data_frames.items():
        if data_frame.empty:
            with open(path, "w", newline="") as output_file:
                writer(output_file).writerow(headers)


def toggle_progress_bar(data, callback, canvas, verbose, args=None):
    def verbose_mode():
        for item in data.itertuples():
            callback(item, canvas, verbose, args)

    def progress_bar_mode():
        with progressbar(data.itertuples(), length=len(data.index)) as progress:
            for item in progress:
                callback(item, canvas, verbose, args)

    if verbose:
        verbose_mode()
    else:
        progress_bar_mode()
