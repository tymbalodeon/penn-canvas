from requests import get

from .config import get_config_option
from .helpers import MAIN_ACCOUNT_ID

emails = []
prod_key = get_config_option("canvas_keys", "canvas_prod_key")
open_key = get_config_option("canvas_keys", "open_canvas_prod_key")
prod_base_url = get_config_option("canvas_urls", "canvas_prod_url")
open_base_url = get_config_option("canvas_urls", "open_canvas_url")
prod_headers = {"Authorization": f"Bearer {prod_key}"}
open_headers = {"Authorization": f"Bearer {open_key}"}


def find_users_by_email():
    for url, headers, account_id in [
        (prod_base_url, prod_headers, MAIN_ACCOUNT_ID),
        (open_base_url, open_headers, 1),
    ]:
        print("PROD" if url == prod_base_url else "OPEN")
        for email in emails:
            search_url = f"{url}api/v1/accounts/{account_id}/users?search_term={email}"
            response = get(search_url, headers=headers).json()
            if response:
                response = response[0]
                print(
                    f"{email}, {response['id']}, {response['name']},"
                    f" {response['login_id']}"
                )
            else:
                print(email, response)
