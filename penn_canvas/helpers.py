from csv import writer
from datetime import datetime
from os import remove
from pathlib import Path

from canvasapi import Canvas
from pandas import read_csv
from typer import Abort, Exit, colors, confirm, echo, progressbar, prompt, secho, style

CANVAS_URL_PROD = "https://canvas.upenn.edu"
CANVAS_URL_TEST = "https://upenn.test.instructure.com"
CANVAS_URL_OPEN = "https://upenn-catalog.instructure.com"
CONFIG_DIRECTORY = Path.home() / ".config"
CONFIG_PATH = CONFIG_DIRECTORY / "penn-canvas"
COMMAND_DIRECTORY_BASE = Path.home() / "penn-canvas"
TODAY = datetime.now().strftime("%d_%b_%Y")
TODAY_AS_Y_M_D = datetime.strptime(TODAY, "%d_%b_%Y").strftime("%Y_%m_%d")


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


def make_csv_paths(csv_dir, csv_file, headers):
    if not csv_dir.exists():
        Path.mkdir(csv_dir)

    if not csv_file.is_file():
        with open(csv_file, "w", newline="") as result:
            writer(result).writerow(headers)


def get_command_paths(command, logs=False, processed=False, input_dir=False):
    COMMAND_DIRECTORY = COMMAND_DIRECTORY_BASE / f"{command}"
    input_name = "input" if input_dir else "reports"
    REPORTS = COMMAND_DIRECTORY / input_name
    RESULTS = COMMAND_DIRECTORY / "results"
    LOGS = COMMAND_DIRECTORY / "logs"
    PROCESSED = COMMAND_DIRECTORY / "processed"

    PATHS = [REPORTS, RESULTS]

    if logs:
        PATHS.append(LOGS)

    if processed:
        PATHS.append(PROCESSED)

    return tuple(PATHS)


def check_previous_output(result_path):
    echo(") Checking for previous results...")

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
            colorize("TASK ALREADY COMPLETE", "yellow", True)
            result_path_display = colorize(result_path, "green")
            echo(f"- Output available at: {result_path_display}")
            echo(
                "- To re-run the task, overwriting previous results, run this command"
                " with the '--force' option"
            )
            colorize("FINISHED", "yellow", True)

            raise Exit()
    else:
        index = 0

    return index


def get_start_index(force, result_path):
    if force:
        if result_path.exists():
            remove(result_path)

        return 0
    else:
        return check_previous_output(result_path)


def make_skip_message(start, item):
    if start == 0:
        return
    elif start == 1:
        item = f"{item.upper()}"
    else:
        item = f"{item.upper()}S"

    message = colorize(f"SKIPPING {start} PREVIOUSLY PROCESSED {item}...", "yellow")
    echo(f") {message}")


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


def find_sub_accounts(canvas, account_id):
    ACCOUNT = canvas.get_account(account_id)
    sub_accounts = ACCOUNT.get_subaccounts(recursive=True)
    ACCOUNTS = [account_id]

    for account in sub_accounts:
        ACCOUNTS.append(account.id)

    return ACCOUNTS


def colorize(text, color="magenta", echo=False):
    typer_colors = {
        "blue": colors.BLUE,
        "cyan": colors.CYAN,
        "green": colors.GREEN,
        "magenta": colors.MAGENTA,
        "red": colors.RED,
        "yellow": colors.YELLOW,
    }

    if echo:
        return secho(str(text), fg=typer_colors[color])
    else:
        return style(str(text), fg=typer_colors[color])


def toggle_progress_bar(data, callback, canvas, verbose, args):
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
