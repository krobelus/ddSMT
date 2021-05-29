import pytest

from .. import mutators
from .. import options

# Need valid args to import "cli".
options.args(['_in', '_out', '_cmd'])
from .. import cli


def test_main_path_lookup(tmp_path):
    input_file = tmp_path / 'in'
    input_file.write_text('')
    options.__PARSED_ARGS = None
    options.args([str(input_file), '/dev/null', 'true'])
    cli.ddsmt_main()
