from csv import writer
from json import dumps

from requests import get

from penn_canvas.config import get_penn_canvas_config

from .helpers import get_canvas

TESTING = False
course_id = 1569010
course_date = "2021-02-11"
canvas = get_canvas(TESTING)
course = canvas.get_course(course_id)
students = course.get_users()
canvas_prod_key = get_penn_canvas_config("canvas_keys")[0]
headers = {"Authorization": "Bearer %s" % canvas_prod_key}
outputFile = "data/{0}_{1}.csv".format(course_id, course_date)
output = writer(open(outputFile, "w+", newline=""))

for s in students:
    user = s.id

    last_page = False

    url = (
        "https://canvas.upenn.edu/api/v1/users/{0}/page_views?start_time={1}T00:00:00Z"
        "&end_time={1}T23:59:59Z&per_page=100".format(user, course_date)
    )

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

    while not last_page:

        response = get(url, headers=headers)
        r = response.json()

        print(response.url)
        print(dumps(r))

        links = response.links
        print(links)

        print("\n ~~~~~~~PAGE VIEWS~~~~~~~ \n")
        data = r

        for row in data:
            output.writerow(row.values())

        last_page = True

        if "next" in links.keys():
            url = links["next"]["url"]
            print(url)

            last_page = False
