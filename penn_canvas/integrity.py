import csv

import requests

from .helpers import API_KEY_PROD

headers = {"Authorization": f"Bearer {API_KEY_PROD}"}


def check_user(user, start):
    url = f"https://canvas.upenn.edu/api/v1/users/{user}/page_views?start_time={start}&per_page=100"
    result = f"Student_Activity_User_{user}.csv"
    output = csv.writer(open(result, "w+", newline=""))

    output.writerow(
        [
            "session_id",
            "url",
            "context_type",
            "asset_type",
            "controller",
            "action",
            "interaction_seconds",
            "created_at",
            "updated_at",
            "developer_key_id",
            "user_request",
            "render_time",
            "user_agent",
            "asset_user_access_id",
            "participated",
            "summarized",
            "http_method",
            "remote_ip",
            "id",
            "contributed",
            "links",
            "app_name",
        ]
    )

    last_page = False

    while not last_page:
        response = requests.get(url, headers=headers)
        response_json = response.json()
        links = response.links

        for row in response_json:
            output.writerow(row.values())

        if "next" in links.keys():
            url = links["next"]["url"]
            last_page = False
        else:
            last_page = True


def integrity_main(test, users, start, end):
    for user in users:
        check_user(user, start)
