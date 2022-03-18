from configparser import ConfigParser
from itertools import chain
from pathlib import Path

from loguru import logger
from typer import Exit, confirm, echo, prompt

from penn_canvas.helpers import BASE_PATH, create_directory, switch_logger_file

from .style import color

CONFIG_DIRECTORY = create_directory(Path.home() / ".config" / "penn-canvas")
LOGS = create_directory(BASE_PATH / "Logs")
CONFIG_FILE = CONFIG_DIRECTORY / "penn-canvas.ini"
CONFIG_OPTIONS = {
    "canvas_urls": [
        "canvas_prod_url",
        "canvas_test_url",
        "canvas_beta_url",
        "open_canvas_url",
        "open_canvas_test_url",
    ],
    "canvas_keys": [
        "canvas_prod_key",
        "canvas_test_key",
        "canvas_beta_key",
        "open_canvas_prod_key",
        "open_canvas_test_key",
    ],
    "data_warehouse": [
        "data_warehouse_user",
        "data_warehouse_password",
        "data_warehouse_dsn",
    ],
    "email": ["address", "password"],
}
SECRET_OPTIONS = CONFIG_OPTIONS["canvas_keys"][:]
SECRET_OPTIONS.append(CONFIG_OPTIONS["data_warehouse"][1])


def create_config_directory():
    if not CONFIG_DIRECTORY.exists():
        Path.mkdir(CONFIG_DIRECTORY, parents=True)


def get_config_directory():
    create_config_directory()
    return CONFIG_DIRECTORY


def get_config_option(section, option):
    config = ConfigParser()
    config.read(CONFIG_FILE)
    return config.get(section, option)


def get_section_options(section):
    config = ConfigParser()
    config.read(CONFIG_FILE)
    return [config.get(section, option) for option in config.options(section)]


def get_section_options_as_tuple(section):
    config = ConfigParser()
    config.read(CONFIG_FILE)
    return [(option, config.get(section, option)) for option in config.options(section)]


def get_all_config_options():
    return list(
        chain.from_iterable(
            [get_section_options(section) for section in CONFIG_OPTIONS.keys()]
        )
    )


def get_all_config_options_as_tuple():
    return list(
        chain.from_iterable(
            [
                (get_section_options_as_tuple(section))
                for section in CONFIG_OPTIONS.keys()
            ]
        )
    )


def get_new_config_value(section, option, first_time):
    option_display = option.replace("_", " ").upper()
    confirm_message = f"Would you like to update the {option_display} value?"
    prompt_message = f"Please provide your {option_display} value"
    updating = first_time or confirm(confirm_message)
    hide_input = option in SECRET_OPTIONS
    return (
        prompt(prompt_message, hide_input=hide_input, default="", show_default=False)
        if updating
        else get_config_option(section, option)
    )


def get_new_config_values(section, first_time):
    return [
        (option, get_new_config_value(section, option, first_time))
        for option in CONFIG_OPTIONS[section]
    ]


def get_new_section_values(section, first_time):
    get_new_values = first_time or confirm(
        f"Would you like to update the {section.replace('_', ' ').upper()} config"
        " values?"
    )
    return get_new_config_values(section, first_time) if get_new_values else []


def write_config_options(first_time=False):
    create_config_directory()
    config = ConfigParser()
    if not first_time:
        config.read(CONFIG_FILE)
    for section in CONFIG_OPTIONS.keys():
        new_values = get_new_section_values(section, first_time)
        if first_time:
            config[section] = dict()
        for option, value in new_values:
            if value is not None:
                config[section][option] = value
    with open(CONFIG_FILE, "w") as config_file:
        config.write(config_file)
    return get_all_config_options()


def print_create_config_message():
    echo(
        f"A config file is required. Please create one at {CONFIG_FILE} and try again."
    )


def confirm_create_config():
    return (
        write_config_options(first_time=True)
        if confirm("Config file not found. Would you like to create one now?")
        else print_create_config_message()
    )


def get_config(section, as_tuple):
    return (
        (
            get_section_options_as_tuple(section)
            if section
            else get_all_config_options_as_tuple()
        )
        if as_tuple
        else (get_section_options(section) if section else get_all_config_options())
    )


def get_penn_canvas_config(section=None, as_tuple=False):
    config = (
        get_config(section, as_tuple)
        if CONFIG_FILE.is_file()
        else confirm_create_config()
    )
    if not config:
        raise Exit(1)
    return config


@logger.catch
def print_config(show_secrets):
    switch_logger_file(LOGS / "config_{time}.log")
    for option, value in get_penn_canvas_config(as_tuple=True):
        if not value:
            value = color("[ empty ]", "yellow")
        elif not show_secrets and option in SECRET_OPTIONS:
            value = color("[ ...hidden... ]", "yellow")
        else:
            value = color(value, "green")
        echo(f"{color(option.replace('_', ' ').upper())}: {value}")
