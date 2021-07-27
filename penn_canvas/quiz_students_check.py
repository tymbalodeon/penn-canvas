from csv import writer
from json import dumps

from requests import get

from .helpers import API_KEY_PROD, API_KEY_TEST, get_canvas, make_data_dir

TESTING = False

course_id = 1569010
course_date = "2021-02-11"
canvas = get_canvas(TESTING)

course = canvas.get_course(course_id)
students = course.get_users()

use_API_KEY = API_KEY_TEST if TESTING else API_KEY_PROD

headers = {"Authorization": "Bearer %s" % use_API_KEY}
outputFile = "data/{0}_{1}.csv".format(course_id, course_date)

try:
    output = writer(open(outputFile, "w+", newline=""))
except FileNotFoundError:
    make_data_dir()
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
            # if course_id in row['url']: #or course_id == row[-2]['context']:
            output.writerow(row.values())  # values row

        last_page = True

        if "next" in links.keys():
            url = links["next"]["url"]
            print(url)

            last_page = False
