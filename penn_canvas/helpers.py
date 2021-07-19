from csv import writer
from pathlib import Path

import cx_Oracle
import pandas
import typer
from canvasapi import Canvas

CANVAS_URL_PROD = "https://canvas.upenn.edu/"
CANVAS_URL_TEST = "https://upenn.test.instructure.com/"
CANVAS_URL_OPEN = "https://upenn-catalog.instructure.com/"
CONFIG_DIR = Path.home() / ".config"
CONFIG_PATH = CONFIG_DIR / "penn-canvas"

lib_dir = Path.home() / "Downloads/instantclient_19_8"
config_dir = lib_dir / "network/admin"
cx_Oracle.init_oracle_client(
    lib_dir=str(lib_dir),
    config_dir=str(config_dir),
)


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

    use_production = typer.confirm("Input an Access Token for PRODUCTION?")

    if use_production:
        production = typer.prompt(
            "Please enter your Access Token for the PRODUCTION instance of Penn Canvas"
        )

    use_development = typer.confirm("Input an Access Token for DEVELOPMENT?")

    if use_development:
        development = typer.prompt(
            "Please enter your Access Token for the TEST instance of Penn Canvas"
        )

    use_open = typer.confirm("Input an Access Token for OPEN canvas?")

    if use_open:
        open_canvas = typer.prompt("Please enter your Access Token for OPEN Canvas")

    use_data_warehouse = typer.confirm(
        "Input DSN and connection credentials for DATA WAREHOUSE?"
    )

    if use_data_warehouse:
        data_warehouse_user = typer.prompt("Please enter your DATA WAREHOUSE USER")
        data_warehouse_password = typer.prompt(
            "Please enter your DATA WAREHOUSE PASSWORD"
        )
        data_warehouse_dsn = typer.prompt("Please enter your DATA WAREHOUSE DSN")

    with open(CONFIG_PATH, "w+") as config:
        config.write(f"CANVAS_KEY_PROD={production}")
        config.write(f"\nCANVAS_KEY_DEV={development}")
        config.write(f"\nCANVAS_KEY_OPEN={open_canvas}")
        config.write(f"\nDATA_WAREHOUSE_USER={data_warehouse_user}")
        config.write(f"\nDATA_WAREHOUSE_PASSWORD={data_warehouse_password}")
        config.write(f"\nDATA_WAREHOUSE_DSN={data_warehouse_dsn}")


def display_config():
    (
        production,
        development,
        open_canvas,
        data_warehouse_user,
        data_warehouse_password,
        data_warehouse_dsn,
    ) = check_config(CONFIG_PATH)

    production = typer.style(f"{production}", fg=typer.colors.YELLOW)
    development = typer.style(f"{development}", fg=typer.colors.YELLOW)
    open_canvas = typer.style(f"{open_canvas}", fg=typer.colors.YELLOW)
    data_warehouse_user = typer.style(f"{data_warehouse_user}", fg=typer.colors.YELLOW)
    data_warehouse_password = typer.style(
        f"{data_warehouse_password}", fg=typer.colors.YELLOW
    )
    data_warehouse_dsn = typer.style(f"{data_warehouse_dsn}", fg=typer.colors.YELLOW)
    config_path = typer.style(f"{CONFIG_PATH}", fg=typer.colors.GREEN)

    typer.echo(
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
        error = typer.style(
            "- ERROR: No config file ($HOME/.config/penn-canvas) exists for"
            " Penn-Canvas.",
            fg=typer.colors.YELLOW,
        )
        create = typer.confirm(f"{error} \n- Would you like to create one?")

        if not create:
            typer.echo(
                ") NOT creating...\n"
                "- Please create a config file at: $HOME/.config/penn-canvas"
                "\n- Place your Canvas Access Tokens in this file using the following"
                " format:"
                "\n\tCANVAS_KEY_PROD=your-canvas-prod-key-here"
                "\n\tCANVAS_KEY_DEV=your-canvas-test-key-here"
                "\n\tCANVAS_KEY_OPEN=your-open-canvas-key-here"
            )
            raise typer.Abort()
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


def get_command_paths(command, logs=False, input_dir=False):
    COMMAND_DIRECTORY = Path.home() / f"penn-canvas/{command}"
    input_name = "input" if input_dir else "reports"
    REPORTS = COMMAND_DIRECTORY / input_name
    RESULTS = COMMAND_DIRECTORY / "results"
    LOGS = COMMAND_DIRECTORY / "logs"

    if logs:
        return REPORTS, RESULTS, LOGS
    else:
        return REPORTS, RESULTS


def check_previous_output(result_path):
    typer.echo(") Checking for previous results...")

    if result_path.is_file():
        INCOMPLETE = pandas.read_csv(result_path)

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
            index = 0
    else:
        index = 0

    return index


def check_if_complete(start, total):
    if start > total:
        typer.secho("TASK ALREADY COMPLETE FOR CURRENT PERIOD", fg=typer.colors.YELLOW)
        typer.echo(
            "- To re-run the task, overwriting previous results, run this command with"
            " the '--force' option"
        )

        raise typer.Exit(1)


def toggle_progress_bar(data, callback, canvas, verbose, args=None, index=False):
    def verbose_mode():
        for item in data.itertuples(index=index):
            callback(item, canvas, verbose)

    def verbose_mode_with_args():
        for item in data.itertuples(index=index):
            callback(item, canvas, verbose, args)

    def progress_bar_mode():
        with typer.progressbar(
            data.itertuples(index=index), length=len(data.index)
        ) as progress:
            for item in progress:
                callback(item, canvas, verbose)

    def progress_bar_mode_with_args():
        with typer.progressbar(
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
    typer.echo(") Reading Canvas Access Tokens from config file...")

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


def get_data_warehouse_cursor():
    typer.echo(") Reading Data Warehouse DSN and credentials from config file...")

    user, password, dsn = check_config(CONFIG_PATH)[3:]
    connection = cx_Oracle.connect(user, password, dsn)

    return connection.cursor()


def find_sub_accounts(canvas, account_id):
    ACCOUNT = canvas.get_account(account_id)
    sub_accounts = ACCOUNT.get_subaccounts(recursive=True)
    ACCOUNTS = [account_id]

    for account in sub_accounts:
        ACCOUNTS.append(account.id)

    return ACCOUNTS


def colorize(text):
    return typer.style(text, fg=typer.colors.MAGENTA)


def colorize_path(text):
    return typer.style(text, fg=typer.colors.GREEN)
