from csv import writer
from pathlib import Path

import pandas
import typer
from canvasapi import Canvas

CANVAS_URL_PROD = "https://canvas.upenn.edu/"
CANVAS_URL_TEST = "https://upenn.test.instructure.com/"
CANVAS_URL_OPEN = "https://upenn-catalog.instructure.com/"
CONFIG_DIR = Path.home() / ".config"
CONFIG_PATH = CONFIG_DIR / "penn-canvas"


def make_config():
    if not CONFIG_DIR.exists():
        Path.mkdir(CONFIG_DIR, parents=True)

    production = typer.prompt(
        "Please enter your Access Token for the PRODUCTION instance of Penn Canvas"
    )
    development = typer.prompt(
        "Please enter your Access Token for the TEST instance of Penn Canvas"
    )
    open_canvas = typer.prompt("Please enter your Access Token for OPEN Canvas")

    with open(CONFIG_PATH, "w+") as config:
        config.write(f"CANVAS_KEY_PROD={production}")
        config.write(f"\nCANVAS_KEY_DEV={development}")
        config.write(f"\nCANVAS_KEY_OPEN={open_canvas}")


def display_config():
    production, development, open_canvas = check_config(CONFIG_PATH)

    production = typer.style(f"{production}", fg=typer.colors.YELLOW)
    development = typer.style(f"{development}", fg=typer.colors.YELLOW)
    open_canvas = typer.style(f"{open_canvas}", fg=typer.colors.YELLOW)

    typer.echo(
        f"\nCANVAS_KEY_PROD: {production}"
        f"\nCANVAS_KEY_DEV: {development}"
        f"\nCANVAS_KEY_OPEN: {open_canvas}"
    )


def check_config(config):
    typer.echo(") Reading Canvas Access Tokens from config file...")

    if not config.exists():
        error = typer.style(
            "- ERROR: No config file ($HOME/.config/penn-canvas) exists for"
            " Penn-Canvas.",
            fg=typer.colors.YELLOW,
        )
        create = typer.confirm(f"{error} \n- Would you like to create one?")

        if not create:
            typer.echo(
                ") Not creating...\n"
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

    if config.is_file():
        with open(CONFIG_PATH, "r") as config:
            lines = config.read().splitlines()
            production = lines[0].replace("CANVAS_KEY_PROD=", "")
            development = lines[1].replace("CANVAS_KEY_DEV=", "")
            open_canvas = lines[2].replace("CANVAS_KEY_OPEN=", "")

        return production, development, open_canvas


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


def get_canvas(instance):
    production, development, open_canvas = check_config(CONFIG_PATH)

    if instance == "prod":
        url = CANVAS_URL_PROD
        access_token = production
    elif instance == "test":
        url = CANVAS_URL_TEST
        access_token = development
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


def colorize(text):
    return typer.style(text, fg=typer.colors.MAGENTA)


def colorize_path(text):
    return typer.style(text, fg=typer.colors.GREEN)
