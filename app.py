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


def connect_db() -> sqlite3.Connection:
    """Connects to the database.
    output: sqlite3.Connection object."""

    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row

    return rv


def init_db() -> None:
    """Function to initialize the database.
    output: None."""

    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()


@app.cli.command('initdb')
def initdb_command():
    """Command to initialize the database.
    output: None."""

    init_db()
    print('Initialized the database.')


def get_db() -> sqlite3.Connection:
    """Opens a new database connection if there is none.
    output: sqlite3.Connection object."""

    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()

    return g.sqlite_db


@app.teardown_appcontext
def close_db(error) -> None:
    """Closes the database at the end of the request.
    output: None."""

    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()


def get_latest_data() -> [float]:
    """Helper function to get the latest data entries from the database. Gets all data from telemetry_data table
    associated with the most recent entry in session table. Returns data in a 2D array.
    output: Returns most recent data from telemetry_data table as a 2D array with each row representing the respective
    column in the database."""

    db = get_db()

    col_names = ['time', 'alt', 'temp', 'acc_mag']  # names of columns to get data from

    # get latest session value
    cur = db.execute('SELECT datetime FROM session ORDER BY datetime DESC LIMIT 1')
    db.commit()
    session_datetime = cur.fetchone()[0]
    
    data = []  # store data

    for name in col_names:
        cur = db.execute(f'SELECT {name} FROM telemetry_data WHERE session = ?', [session_datetime])
        db.commit()
        sql_data = cur.fetchall()

        # create 2D array of data (located at 0 index of SQL object)
        data.append([val[0] for val in sql_data])
    
    return data


def create_figure(x: [float], y: [float], title: str) -> Figure:
    """Helper function to create figures displayed after data is collected.
    x: array of data plotted on x-axis.
    y: array of data plotted on y-axis.
    title: title of the graph.
    output: returns a Figure object."""
    
    fig = Figure(figsize=(6, 6), dpi=80)  # size can be an issue, but this works well for my viewport
    axis = fig.add_subplot(1, 1, 1)  # 1 row, 1 column, index 1
    fig.tight_layout(pad=5.0)  # add padding
    axis.set_title(title)
    axis.plot(x, y, 'b+')  # b+ controls type of plot markers

    return fig


def test_data() -> bool:
    """Function to test if data is being received properly. Initializes data collection and makes entries into the
    database under the column 'test.' The column is then read to ensure proper function. Returns True if data is being
    collected and False if not.
    output: Returns True if working and False if not."""

    if request.headers.getlist("X-Forwarded-For"):
        client_ip = request.headers.getlist("X-Forwarded-For")[0]

    else:
        client_ip = request.remote_addr or ""

    try:
        logger.info("Client %s connected", client_ip)

        data_list = []

        for i in range(2):
            time_val = round(time.perf_counter(), 1)
            data = [time_val, random.random() * 100, random.random() * 100, random.random() * 100]
            data_list.append(data)

        return all(data)  # if a data point is empty return false

    except GeneratorExit:
        logger.info("Client %s disconnected", client_ip)


def get_data() -> None:
    """Function to get data from the radio to the live JavaScript graphs.
    output: None."""

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
            yield f"data:{json_data}\n\n"  # send to JavaScript
            time.sleep(0.1)  # wait in seconds
            db.execute('INSERT INTO telemetry_data (session, time, alt, temp, acc_mag) VALUES (?, ?, ?, ?, ?) ',
                       [datetime_val, time_val, data[0], data[1], data[2]])
            db.commit()

    except GeneratorExit:
        logger.info("Client %s disconnected", client_ip)


@app.route('/plot-png/<int:i>')
def plot_png(i: int) -> Response:
    """Route to plot graphs once data collection is complete.
    i: input from the url indicating which data set is plotted (only 3 images in html).
    output: returns a Response object that sends the graph to the webpage."""

    graph_names = ['Altitude', 'Temperature', 'Acceleration']

    data = get_latest_data()
    print(data)
    y = [data[j+1] for j in range(3)]  # get data (up to 3 values)

    fig = create_figure(data[0], y[i], graph_names[i])  # time is the first column of the database
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)

    return Response(output.getvalue(), mimetype='image/png')


@app.route('/', methods=['GET', 'POST'])
def index() -> str:
    """Renders the main page.
    output: Index template as a string."""

    if request.form.get('device_tested'):
        if test_data():
            flash('Device Successfully Tested.')
            return render_template('index.html', device_tested=True)
        else:
            flash('Device Failed Test. Please Try Again.')
            return render_template('index.html')

    elif request.form.get('take_data'):
        return render_template('index.html', device_tested=True, take_data=True)

    elif request.form.get('stop'):
        # could pass number of data points and other cool values eventually
        return render_template('index.html', device_tested=False, take_data=True)

    elif request.form.get('reset'):
        return render_template('index.html')

    else:
        return render_template('index.html')


@app.route("/chart-data")
def chart_data() -> Response:
    """Route to send data to live graphs that use JavaScript.
    output: Returns Response object."""

    response = Response(stream_with_context(get_data()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"

    return response


@app.route("/download_data_csv")
def download_data_csv() -> Response:
    """Route to download the latest data as a csv file.
    stackoverflow.com/questions/30024948/flask-download-a-csv-file-on-clicking-a-button was of great help.
    output: returns Response object."""

    csv = get_latest_data()

    #csv = "\n".join([",".join(map(str, row)) for row in data])  # create a CSV string

    datetime_val = datetime.datetime.now()  # use current time to name file

    return Response(
        csv,
        mimetype="text/csv",
        headers={"Content-disposition":
                 f"attachment; filename={datetime_val}.csv"})


if __name__ == '__main__':
    app.run(debug=True)
