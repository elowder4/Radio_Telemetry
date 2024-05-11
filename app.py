import json
import os
from sqlite3 import dbapi2 as sqlite3
from flask import Flask, request, g, render_template, flash, Response, stream_with_context
import numpy as np
import serial
import logging
import sys
import time
import json
from datetime import datetime
import random

app = Flask(__name__)

# load default config and override config from an environment variable
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'telemetry.db'),
    DEBUG=True,
    SECRET_KEY='development key',
))

app.config.from_envvar('FLASKR_SETTINGS', silent=True)

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
random.seed()  # Initialize the random number generator


def connect_db():
    """Connects to the database."""

    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row

    return rv


def init_db():
    """Function to initialize the database."""

    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()


@app.cli.command('initdb')
def initdb_command():
    """Command to initialize the database."""

    init_db()
    print('Initialized the database.')


def get_db():
    """Opens a new database connection if there is none."""

    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db


@app.teardown_appcontext
def close_db(error):
    """Closes the database at the end of the request."""

    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()


def get_data():
    """Docstring Here"""
    count = 0
    if request.headers.getlist("X-Forwarded-For"):
        client_ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        client_ip = request.remote_addr or ""

    try:
        if count == 0:
            t0 = time.perf_counter()
            count += 1

        logger.info("Client %s connected", client_ip)
        while True:
            json_data = json.dumps(
                {
                    "time": round(time.perf_counter() - t0, 1),
                    "value": [random.random() * 100, random.random() * 100, random.random() * 100],
                }
            )
            yield f"data:{json_data}\n\n"
            time.sleep(2)
    except GeneratorExit:
        logger.info("Client %s disconnected", client_ip)


@app.route('/', methods=['GET', 'POST'])
def index():
    """Renders the main page."""

    if request.form.get('device_tested'):
        # some logic for testing the device will go here
        flash('Device Successfully Tested')
        return render_template('index.html', device_tested=True)
    elif request.form.get('take_data'):
        # send some command to the radio to get ready
        return render_template('index.html', take_data=True)
    elif request.form.get('stop'):
        # send stop command to radio
        # stop saving data and display amount of data points and stuff
        return render_template('index.html', stop=True)
    elif request.form.get('reset'):
        # send stop command to radio
        return render_template('index.html')
    else:
        return render_template('index.html')


@app.route("/chart-data")
def chart_data() -> Response:
    response = Response(stream_with_context(get_data()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


if __name__ == '__main__':
    app.run(debug=True)
