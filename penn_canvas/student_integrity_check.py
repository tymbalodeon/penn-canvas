import csv
import json

import requests
from canvas_shared import API_KEY_PROD, get_canvas

# baowei@upenn.edu
# 1/20/2021: check the page views of three students (5608161, 5484129, 5608478) between 9/1/2020 and 12/23/2020

headers = {"Authorization": "Bearer %s" % API_KEY_PROD}

last_page = False
users = ["5608161", "5484129", "5608478"]
start_time = "2020-09-01T00:00:00Z"
end_time = "2020-12-24T00:00:00Z"

for user in users:
    url = (
        "https://canvas.upenn.edu/api/v1/users/"
        + user
        + "/page_views?"
        + "start_time="
        + start_time
        + "&per_page=100"
    )

    outputFile = "Student_Activity_User_%s.csv" % user
    output = csv.writer(open(outputFile, "w+", newline=""))

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

        response = requests.get(url, headers=headers)
        r = response.json()

        print(response.url)
        print(json.dumps(r))

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
