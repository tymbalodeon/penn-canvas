# Canvas Scripts

A collection of helpful python scripts for working with UPenn Canvas.

## Installation & Setup

To install dependencies, run `pip install -r requirements.txt` from within your [virtual environment](https://docs.python.org/3/tutorial/venv.html) for this project.

### Access Tokens

Access Tokens are required to connect to Canvas. You will need a separate one for [production](https://canvas.upenn.edu/) and [test](https://upenn.test.instructure.com/) regions.

To generate tokens, login to your Canvas account, go to Account > Settings, and click the "New Access Token" button under the "Approved Integrations" heading.

In order to use these tokens with the scripts, you will need to create a file named ".env" in the root directory of this project and add your keys using the following format:

> CANVAS_KEY_PROD=your-canvas-prod-key-here  
> CANVAS_KEY_TEST=your-canvas-test-key-here

## Usage

Basic format: `python main.py [OPTIONS] COMMAND [ARGS]`

Documentation is provided in the CLI itself.

To see available commands: `python main.py --help`

To see detailed information for a particular command: `python main.py COMMAND --help`
