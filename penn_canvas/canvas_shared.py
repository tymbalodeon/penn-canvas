from canvasapi import Canvas
from pathlib import Path
import typer

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
    test = typer.prompt(
        "Please enter your Access Token for the TEST instance of Penn Canvas"
    )
    with open(CONFIG_PATH, "w+") as config:
        config.write(f"CANVAS_KEY_PROD={production}")
        config.write(f"\nCANVAS_KEY_TEST={test}")


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
            typer.echo("\t\tCANVAS_KEY_TEST=your-canvas-test-key-here")
            raise typer.Abort()
        else:
            make_config()
    if config.is_file():
        with open(CONFIG_PATH, "r") as config:
            lines = config.read().splitlines()
            production = lines[0].replace("CANVAS_KEY_PROD=", "")
            test = lines[1].replace("CANVAS_KEY_TEST=", "")
        return production, test


def get_canvas(test):
    production, test = check_config(CONFIG_PATH)
    return Canvas(
        CANVAS_URL_TEST if test else CANVAS_URL_PROD,
        test if test else production,
    )


def find_accounts_subaccounts(canvas, account_id):
    subs_list = [account_id]
    account = canvas.get_account(account_id)
    subs = account.get_subaccounts(recursive=True)

    for sub in subs:
        subs_list += [sub.id]
    return subs_list


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
