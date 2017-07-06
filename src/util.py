## The following exceptions are defined to deal with any
## problems caused when the program attempts to locate
## the directory the database is stored in and all frame
## images are saved in. If a default directory is not
## defined for the operating system or the program is
## not able to find the home directory of the system,
## an error message will be printed and the program will
## shut down.

import os
import os.path
import socket

class UndefinedEnvironmentVariableException(Exception):
    'An environment variable was referenced that does not exist.'
    def __init__(self, name_of_variable):
        self.name_of_variable = name_of_variable
    def __repr__(self):
        return 'Could not find the variable %s in the environment.' % (self.name_of_variable)

class UnsupportedSystemException(Exception):
    'The operating system is not supported.'
    def __init__(self, detected_os):
        self.detected_os = detected_os
    def __repr__(self):
        return 'The detected operating system, %s, is not supported.'
        

def default_save_location():
    'The default location to save files on this machine.'    
    if os.name == 'posix':
        try:
            return os.path.join(os.environ['HOME'],
                                '.KinectExperiment')
        except KeyError, e:
            raise UndefinedEnvironmentVariableException(e.message)
    elif os.name == 'nt':
        try:
            return os.path.join(os.environ['HOMEPATH'],
                                'AppData',
                                'Roaming',
                                'KinectExperiment')
        except KeyError, e:
            raise UndefinedEnvironmentVariableException(e.message)
    else:
        raise UnsupportedSystemException(os.name)

def retrieve_file(relative_path):
    'Retrieve the full path to the file in the project directory. The program will shutdown if the project directory cannot be found.'
    try:
        return os.path.join(default_save_location(), relative_path)
    except UnsupportedSystemException, e:
        print 'System %s is not supported.' % (e.detected_os,)
        quit(1)
    except UndefinedEnvironmentVariableException, e:
        print 'The system attempted to look up the home directory, but the environment variable %s was undefined.' % (e.name_of_variable)
        quit(1)

def is_valid_ipv6_address(addr):
    'True if ADDR is a valid ipv6 address.'
    try:
        socket.inet_pton(socket.AF_INET6, addr)
    except socket.error:
        return False
    return True        
    
def is_port_number(n):
    'Returns argument if valid port number, otherwise raise an ArgumentError.'
    try:
        int(n)
    except ValueError:
        raise argparse.ArgumentError('not an int')
    if not (0 <= int(n) <= (2 << 15) - 1):
        raise argparse.ArgumentError('not a valid port number, out of range')
    return int(n)
