from configparser import ConfigParser
from itertools import chain
from pathlib import Path
from typing import Optional

from loguru import logger
from typer import Exit, confirm, echo, prompt

from .helpers import BASE_PATH, create_directory, switch_logger_file
from .style import color

CONFIG_DIRECTORY = create_directory(Path.home() / ".config" / "penn-canvas")
LOGS = create_directory(BASE_PATH / "Logs")
CONFIG_FILE = CONFIG_DIRECTORY / "penn-canvas.ini"
CONFIG_OPTIONS = {
    "canvas_urls": [
        "canvas_prod_url",
        "canvas_test_url",
        "canvas_beta_url",
        "open_canvas_prod_url",
        "open_canvas_test_url",
        "open_canvas_beta_url",
    ],
    "canvas_keys": [
        "canvas_prod_key",
        "canvas_test_key",
        "canvas_beta_key",
        "open_canvas_prod_key",
        "open_canvas_test_key",
        "open_canvas_beta_key",
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
SECRET_OPTIONS.append(CONFIG_OPTIONS["email"][1])

Section = Option = Value = str
OptionAndValue = tuple[Value, Option]


def get_config_option(section: Section, option: Option) -> Option:
    config = ConfigParser()
    try:
        config.read(CONFIG_FILE)
        option = config.get(section, option)
    except Exception as error:
        echo(error)
        logger.warning(error)
        get_new_config_value(section, option, first_time=True)
    return option


def get_section_options(
    section: Section, with_option_name=False
) -> list[Value] | list[OptionAndValue]:
    config = ConfigParser()
    config.read(CONFIG_FILE)
    try:
        required_options = set(CONFIG_OPTIONS.get(section, list()))
        options = config.options(section)
        new_options = required_options ^ set(options)
        if new_options:
            values = [
                (option, get_new_config_value(section, option, first_time=True))
                for option in new_options
            ]
            for option, value in values:
                write_config_option(config, section, option, value)
            with open(CONFIG_FILE, "w") as config_file:
                config.write(config_file)
            options = config.options(section)
        if with_option_name:
            return [(option, config.get(section, option)) for option in options]
        else:
            return [config.get(section, option) for option in options]
    except Exception as error:
        echo(error)
        logger.warning(error)
        write_config_options(new_section=section)
        return get_section_options(section, with_option_name)


def get_all_config_options(with_option_name=False) -> list[Value | OptionAndValue]:
    keys = CONFIG_OPTIONS.keys()
    options = [get_section_options(section, with_option_name) for section in keys]
    return list(chain.from_iterable(options))


def get_new_config_value(section: Section, option: Option, first_time: bool) -> Value:
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


def get_new_config_values(section: Section, first_time: bool) -> list[OptionAndValue]:
    return [
        (option, get_new_config_value(section, option, first_time))
        for option in CONFIG_OPTIONS[section]
    ]


def get_new_section_values(section: Section, first_time: bool) -> list[OptionAndValue]:
    get_new_values = first_time or confirm(
        f"Would you like to update the {section.replace('_', ' ').upper()} config"
        " values?"
    )
    return get_new_config_values(section, first_time) if get_new_values else []


def write_config_option(
    config: ConfigParser, section: Section, option: Option, value: Value
):
    config[section][option] = value


def write_config_section(
    config: ConfigParser, section: Section, first_time: bool
) -> ConfigParser:
    new_values = get_new_section_values(section, first_time)
    if first_time:
        config[section] = dict()
    for option, value in new_values:
        if value is not None:
            write_config_option(config, section, option, value)
    return config


def write_config_options(
    first_time=False, new_section: Optional[Section] = None
) -> list[Value | OptionAndValue]:
    config = ConfigParser()
    if not first_time:
        config.read(CONFIG_FILE)
    if new_section:
        config = write_config_section(config, new_section, first_time=True)
    else:
        for section in CONFIG_OPTIONS.keys():
            config = write_config_section(config, section, first_time)
    with open(CONFIG_FILE, "w") as config_file:
        config.write(config_file)
    return get_all_config_options()


def confirm_create_config() -> Optional[list[Value | OptionAndValue]]:
    if confirm("Config file not found. Would you like to create one now?"):
        return write_config_options(first_time=True)
    else:
        echo(
            f"A config file is required. Please create one at {CONFIG_FILE} and try"
            " again."
        )


def get_config(
    section: Optional[Section], with_option_name: bool
) -> list[Value] | list[OptionAndValue] | list[Value | OptionAndValue]:
    if section:
        return get_section_options(section, with_option_name)
    else:
        return get_all_config_options(with_option_name)


def get_penn_canvas_config(
    section: Optional[Section] = None, with_option_name=False
) -> list[Value] | list[OptionAndValue] | list[Value | OptionAndValue]:
    config = (
        get_config(section, with_option_name)
        if CONFIG_FILE.is_file()
        else confirm_create_config()
    )
    if not config:
        raise Exit(1)
    return config


def print_config(show_secrets: bool):
    switch_logger_file(LOGS, "config")
    for option, value in get_penn_canvas_config(with_option_name=True):
        if not value:
            value = color("[ empty ]", "yellow")
        elif not show_secrets and option in SECRET_OPTIONS:
            value = color("[ ...hidden... ]", "yellow")
        else:
            value = color(value, "green")
        echo(f"{color(option.replace('_', ' ').upper())}: {value}")


def get_email_credentials() -> list[Value] | list[OptionAndValue]:
    return get_section_options("email")
