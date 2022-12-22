Recipe: Network Server
======================

A network server requires a client binary that speaks the same protocol. The differ project will
launch the server binary and, after it has time to completely initialize, run the client to connect
to the server and exercise some functionality. The server will either terminate on its own and will
need to be terminated manually so that it cleanly exits.

This recipe will use the netcat tool, running in server mode, and then use another netcat instance
to send a message to the server.

Project Configuration
---------------------

.. code-block:: yaml

    name: netcat
    original: /usr/bin/nc
    debloaters:
      some_debloater: /usr/bin/nc

    templates:
      # The command line arguments will load a configuration file. Listen on port 8080
      - arguments: -l 8080

        # Create the fuzz variables
        variables:
          # The number to make sure we have some randomness in the output between traces
          number:
            type: int
            range:
              minimum: 0
              maximum: 1024
              count: 5

        # The concurrent commands to execute while the trace is running. This will be our call to
        # netcat to send the message
        concurrent:
          delay: 2.0  # allow the HTTP server 2 seconds to start up prior to running wget
          run: |
            echo 'hello world: {{number}}' | nc -N 127.0.0.1 8080
            exit $?

        # Finally, the list of comparators we run
        comparators:
          # Verify the exit code of the server matches
          - exit_code
          # Verify the stdout and stderr content of the server matches, this will include the
          # message received from the netcat client.
          - stdout
          - stderr
          # Verify that the stdout/stderr content and the exit code of the concurrent bash script
          # (nc) matches
          - concurrent_script


.. spell-checker:ignore netcat
