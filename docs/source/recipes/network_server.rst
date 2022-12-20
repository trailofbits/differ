Recipe: Network Server
======================

A network server will typically require:

1. A configuration file
2. A client to connect to and interact with the server

The client will exercise the server, trigger some behavior, and then produce some output that can be
compared across binaries to verify that the server is operating correctly.

This recipe will target a notional HTTP server and use off the shelf ``wget`` as the client. The
trace template will:

- Generate a configuration based on some fuzz variables
- Run the server
- While the server is running, launch the client program to download a file from the server
- Gracefully terminate the server
- Compare the downloaded file contents

This is a notional example where the HTTP server is configured through an INI file. The project is
configured to serve the ``test.html`` file from a fuzzed endpoint name.

Project Configuration
---------------------

.. code-block:: yaml

    name: http_server
    original: /path/to/http/server
    debloaters:
      some_debloater: /path/to/debloated/http/server

    templates:
      # The command line arguments will load a configuration file, ./config.ini
      - arguments: -c ./config.ini

        input_files:
          # We need to generate the configuration file based on variables.
          - source: configuration.template.ini
            destination: config.ini

          # Next, we need some file to serve (test.html)
          - test.html

        # Create the fuzz variables
        variables:
          # The route to the filename being served (e.g.- "GET /{{route}}" returns "test.html")
          route:
            type: str
            regex:
              pattern: '[A-Z][0-9A-Za-z_]{3,10}'
              count: 5

        # The concurrent commands to execute while the trace is running. This will be our call to
        # wget to download the file
        concurrent:
          delay: 2.0  # allow the HTTP server 2 seconds to start up prior to running wget
          run: |
            wget http://localhost:8080/{{route}} --output-document downloaded.html
            rc=$?

            # We downloaded the file, we can safely terminate the server
            kill $(DIFFER_BINARY_PID)

            # exit with the exit code of wget to trigger an error if wget failed
            exit $rc

        # Finally, the list of comparators we run
        comparators:
          # Verify the exit code of the server matches
          - exit_code
          # Verify the stdout and stderr content of the server matches
          - stdout
          - stderr
          # Verify that the stdout/stderr content and the exit code of the concurrent bash script
          # (wget) matches
          - concurrent_script
          # Verify the contents of the downloaded file
          - id: file
            filename: downloaded.html


Configuration File Template
---------------------------

For this example, the server accepts an INI file for configuration. The server is configured to
listen on port 8080 and serve the ``test.html`` file at the ``{{route}}`` endpoint.

.. code-block:: ini

    listen=8080

    [routes]
    {{route}}=test.html


Test HTML File Template
-----------------------

.. code-block:: html

    <html>
      <head>
        <title>Hello from: {{route}}</title>
      </head>
      <body>
        <h1>Hello from: {{route}}</h1>
      </body>
    </html>

