# Penn Canvas

A command line tool for working with Penn Canvas

## Installation & Setup

NOTE: This project is intended to be developed and built using [poetry](https://python-poetry.org/).

1. `poetry install`
2. `poetry build`
3. `pip install --user <path-to-.whl-file-in-this-project's-dist-folder>`

The `penn-canvas` command will then be globally available in your shell.

### Non-Poetry

A "requirements.txt" file is also included for non-Poetry installation. Instructions for developing without Poetry are not currently available.

### Access Tokens

Access Tokens are required to connect to Canvas. You will need a separate one for [production](https://canvas.upenn.edu/) and [test](https://upenn.test.instructure.com/) regions.

To generate tokens, login to your Canvas account, go to Account > Settings, and click the "New Access Token" button under the "Approved Integrations" heading.

#### CLI config generator

A config file containing your Access Tokens can be generated for you by Penn-Canvas by calling `penn-canvas configure`. You will be prompted to input your production and test region Access Tokens. (If you try to run another command without a config file, you will also be prompted to generate one before proceeding.)

#### Manual config creation

You may also create your config file manually. Penn-Canvas expects the location to be "$HOME/.config/penn-canvas.txt" and the contents to be:

> CANVAS_KEY_PROD=your-canvas-prod-key-here  
> CANVAS_KEY_TEST=your-canvas-test-key-here

Prepending the keys with "[KEY_NAME]=" is optional, but each token must be on its own line, with the production token first.

## Usage

Basic format: `penn-canvas[OPTIONS] COMMAND [ARGS]`

Documentation is provided in the CLI itself.

To see available commands: `penn-canvas --help` or simply `penn-canvas`

To see detailed information for a particular command: `penn-canvas COMMAND --help`
