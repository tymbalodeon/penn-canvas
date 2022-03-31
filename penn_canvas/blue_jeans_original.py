from datetime import datetime
from click.termui import style

import pandas as pd
import requests
from bs4 import BeautifulSoup as bs
from flatten_json import flatten
from pytz import timezone

from .api import get_canvas
from .style import color

pd.set_option("display.max_rows", 200)
pd.set_option("display.max_columns", 200)
# canvas_token = <apitoken> #we source from encrypted AWS Systems Manager values
# API_URL = "https://canvas.upenn.edu"
# API_KEY = canvas_token
bjc_base_url = "https://canvaslms.bluejeansint.com"
# canvas = Canvas(API_URL, API_KEY)


def bluejeans_course_report(term_name="Test", course_id=1635419, course_index=0):
    global df
    canvas = get_canvas()
    course = canvas.get_course(course_id)

    # Setup a way to know when the Courseware team changes Virtual Meetings to BlueJeans
    found_VM = 0
    found_BJ = 0

    print(
        "Fetching {} course index (0-based) {} for {}".format(
            term_name, course_index, course
        )
    )
    # print(course)
    # print(json.dumps(course.attributes, indent=2))
    timestamp_utc = datetime.now().astimezone(timezone("UTC"))
    tabs = course.get_tabs()
    this_course_has_bj_tab = False
    for tab in tabs:
        # print("{} ({})".format(tab.label, tab.id))
        if tab.label in ["Virtual Meetings", "BlueJeans"]:  # ,'Class Recordings']:
            if tab.label == "Virtual Meetings":
                found_VM += 1
            elif tab.label == "BlueJeans":
                found_BJ += 1
            this_course_has_bj_tab = True
            # print(tab.attributes) # tab.attributes['url'] = tab.url for short
            # print('********** Tab url: ********** {}'.format(tab.url))
            # url1 = 'https://canvas.upenn.edu/courses/1534094/external_tools/91180'
            rsp_tab = canvas._Canvas__requester.request("GET", _url=tab.url)
            # print("rsp_tab: {}".format(rsp_tab))
            # print("rsp_tab headers: {}".format(rsp_tab.headers))
            # print("rsp_tab text: {}".format(rsp_tab.text))
            form_url = rsp_tab.json().get("url")
            # tab_session_id = rsp_tab.headers['X-Session-Id']
            # print("rsp_tab session_id: {}".format(tab_session_id))
            # tab_csrf_token = rsp_tab.headers['Set-Cookie'].split(';')[0].split('=')[1]
            # print('rsp_tab CSRF token: {}'.format(tab_csrf_token))

            # print("********** Form url: ********** {}".format(form_url))
            rsp_form = requests.get(form_url)
            # print("rsp_form: {}".format(rsp_form))
            # print("rsp_form headers: {}".format(rsp_form.headers))
            # print("rsp_form text: {}".format(rsp_form.text))
            # print('rsp_form Set-Cookie: {}'.format(rsp_form.headers['Set-Cookie']))
            # form_csrf_token = rsp_form.headers['Set-Cookie'].split(';')[0].split('=')[1]
            # print('rsp_form CSRF token: {}'.format(form_csrf_token))
            # g0209279@upenn.edu
            soup_form = bs(rsp_form.text, "html.parser")
            # Get the form and parse out all of the inputs
            form = soup_form.find("form")
            if not form:
                print("Could not find a form to launch this BJ page, skipping")
                break

            fields = form.findAll("input")
            formdata = dict((field.get("name"), field.get("value")) for field in fields)
            print("\n")
            form_data_text = color("FORM DATA VALUES", "cyan", bold=True)
            print(f"==== {form_data_text} ====")
            for key, value in formdata.items():
                print(f"{key.upper()}: {color(value, 'yellow')}")
            print("\n")

            # Get the URL to post back to
            formpost_url = form.get("action")

            # print("********** Formpost url: ********** {}".format(formpost_url))

            # Initiate the LTI launch to BlueJeans in a session
            # sess_formpost.cookies.set(cookies.keys()[n],cookies.values()[n])
            # sess_formpost.cookies.set(cookies.keys()[n],cookies.values()[n])
            # formpost_url = 'https://static-canvaslms.bluejeans.com/lti/course'
            # rsp_formpost = sess_formpost.post(url=formpost_url, data=formdata, headers=sess_formpost.headers)
            rsp_formpost = requests.request(
                method="post", url=formpost_url, data=formdata, allow_redirects=False
            )  # , headers=sess_formpost.headers)
            # rsp_formpost = sess_formpost.request(method='post', url=formpost_url, data=formdata, headers=sess_formpost.headers, allow_redirects=False)
            # print("rsp_formpost: {}".format(rsp_formpost))
            # print("rsp_formpost headers: {}".format(rsp_formpost.headers))

            post_response_text = color("POST RESPONSE VALUES", "cyan", bold=True)
            print(f"==== {post_response_text} ====")
            for key, value in rsp_formpost.headers.items():
                print(f"{key.upper()}: {color(value, 'yellow')}")
            print("\n")
            try:
                lti_auth_token = (
                    rsp_formpost.headers["Location"].split("&")[0].split("=")[1]
                )
                lti_course_id = (
                    rsp_formpost.headers["Location"].split("&")[2].split("=")[1]
                )
                lti_user_id = (
                    rsp_formpost.headers["Location"].split("&")[3].split("=")[1]
                )
            except Exception:
                print("ERROR getting lti credentials. Skipping...")
                continue
            print(
                "Course: {} User: {} Token: <Don't Print>".format(
                    lti_course_id, lti_user_id
                )
            )  # , lti_auth_token))
            auth_header = {"Authorization": "Bearer {}".format(lti_auth_token)}
            bj_sess = requests.Session()
            bj_sess.headers.update(auth_header)
            # print('********** New API Request Headers: ********** {}'.format(bj_sess.headers))

            url_upc = "https://canvaslms.bluejeansint.com/api/canvas/course/{}/user/{}/conferences?limit=100".format(
                lti_course_id, lti_user_id
            )
            rsp_upc = bj_sess.get(url=url_upc)  # Headers are already in the session
            # print('********** Upcoming URL: ********** {}'.format(url_upc))
            # print('Upcoming Response: {}'.format(rsp_upc))
            # print('Upcoming Response Headers: {}'.format(rsp_upc.headers))
            # print('Upcoming Response Text: {}'.format(rsp_upc.text))
            jsn_upc = rsp_upc.json().get("details")
            for row in range(len(jsn_upc)):
                jsn_upc[row]["mtg_status"] = "upcoming"
            # print('Upcoming JSON Type: {} JSON: {}'.format(type(jsn_upc), jsn_upc))

            url_cur = "https://canvaslms.bluejeansint.com/api/canvas/course/{}/user/{}/conferences?limit=100&current=true".format(
                lti_course_id, lti_user_id
            )
            rsp_cur = bj_sess.get(url=url_cur)  # Headers are already in the session
            # print('********** Current URL: ********** {}'.format(url_cur))
            # print('Current Response: {}'.format(rsp_cur))
            # print('Current Response Headers: {}'.format(rsp_cur.headers))
            # print('Current Response Text: {}'.format(rsp_cur.text))
            jsn_cur = rsp_cur.json().get("details")
            for row in range(len(jsn_cur)):
                jsn_cur[row]["mtg_status"] = "current"
            # print('Current JSON Type: {} JSON: {}'.format(type(jsn_cur), jsn_cur))

            url_rec = "https://canvaslms.bluejeansint.com/api/canvas/course/{}/user/{}/recordings?limit=100".format(
                lti_course_id, lti_user_id
            )
            rsp_rec = bj_sess.get(url=url_rec)  # Headers are already in the session
            # print('********** Recorded URL: ********** {}'.format(url_rec))
            # print('Recorded Response: {}'.format(rsp_rec))
            # print('Recorded Response Headers: {}'.format(rsp_rec.headers))
            # print('Recorded Response Text: {}'.format(rsp_rec.text))
            jsn_rec = rsp_rec.json().get("details")
            for row in range(len(jsn_rec)):
                jsn_rec[row]["mtg_status"] = "recorded"
            # print('Recorded JSON Type: {} JSON: {}'.format(type(jsn_rec), jsn_rec))

            jsn_all = jsn_upc + jsn_cur + jsn_rec
            # The id field is a mesh of various IDs. If it's long, it's unknown exactly what kind of id it is
            #   but we do know the meeting is one created post 9/20/20 upgrade.
            #   If it's short and there's a meeting ID, it's the same as the old bjc_conf_id.
            #   If it's short and there's no meeting ID, it's the same as the old bjc_rec_id.
            for row in range(len(jsn_all)):
                jsn_all[row]["bj_meeting_id"] = (
                    jsn_all[row]["meetingLink"].split("/")[3]
                    if "meetingLink" in jsn_all[row]
                    else "0"
                )
                jsn_all[row]["bjc_conf_id"] = (
                    jsn_all[row]["id"]
                    if len(jsn_all[row]["id"]) < 10 and "meetingLink" in jsn_all[row]
                    else "0"
                )
                jsn_all[row]["bjc_rec_id"] = (
                    jsn_all[row]["id"]
                    if len(jsn_all[row]["id"]) < 10
                    and "meetingLink" not in jsn_all[row]
                    else "0"
                )
                jsn_all[row]["bj_unknown_uuid"] = (
                    jsn_all[row]["id"] if len(jsn_all[row]["id"]) >= 10 else "0"
                )
                jsn_all[row] = flatten(jsn_all[row])
            # print('All JSON: {}'.format(json.dumps(jsn_all, indent=4)))

            if len(jsn_all) > 0:
                dft = pd.DataFrame(data=jsn_all)
                # dft.to_csv('./dft_{}.csv'.format(course_id), index=False)
                dft["canvas_acct_id"] = course.account_id
                dft["canvas_course_blueprint"] = course.blueprint
                dft["canvas_course_id"] = course_id
                dft["canvas_course_name"] = course.name
                dft["canvas_course_status"] = course.workflow_state
                dft["canvas_course_tab_id"] = tab.id
                dft["canvas_course_tab_is_hidden"] = hasattr(
                    tab, "hidden"
                )  # present only if True
                dft["canvas_course_tab_is_unused"] = hasattr(
                    tab, "unused"
                )  # present only if True
                dft["canvas_course_tab_vis_group"] = tab.visibility
                dft["term"] = term_name
                dft["timestamp"] = timestamp_utc
                dft.rename(
                    columns={
                        "listStartTime": "startTimeForList",
                        "title": "mtg_name",
                        "description": "mtg_desc",
                        "start": "mtg_start_time",
                        "end": "mtg_end_time",
                        "recordingTime": "mtg_recording_time",
                        "meetingLink": "mtg_join_link",
                        "recordingUrl": "mtg_play_link",
                    },
                    inplace=True,
                )
                df = df.append(dft, ignore_index=True, sort=True)
            else:
                # If no meetings in this BJ tab, insert a row to indicate
                df = df.append(
                    {
                        "canvas_acct_id": course.account_id,
                        "canvas_course_id": course.id,
                        "canvas_course_name": course.name,
                        "mtg_name": "None",
                        "term": term_name,
                        "timestamp": timestamp_utc,
                        "canvas_course_blueprint": course.blueprint,
                        "canvas_course_status": course.workflow_state,
                        "canvas_course_tab_id": tab.id,
                        "canvas_course_tab_is_hidden": hasattr(
                            tab, "hidden"
                        ),  # present only if True
                        "canvas_course_tab_is_unused": hasattr(
                            tab, "unused"
                        ),  # present only if True
                        "canvas_course_tab_vis_group": tab.visibility,
                    },
                    ignore_index=True,
                    sort=True,
                )

    # If this course has no BlueJeans tab then we should insert a row to indicate this
    if not this_course_has_bj_tab:
        df = df.append(
            {
                "canvas_acct_id": course.account_id,
                "canvas_course_id": course_id,
                "canvas_course_name": course.name,
                "canvas_course_blueprint": course.blueprint,
                "canvas_course_status": course.workflow_state,
                "mtg_name": "None",
                "term": term_name,
                "timestamp": timestamp_utc,
            },
            ignore_index=True,
            sort=True,
        )

    print("Number of Virtual Meetings tabs: {}".format(found_VM))
    print("Number of BlueJeans tabs: {}".format(found_BJ))
