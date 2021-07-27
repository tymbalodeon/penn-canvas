from csv import writer
from os import remove
from pathlib import Path

from canvasapi import Canvas
from pandas import read_csv
from typer import Abort, Exit, colors, confirm, echo, progressbar, prompt, secho, style

CANVAS_URL_PROD = "https://canvas.upenn.edu"
CANVAS_URL_TEST = "https://upenn.test.instructure.com"
CANVAS_URL_OPEN = "https://upenn-catalog.instructure.com"
CONFIG_DIR = Path.home() / ".config"
CONFIG_PATH = CONFIG_DIR / "penn-canvas"


def make_config():
    if not CONFIG_DIR.exists():
        Path.mkdir(CONFIG_DIR, parents=True)

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
        "This command will display sensitive information on your screen. Are you sure you want to proceed?"
    ):
        (
            production,
            development,
            open_canvas,
            data_warehouse_user,
            data_warehouse_password,
            data_warehouse_dsn,
        ) = check_config(CONFIG_PATH)

        production = style(f"{production}", fg=colors.YELLOW)
        development = style(f"{development}", fg=colors.YELLOW)
        open_canvas = style(f"{open_canvas}", fg=colors.YELLOW)
        data_warehouse_user = style(f"{data_warehouse_user}", fg=colors.YELLOW)
        data_warehouse_password = style(f"{data_warehouse_password}", fg=colors.YELLOW)
        data_warehouse_dsn = style(f"{data_warehouse_dsn}", fg=colors.YELLOW)
        config_path = style(f"{CONFIG_PATH}", fg=colors.GREEN)

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
        error = style(
            "- ERROR: No config file ($HOME/.config/penn-canvas) exists for"
            " Penn-Canvas.",
            fg=colors.YELLOW,
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


def make_csv_paths(csv_dir, csv_file, headers):
    if not csv_dir.exists():
        Path.mkdir(csv_dir)

    if not csv_file.is_file():
        with open(csv_file, "w", newline="") as result:
            writer(result).writerow(headers)


def get_command_paths(command, logs=False, processed=False, input_dir=False):
    COMMAND_DIRECTORY = Path.home() / f"penn-canvas/{command}"
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
            secho("TASK ALREADY COMPLETE", fg=colors.YELLOW)
            result_path_display = style(str(result_path), fg=colors.GREEN)
            echo(f"- Output available at: {result_path_display}")
            echo(
                "- To re-run the task, overwriting previous results, run this command"
                " with the '--force' option"
            )
            secho("FINISHED", fg=colors.YELLOW)

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

    message = style(
        f"SKIPPING {start} PREVIOUSLY PROCESSED {item}...",
        fg=colors.YELLOW,
    )
    echo(f") {message}")


def toggle_progress_bar(data, callback, canvas, verbose, args=None, index=False):
    def verbose_mode():
        for item in data.itertuples(index=index):
            callback(item, canvas, verbose)

    def verbose_mode_with_args():
        for item in data.itertuples(index=index):
            callback(item, canvas, verbose, args)

    def progress_bar_mode():
        with progressbar(
            data.itertuples(index=index), length=len(data.index)
        ) as progress:
            for item in progress:
                callback(item, canvas, verbose)

    def progress_bar_mode_with_args():
        with progressbar(
            data.itertuples(index=index), length=len(data.index)
        ) as progress:
            for item in progress:
                callback(item, canvas, verbose, args)

    if verbose:
        if args:
            verbose_mode_with_args()
        else:
            verbose_mode()
    else:
        if args:
            progress_bar_mode_with_args()
        else:
            progress_bar_mode()


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


def get_data_warehouse_config():
    echo(") Reading Data Warehouse credentials from config file...")

    return check_config(CONFIG_PATH)[3:]


def find_sub_accounts(canvas, account_id):
    ACCOUNT = canvas.get_account(account_id)
    sub_accounts = ACCOUNT.get_subaccounts(recursive=True)
    ACCOUNTS = [account_id]

    for account in sub_accounts:
        ACCOUNTS.append(account.id)

    return ACCOUNTS


def colorize(text):
    return style(text, fg=colors.MAGENTA)


def colorize_path(text):
    return style(text, fg=colors.GREEN)
