'A server that saves Kinect frame data sent to it.'

### This program is a simple server that receives
### and saves data sent by a client program hooked up
### to a Kinect sensor. The major parts of this
### server are; the request handling code that
### actually saves data locally, the interface with
### the database, and some validators.

import os.path
import sqlite3
import socket
import datetime
import re
import uuid
import argparse
import logging

from flask import Flask
from flask import request
from flask import g

from util import *

app = Flask(__name__) # Create the web application.

## The get_db and close_connection functions make it possible
## to access the database inside request handlers. When the
## get_db function is called, it returns a handle to the
## database. When the request handler is finished running,
## the close_connection function cleans up the database
## handle.
## Both functions deal with the case where a handle already
## exists or doesn't already exist. If a handle already
## exists, get_db just returns it. If a handle does not
## exist, close_connection does nothing.
    
def get_db():
    'Get a reference to the database.'
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
    db.row_factory = make_frame_data # Changes the way queries are represented.
    return db

@app.teardown_appcontext
def close_connection(exception):
    'Close the database if open.'
    db = getattr(g, '_database', None)
    if db is not None:
        db.commit()
        db.close()

## The get_db function mentioned earlier does more than just
## return a handle; it also changes the row_factory. The row
## factory is a function called on the results of a query
## before returning them. The sqlite3 queries are tuples
## containing row values by default, but the order of the
## frame meta data fields is irrelevant, the fields don't
## need to be iterated over, and it should be obvious what
## field is being accessed. Using a tuple directly would
## lead to a bunch of code with rows being indexed with magic
## numbers. Representing the queries as class instances was
## the cleanest way to make the accessors meaningful.
## The FrameMetaData class just contains the fields in a row
## from the database. To see the actual fields, take a look
## at the SQL script used to initialize the database and
## create tables.

class FrameMetaData(object):
    'Meta data about a frame.'
    def __init__(self, file_name, origin_machine, time):
        self.file_name = file_name
        self.origin_machine = origin_machine
        self.time = time        

def make_frame_data(cursor, row):
    'A factory function that takes a frame SQL row tuple and returns a FrameMetaData instance.'
    return FrameMetaData(row[0], row[1], row[2])

## The init_db function initializes the database with a
## given scehem. It will be called automatically if no
## file with the expected path is found. It can also be
## ran from an interpreter to reset the database.
def init_db():
    'Initialize the database with an empty table.'
    with app.app_context():
	try:
            db = get_db()
	except sqlite3.OperationalError, e:
            logging.debug('Does the project directory %s exist?', default_save_location())
            raise e
        with app.open_resource('schema.sql', mode = 'r') as f:
            db.cursor().executescript(f.read())
        db.commit()



## The following two functions are predicates used to check
## that the data being saved in the database is valid before
## it's actually saved. Ideally, these functions and the
## assertions they're used in will prevent any malformed
## records from being saved. They're defined and used
## outside of the FrameMetaData constructor because it's
## possible for the fields to be changed after the object
## is constructed.
        


## Compiling the regular expression outside of the function
## ensures it only gets compiled once.
_UUID_RE = re.compile('^[0-9a-f\\-]{8}-[0-9a-f\\-]{4}-[0-9a-f\\-]{4}-[0-9a-f\\-]{4}-[0-9a-f\\-]{12}$') 
def is_valid_uuid(file_name):
    'True if FILE_NAME is a valid hexidecimal UUID.'
    return re.match(_UUID_RE, file_name)

def is_valid_time(time):
    'True if TIME is a valid string in a simple subset of ISO8601.'
    try:
        datetime.datetime.strptime(time, '%Y-%m-%dT%H:%M:%S')
        return True
    except ValueError:
        return False        


## The next two functions are used to save a piece of frame data.
## The first function only saves meta data about the frame. It saves
## the IP address of the sender, the name of the file the actual
## image date will be stored in, and the time the data was received.
## The second function saves the actual data to the file system.
## The data is split across a database and file system because it
## has better read performance for the size of files being used. [0]
## [0] https://www.sqlite.org/intern-v-extern-blob.html

def save_frame_record(frame):
    'Save a record containing metadata about a FRAME to the database.'
    assert is_valid_ipv6_address(frame.origin_machine)
    assert is_valid_uuid(frame.file_name)
    assert is_valid_time(frame.time)
    curr = get_db().execute('INSERT INTO frames values(?, ?, ?)',
                            (frame.file_name, frame.origin_machine, frame.time))
    logging.info('Saved record to database.')

def save_frame_image(data, file_name):
    'Save the image DATA of the frame to a file with FILE_NAME.'
    path = os.path.join(SAVE_LOCATION, file_name)
    logging.info('Frame image save to %s', path)
    with file(path, 'wb') as f_obj:
        f_obj.write(data)
    logging.info('Saved image to %s', path)

## Every PUT or POST request is handled the same way. The body of the
## request is saved in a new file and information about the request
## and file is stored in the database. The following function is bound
## to the root URL.
@app.route('/', methods = ('POST', 'PUT'))
def save():
    'Save the following frame data.'
    file_name = str(uuid.uuid4()) # Create a random UUID.
    save_frame_record(FrameMetaData(file_name,
                                    request.remote_addr,
                                    time = datetime.datetime.now().replace(microsecond = 0).isoformat()))
    save_frame_image(request.data, file_name)
    return 'Success'

## Start the server if this file is run as a command.    
if __name__ == '__main__':
    logging.basicConfig(level = logging.DEBUG)
    parser = argparse.ArgumentParser(description = 'A database service for saving sensor data.')
    parser.add_argument('--port', help = 'The port to run the server on.', type = is_port_number, default = 5000)
    parser.add_argument('--save', help = 'The directory to save data to.', type = str, default = default_save_location()) ## TODO! The type argument should not accept invalid paths.
    args = parser.parse_args()
    SAVE_LOCATION = args.save

    ## Retrieve and load the database file. Initialize a
    ## new database if one doesn't already exist in the
    ## expected place.
    DB_PATH = os.path.join(SAVE_LOCATION, 'DB_FRAMES')
    try:
        with file(DB_PATH) as f_obj:
            pass
    except IOError:
        init_db()

    app.run(host = '::', port = args.port)
