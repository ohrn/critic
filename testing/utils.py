import re
import contextlib

instance = None
frontend = None

RE_REVIEW_URL = re.compile(r"^remote:\s+http://.*/r/(\d+)\s*$")

@contextlib.contextmanager
def settings(user, settings, repository=None):
    data = { "settings": [{ "item": item, "value": value }
                          for item, value in settings.items()] }
    if repository:
        data["repository"] = repository

    # Set requested settings.
    with frontend.signin(user):
        frontend.operation("savesettings", data=data)

    try:
        yield
    finally:
        data = { "settings": [{ "item": item }
                              for item, value in settings.items()] }
        if repository:
            data["repository"] = repository

        # Reset settings back to the default.
        with frontend.signin(user):
            frontend.operation("savesettings", data=data)

@contextlib.contextmanager
def access_token(user, profile):
    with frontend.signin(user):
        access_token = frontend.json(
            "users/me/accesstokens",
            post={
                "title": "by testing.utils.access_token()",
                "profile": profile
            },
            expect={
                "id": int,
                "access_type": "user",
                "user": instance.userid(user),
                "title": "by testing.utils.access_token()",
                "part1": str,
                "part2": str,
                "profile": dict
            })

    try:
        yield access_token
    finally:
        with frontend.signin(user):
            frontend.json(
                "accesstokens/%d" % access_token["id"],
                delete=True,
                expected_http_status=204)

def createReviewViaPush(work, owner, commit="HEAD"):
    with settings(owner, { "review.createViaPush": True }):
        remote_url = instance.repository_url(owner)
        output = work.run(["push", remote_url, "HEAD"], TERM="dumb")
        for line in output.splitlines():
            match = RE_REVIEW_URL.match(line)
            if match:
                return int(match.group(1))
        else:
            testing.expect.check("<review URL in 'git push' output>",
                                 "<no review URL found>")
