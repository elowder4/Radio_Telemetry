import os
from sqlite3 import dbapi2 as sqlite3
from flask import Flask, request, g, render_template, flash, Response, stream_with_context
import serial
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import io
import logging
import sys
import time
import json
import datetime
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
random.seed()  # initialize the random number generator


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


def get_latest_data():
    db = get_db()
    cur = db.execute('SELECT datetime FROM session ORDER BY datetime DESC LIMIT 1')
    db.commit()
    session_datetime = cur.fetchone()[0]

    cur = db.execute('SELECT time FROM telemetry_data WHERE session = ?', [session_datetime])
    db.commit()
    sql_x = cur.fetchall()

    cur = db.execute('SELECT alt FROM telemetry_data WHERE session = ?', [session_datetime])
    sql_y0 = cur.fetchall()
    db.commit()

    cur = db.execute('SELECT temp FROM telemetry_data WHERE session = ?', [session_datetime])
    sql_y1 = cur.fetchall()
    db.commit()

    cur = db.execute('SELECT acc_mag FROM telemetry_data WHERE session = ?', [session_datetime])
    sql_y2 = cur.fetchall()
    db.commit()

    x, y0, y1, y2 = [], [], [], []

    for val_x, val_y0, val_y1, val_y2 in zip(sql_x, sql_y0, sql_y1, sql_y2):
        x.append(val_x[0])
        y0.append(val_y0[0])
        y1.append(val_y1[0])
        y2.append(val_y2[0])

    return x, y0, y1, y2


def create_figure(x, y, i):
    fig = Figure(figsize=(6, 6), dpi=80)
    graph_titles = ['Altitude', 'Temperature', 'Acceleration']
    axis = fig.add_subplot(1, 1, 1)
    fig.tight_layout(pad=5.0)
    axis.set_title(graph_titles[i])
    axis.plot(x, y, 'b+')

    return fig


@app.route('/plot-png/<int:i>')
def plot_png(i):
    x, y0, y1, y2 = get_latest_data()

    y = [y0, y1, y2]
    fig = create_figure(x, y[i], i)
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)

    return Response(output.getvalue(), mimetype='image/png')


def get_data():
    """Docstring Here"""

    count = 0
    db = get_db()

    if request.headers.getlist("X-Forwarded-For"):
        client_ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        client_ip = request.remote_addr or ""

    try:
        if count == 0:
            datetime_val = datetime.datetime.now()
            db.execute('INSERT INTO session (datetime) VALUES (?)', [datetime_val])
            db.commit()
            t0 = time.perf_counter()
            count += 1

        logger.info("Client %s connected", client_ip)
        while True:
            time_val = round(time.perf_counter() - t0, 1)
            data = [random.random() * 100, random.random() * 100, random.random() * 100]
            json_data = json.dumps(
                {
                    "time": time_val,
                    "value": data,
                }
            )
            yield f"data:{json_data}\n\n"
            time.sleep(0.1)
            db.execute('INSERT INTO telemetry_data (session, time, alt, temp, acc_mag) VALUES (?, ?, ?, ?, ?) ',
                       [datetime_val, time_val, data[0], data[1], data[2]])
            db.commit()

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
        return render_template('index.html', device_tested=True, take_data=True)
    elif request.form.get('stop'):
        # send stop command to radio
        # stop saving data and display amount of data points and stuff
        return render_template('index.html', device_tested=False, take_data=True)
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


@app.route("/download_data_csv")
def download_data_csv():
    # https://stackoverflow.com/questions/30024948/flask-download-a-csv-file-on-clicking-a-button
    t, alt, temp, acc = get_latest_data()
    # assuming all lists have the same length
    data = zip(t, alt, temp, acc)

    # create a CSV string
    csv = "\n".join([",".join(map(str, row)) for row in data])

    datetime_val = datetime.datetime.now()

    return Response(
        csv,
        mimetype="text/csv",
        headers={"Content-disposition":
                 f"attachment; filename={datetime_val}.csv"})


if __name__ == '__main__':
    app.run(debug=True)
