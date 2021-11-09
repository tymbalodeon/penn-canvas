from csv import writer

from requests import get

from penn_canvas.config import get_penn_canvas_config

CANVAS_URL_PROD = get_penn_canvas_config("canvas_urls")[0]


def check_user(user, start, key):
    headers = {"Authorization": f"Bearer {key}"}
    url = (
        f"{CANVAS_URL_PROD}/api/v1/users/{user}/"
        f"page_views?start_time={start}&per_page=100"
    )
    result = f"Student_Activity_User_{user}.csv"
    output = writer(open(result, "w+", newline=""))

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
        response = get(url, headers=headers)
        response_json = response.json()
        links = response.links

        for row in response_json:
            output.writerow(row.values())

        if "next" in links.keys():
            url = links["next"]["url"]
            last_page = False
        else:
            last_page = True


def integrity_main(test, users, start):
    production, development = get_penn_canvas_config("canvas_keys")[:2]
    key = production if not test else development

    for user in users:
        check_user(user, start, key)
