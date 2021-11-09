# Penn Canvas

A command line tool for working with Penn's Canvas instances.

## Makefile

A Makefile is provided with aliases to common commands.

_This README uses these aliases. Actual commands can be seen in the Makefile itself._

- To install "make" on MacOS: `xcode-select --install`

## Installation & Setup

NOTE: This project is intended to be developed and built using
[poetry](https://python-poetry.org/).

1. `poetry install`
2. `make build`

The `penn-canvas` command will then be globally available in your shell.

### Development

Code changes can be tested quickly without having to build the app by running:

> `make try args=[ARGS]`

### Non-Poetry

A "requirements.txt" file is also included for non-Poetry installation.
Instructions for developing without Poetry are not currently available.

To "freeze" the dependencies to the requirements file via Poetry, run:

> `make freeze`

### Configuration

#### Access Tokens

Access Tokens are required to connect to Canvas. You will need a separate one
for [production](https://canvas.upenn.edu/),
[test](https://upenn.test.instructure.com/) and [OpenCanvas](https://upenn-catalog.instructure.com/) regions.

To generate tokens, login to your Canvas account, go to Account > Settings, and
click the "New Access Token" button under the "Approved Integrations" heading.
Enter a description in the 'Purpose' field and click 'Generate Token'. Store
these tokens in Penn Canvas' config file (see below).

#### Data Warehouse

If using the "nso" command, you will also need to set up a connection to Penn's
Data Warehouse:

1. Install [Oracle InstantClient](https://www.oracle.com/database/technologies/instant-client/downloads.html)
   for your platform
2. Create a "tnsnames.ora" file in your Oracle Instant Client's "network/admin"
   directory, using values provided by the Courseware team
3. Acquire the Courseware team's Data Warehouse username and password and store
   in Penn Canvas' config file (see below)
4. Make sure you are connected to Penn's [GlobalProtectVPN](https://www.isc.upenn.edu/how-to/university-vpn-getting-started-guide)

#### Config

A config file containing your Canvas and Data Warehouse credentials is required
for running the commands. A config file can be generated for you by running
`penn-canvas config`. You will be prompted to input values for each item you
wish to add (you will be given a chance to skip items you are not using them).
Input will not be displayed on screen. If you try to run another command without
a config file, you will also be prompted to generate one before proceeding. You
can update your config later by running `penn-canvas config --update`.

##### View

If you need to quickly check the values of your config file, you can run
`penn-canvas config --view`, which will display all the current values on screen
(you will be asked to confirm that you wish to display sensitive information on
screen).

## Usage

Basic format: `penn-canvas [OPTIONS] COMMAND [ARGS]`

Documentation is provided in the CLI itself.

To see available commands: `penn-canvas --help`

To see detailed information for a particular command: `penn-canvas COMMAND --help`
