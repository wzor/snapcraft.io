"""
A Flask application for snapcraft.io.

The web frontend for the snap store.
"""

# Core packages
import os
import socket
from urllib.parse import (
    unquote,
    urlparse,
    urlunparse,
)

# Third-party packages
import flask
import talisker.flask
import prometheus_flask_exporter
from flask_openid import OpenID
from flask_wtf.csrf import CSRFProtect
from raven.contrib.flask import Sentry
from werkzeug.contrib.fixers import ProxyFix
from werkzeug.debug import DebuggedApplication

# Local webapp
import webapp.authentication as authentication
import webapp.helpers as helpers
import webapp.public.views as public_views
import webapp.publisher.views as publisher_views
import webapp.publisher.api as publisher_api
import webapp.template_functions as template_functions
from webapp.decorators import login_required
from webapp.macaroon import (
    MacaroonRequest,
    MacaroonResponse,
)

app = flask.Flask(
    __name__, template_folder='../templates', static_folder='../static')
talisker.flask.register(app)
app.wsgi_app = ProxyFix(app.wsgi_app)
if app.debug:
    app.wsgi_app = DebuggedApplication(app.wsgi_app)
app.secret_key = os.environ['SECRET_KEY']
app.url_map.strict_slashes = False
app.url_map.converters['regex'] = helpers.RegexConverter
sentry = Sentry(app)

metrics = prometheus_flask_exporter.PrometheusMetrics(
    app,
    group_by_endpoint=True,
    buckets=[0.25, 0.5, 0.75, 1, 2],
    path=None
)

open_id = OpenID(
    app=app,
    stateless=True,
    safe_roots=[],
    extension_responses=[MacaroonResponse]
)

csrf = CSRFProtect(app)

SENTRY_PUBLIC_DSN = os.getenv('SENTRY_PUBLIC_DSN', '').strip()
LOGIN_URL = os.getenv(
    'LOGIN_URL',
    'https://login.ubuntu.com',
)

ENVIRONMENT = os.getenv(
    'ENVIRONMENT',
    'devel'
)
COMMIT_ID = os.getenv(
    'COMMIT_ID',
    'commit_id'
)

app.config['SENTRY_CONFIG'] = {
    'release': COMMIT_ID,
    'environment': ENVIRONMENT
}


@app.context_processor
def utility_processor():
    """
    This defines the set of properties and functions that will be added
    to the default context for processing templates. All these items
    can be used in all templates
    """

    if authentication.is_authenticated(flask.session):
        user_name = flask.session['openid']['fullname']
    else:
        user_name = None

    return {
        # Variables
        'LOGIN_URL': LOGIN_URL,
        'SENTRY_PUBLIC_DSN': SENTRY_PUBLIC_DSN,
        'COMMIT_ID': COMMIT_ID,
        'ENVIRONMENT': ENVIRONMENT,
        'path': flask.request.path,
        'user_name': user_name,

        # Functions
        'contains': template_functions.contains,
        'join': template_functions.join,
        'static_url': template_functions.static_url,
        'format_number': template_functions.format_number,
    }


# Error handlers
# ===
@app.errorhandler(404)
def page_not_found(error):
    """
    For 404 pages, display the 404.html template,
    passing through the error description.
    """

    return flask.render_template(
        '404.html', error=error.description
    ), 404


# Global tasks for all requests
# ===
@app.before_request
def clear_trailing():
    """
    Remove trailing slashes from all routes
    We like our URLs without slashes
    """

    parsed_url = urlparse(unquote(flask.request.url))
    path = parsed_url.path

    if path != '/' and path.endswith('/'):
        new_uri = urlunparse(
            parsed_url._replace(path=path[:-1])
        )

        return flask.redirect(new_uri)


@app.after_request
def add_headers(response):
    """
    Generic rules for headers to add to all requests

    - X-Hostname: Mention the name of the host/pod running the application
    - Cache-Control: Add cache-control headers for public and private pages
    """

    response.headers["X-Hostname"] = socket.gethostname()

    if response.status_code == 200:
        if flask.session:
            response.headers['Cache-Control'] = 'private'
        else:
            # Only add caching headers to successful responses
            response.headers['Cache-Control'] = ', '.join({
                'public',
                'max-age=61',
                'stale-while-revalidate=300',
                'stale-if-error=86400',
            })

    return response


# Redirects
# ===
@app.route('/docs', defaults={'path': ''})
@app.route('/docs/<path:path>')
def docs_redirect(path):
    return flask.redirect('https://docs.snapcraft.io/' + path)


@app.route('/community')
def community_redirect():
    return flask.redirect('/')


@app.route('/create')
def create_redirect():
    return flask.redirect('https://docs.snapcraft.io/build-snaps')


@app.route('/favicon.ico')
def favicon():
    return flask.redirect('https://assets.ubuntu.com/v1/fdc99abe-ico_16px.png')


# Login handler
# ===
@app.route('/login', methods=['GET', 'POST'])
@open_id.loginhandler
@csrf.exempt
def login():
    if authentication.is_authenticated(flask.session):
        return flask.redirect(open_id.get_next_url())

    root = authentication.request_macaroon()
    openid_macaroon = MacaroonRequest(
        caveat_id=authentication.get_caveat_id(root)
    )
    flask.session['macaroon_root'] = root

    return open_id.try_login(
        LOGIN_URL,
        ask_for=['email', 'nickname', 'image'],
        ask_for_optional=['fullname'],
        extensions=[openid_macaroon]
    )


@open_id.after_login
def after_login(resp):
    flask.session['macaroon_discharge'] = resp.extensions['macaroon'].discharge

    try:
        account = publisher_api.get_account(flask.session)
        flask.session['openid'] = {
            'identity_url': resp.identity_url,
            'nickname': account['username'],
            'fullname': account['displayname'],
            'image': resp.image,
            'email': account['email']
        }
    except Exception:
        flask.session['openid'] = {
            'identity_url': resp.identity_url,
            'nickname': resp.nickname,
            'fullname': resp.fullname,
            'image': resp.image,
            'email': resp.email
        }

    return flask.redirect(open_id.get_next_url())


@app.route('/logout')
def logout():
    if authentication.is_authenticated(flask.session):
        authentication.empty_session(flask.session)
    return flask.redirect('/')


# Normal views
# ===
@app.route('/')
def homepage():
    return public_views.homepage()


@app.route('/status')
def status():
    return 'alive'


@app.route('/store')
def store():
    return public_views.store()


@app.route('/discover')
def discover():
    return flask.redirect('/store')


@app.route('/snaps')
def snaps():
    return flask.redirect('/store')


@app.route('/search')
def search_snap():
    return public_views.search_snap()


@app.route('/<regex("[a-z0-9-]*[a-z][a-z0-9-]*"):snap_name>')
def snap_details(snap_name):
    return public_views.snap_details(snap_name)


# Publisher views
# ===
@app.route('/account')
@login_required
def get_account():
    return flask.redirect('/account/snaps')


@app.route('/account/details')
@login_required
def get_account_details():
    return publisher_views.get_account_details()


@app.route('/account/snaps')
@login_required
def get_account_snaps():
    return publisher_views.get_account_snaps()


@app.route('/account/agreement')
@login_required
def get_agreement():
    return publisher_views.get_agreement()


@app.route('/account/agreement', methods=['POST'])
@login_required
def post_agreement():
    return publisher_views.post_agreement()


@app.route('/account/username')
@login_required
def get_account_name():
    return publisher_views.get_account_name()


@app.route('/account/username', methods=['POST'])
@login_required
def post_account_name():
    return publisher_views.post_account_name()


@app.route('/account/snaps/<snap_name>/metrics')
@login_required
def publisher_snap_metrics(snap_name):
    return publisher_views.publisher_snap_metrics(snap_name)


@app.route('/account/snaps/<snap_name>/listing', methods=['GET'])
@login_required
def get_listing_snap(snap_name):
    return publisher_views.get_listing_snap(snap_name)


@app.route('/account/snaps/<snap_name>/listing', methods=['POST'])
@login_required
def post_listing_snap(snap_name):
    return publisher_views.post_listing_snap(snap_name)


@app.route('/account/snaps/<snap_name>/market')
@login_required
def get_market_snap(snap_name):
    return flask.redirect(
        "/account/snaps/{snap_name}/listing".format(
            snap_name=snap_name))


@app.route('/account/snaps/<snap_name>/measure')
@login_required
def get_measure_snap(snap_name):
    return flask.redirect(
        "/account/snaps/{snap_name}/metrics".format(
            snap_name=snap_name))


@app.route('/account/register-name')
@login_required
def get_register_name():
    return publisher_views.get_register_name()


@app.route('/account/register-name', methods=['POST'])
@login_required
def post_register_name():
    return publisher_views.post_register_name()
