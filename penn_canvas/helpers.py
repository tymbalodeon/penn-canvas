from csv import writer
from pathlib import Path

import typer
from canvasapi import Canvas

CANVAS_URL_PROD = "https://canvas.upenn.edu/"
CANVAS_URL_TEST = "https://upenn.test.instructure.com/"
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
    with open(CONFIG_PATH, "w+") as config:
        config.write(f"CANVAS_KEY_PROD={production}")
        config.write(f"\nCANVAS_KEY_DEV={development}")


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
            )
            raise typer.Abort()
        else:
            make_config()
    if config.is_file():
        with open(CONFIG_PATH, "r") as config:
            lines = config.read().splitlines()
            production = lines[0].replace("CANVAS_KEY_PROD=", "")
            development = lines[1].replace("CANVAS_KEY_DEV=", "")
        return production, development


def make_csv_paths(csv_dir, csv_file, headers):
    if not csv_dir.exists():
        Path.mkdir(csv_dir)
    if not csv_file.is_file():
        with open(csv_file, "w", newline="") as result:
            writer(result).writerow(headers)


def get_command_paths(command, logs=False):
    COMMAND_DIRECTORY = Path.home() / f"penn-canvas/{command}"
    REPORTS = COMMAND_DIRECTORY / "reports"
    RESULTS = COMMAND_DIRECTORY / "results"
    LOGS = COMMAND_DIRECTORY / "logs"
    if logs:
        return REPORTS, RESULTS, LOGS
    else:
        return REPORTS, RESULTS


def toggle_progress_bar(data, callback, canvas, verbose, options=None, index=False):
    def verbose_mode():
        for item in data.itertuples(index=index):
            callback(item, canvas, verbose)

    def verbose_mode_with_options():
        for item in data.itertuples(index=index):
            callback(item, canvas, verbose, options)

    def progress_bar_mode():
        with typer.progressbar(
            data.itertuples(index=index), length=len(data.index)
        ) as progress:
            for item in progress:
                callback(item, canvas, verbose)

    def progress_bar_mode_with_options():
        with typer.progressbar(
            data.itertuples(index=index), length=len(data.index)
        ) as progress:
            for item in progress:
                callback(item, canvas, verbose, options)

    if verbose:
        if options:
            verbose_mode_with_options()
        else:
            verbose_mode()
    else:
        if options:
            progress_bar_mode_with_options()
        else:
            progress_bar_mode()


def get_canvas(test):
    production, development = check_config(CONFIG_PATH)
    return Canvas(
        CANVAS_URL_TEST if test else CANVAS_URL_PROD,
        development if test else production,
    )


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
