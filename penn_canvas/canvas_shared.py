from pathlib import Path

import typer
from canvasapi import Canvas

CANVAS_URL_PROD = "https://canvas.upenn.edu/"
CANVAS_URL_TEST = "https://upenn.test.instructure.com/"
CONFIG_DIR = Path.home() / ".config"
CONFIG_PATH = CONFIG_DIR / "penn-canvas.txt"


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
    if not config.exists():
        create = typer.confirm(
            "\t- No config file ($HOME/.config/.penn-canvas) exists for Penn-Canvas. Would you like to create one?"
        )
        if not create:
            typer.echo("\n) Not creating...")
            typer.echo("\tPlease create a config file at: $HOME/.config/.penn-canvas")
            typer.echo(
                "\tPlace your Canvas Access Tokens in this file using the following format:"
            )
            typer.echo("\t\tCANVAS_KEY_PROD=your-canvas-prod-key-here")
            typer.echo("\t\tCANVAS_KEY_DEV=your-canvas-test-key-here")
            raise typer.Abort()
        else:
            make_config()
    if config.is_file():
        with open(CONFIG_PATH, "r") as config:
            lines = config.read().splitlines()
            production = lines[0].replace("CANVAS_KEY_PROD=", "")
            development = lines[1].replace("CANVAS_KEY_DEV=", "")
        return production, development


def get_command_paths(command, logs):
    COMMAND_DIRECTORY = Path.home() / f"penn-canvas/{command}"
    REPORTS = COMMAND_DIRECTORY / "reports"
    RESULTS = COMMAND_DIRECTORY / "results"
    LOGS = COMMAND_DIRECTORY / "logs"
    if logs:
        return REPORTS, RESULTS, LOGS
    else:
        return REPORTS, RESULTS


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


def code_to_sis(course_code):
    middle = course_code[:-5][-6:]

    return f"SRS_{course_code[:11]}-{middle[:3]}-{middle[3:]} {course_code[-5:]}"


def WH_linked_to_SRS(canvas, canvas_id):
    course = canvas.get_course(canvas_id)
    sections = course.get_sections()

    for s in sections:
        try:
            if s.sis_section_id.startswith("SRS_"):
                return True
        except:
            pass
    return False


def linked_to_SRS(course_id):
    return course_id.startswith("SRS_")
