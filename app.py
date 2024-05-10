import os
from sqlite3 import dbapi2 as sqlite3
from flask import Flask, request, g, redirect, url_for, render_template, flash, session, abort

app = Flask(__name__)

# load default config and override config from an environment variable
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'flaskr.db'),
    DEBUG=True,
    SECRET_KEY='development key',
))

app.config.from_envvar('FLASKR_SETTINGS', silent=True)


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


def index():
    """Renders the main page."""

    return render_template(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)