Simple OPC-UA GUI client.

[![Scrutinizer Code Quality](https://scrutinizer-ci.com/g/FreeOpcUa/opcua-client-gui/badges/quality-score.png?b=master)](https://scrutinizer-ci.com/g/FreeOpcUa/opcua-client-gui/?branch=master)
[![Build Status](https://travis-ci.org/FreeOpcUa/opcua-client-gui.svg?branch=master)](https://travis-ci.org/FreeOpcUa/opcua-client-gui)
[![Build Status](https://travis-ci.org/FreeOpcUa/opcua-widgets.svg?branch=master)](https://travis-ci.org/FreeOpcUa/opcua-widgets)

Written using freeopcua python api and pyqt. Most needed functionalities are implemented including subscribing for data changes and events, write variable values listing attributes and references, and call methods. PR are welcome for any whished improvments

It has also a contextual menu with a few usefull function like putting the mode id in clipboard or the entire browse path which can be used directly in you program: client.nodes.root.get_child(['0:Objects', '2:MyNode'])

![Screenshot](/screenshot.png?raw=true "Screenshot")

The Fork: 
* The fork adds the ability to log data in a duckdb database. As default it creates a duckdb file on your home with the name opcua.duckdb. 
* Using a duckdb client e.g. DBeaver and onnecting to the database you get a history of all datapoints to which you subscribe. Reading and writing at the same time is not yet supported.  

What works:
* connecting and disconnecting
* browsing with icons per node types
* showing attributes and references
* subscribing to variable
* available on pip: sudo pip install git+https://github.com/upohl/opcua-client-gui/opcua-client-gui.git
* subscribing to events and logging them
* write variable node values
* gui for certificates
* gui for encryption 
* call methods
* plot method values
* remember last browsed path and restore state

TODO (listed after priority):

* remember connections and show connection history
* detect lost connection and automatically reconnect 
* gui for loging with certificate or user/password (can currently be done by writting them in uri)
* Maybe read history
* Something else?

# How to Install  

*Note: PyQT 5 is required.*

### Linux: (not tested)

1. Make sure python and python-pip is installed
2. 'pip3 install opcua-client'
3. 'pip3 install duckdb'
4. `pip3 install git+https://github.com/upohl/opcua-client-gui.git@duckdb-logger`  
5. Run with: `opcua-client-adesso`  
  
### Windows:  

1. Install winpython https://winpython.github.io/ , install the version including pyqt5!
2. 'pip3 install opcua-client'
3. 'pip3 install duckdb'
4. Use pip to install opcua-client: `pip install git+https://github.com/upohl/opcua-client-gui.git@duckdb-logger`
5. Run via the script pip created: `YOUR_PYTHON_INSTALL_PATH\Scripts\opcua-client-adesso.exe`

To update to the latest release run: `pip install opcua-client --upgrade`

### MacOS (not tested)

1. Make sure python, python-pip and homebrew is installed
2. `brew install pyqt@5`
3. 'pip3 install opcua-client'
4. 'pip3 install duckdb'
5. `pip3 install git+https://github.com/upohl/opcua-client-gui.git@duckdb-logger cryptography numpy`
6. Run with `opcua-client-adesso`

