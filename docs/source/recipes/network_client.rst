Recipe: Network Client
======================

A network client requires a server binary that speaks the same protocol. The differ project will
first need to launch the server binary and, after it has time to completely initialize, run the
client to connect to the server and exercise some functionality from the client. The server will
either terminate on its own and will need to be terminated manually so that it cleanly exits.

This recipe will use the netcat tool, running in client mode, that connects to another netcat tool
running in server mode.

Project Configuration
---------------------

.. code-block:: yaml

    name: netcat
    original: /usr/bin/nc
    debloaters:
      some_debloater: /usr/bin/nc

    templates:
      # The command line arguments will load a configuration file. Connect to port 8080
      - arguments: -N 127.0.0.1 8080

        # Create the fuzz variables
        variables:
          # The number to make sure we have some randomness in the output between traces
          number:
            type: int
            range:
              minimum: 0
              maximum: 1024
              count: 5

        # Start the netcat server first, saving the PID to a file, and wait 2 seconds for the
        # server to fully initialize. The server is launched in a background process and we
        # redirect stdout/stderr so that we can compare the message received between traces.
        setup: |
          echo 'starting server'
          nc -l 8080 > server-out.bin 2>&1 &
          echo $! > server.pid
          sleep 2

        # When cleaning up the job, wait until the background server process exits cleanly, which
        # should happen normally since netcat exits after the client disconnects.
        teardown: |
          PID=$(cat server.pid)
          while ps -p $PID > /dev/null; do sleep 0.2; done

        # Send a message to the server
        stdin:
          value: 'hello world: {{number}}'

        # Finally, the list of comparators we run
        comparators:
          # Verify the exit code of the client matches
          - id: exit_code
            expect: 0
          # Verify the stdout and stderr content of the client matches.
          - stdout
          - stderr
          # Verify that the setup script has identical output
          - setup_script
          # Compare the server output which will contain the message received from the client
          - id: file
            filename: server-out.bin


.. spell-checker:ignore netcat
