"""
Jinja2 Environment and template functions. This module provides the ``JINJA_ENVIRONMENT`` variable
that contains all custom filters that are available to command line arguments and input file
templates.
"""
import os
import shlex
import socket

from jinja2 import Environment

#: The Jinja2 Environment will custom filters.
#:
#: - :func:`quote_filter` - the ``quote`` filter
#: - :func:`socket.gethostbyname` - the ``gethostbyname`` filter
#:
#: And global variables.
#:
#: - ``env`` - :data:`os.environ`
JINJA_ENVIRONMENT = Environment(
    keep_trailing_newline=True,
)


def quote_filter(s: str) -> str:
    """
    A ``quote`` filter that quotes the input string so that it can be used within a command line
    argument or input file. This method calls :func:`shlex.quote` and can be used like so:

    .. code-block:: yaml

      - templates:
        - arguments: '--value {{name | quote}}'
          variables:
            name:
              type: str
              values:
                - 'this value contains spaces'

    In this example, the generated command line arguments generated would be:

    .. code-block:: bash

        /path/to/binary --value 'this value contains spaces'

    :param s: input string to quote
    :returns: quoted string
    """
    return shlex.quote(s)


JINJA_ENVIRONMENT.filters['quote'] = quote_filter
JINJA_ENVIRONMENT.filters['gethostbyname'] = socket.gethostbyname
JINJA_ENVIRONMENT.globals = {'env': dict(os.environ)}
