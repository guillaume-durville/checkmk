#!/usr/bin/env python

import re
from bs4 import BeautifulSoup as bs
import __builtin__
import pytest

from tools import compare_html, gentest, compare_and_empty, bcolors

from cmk.gui.i18n import _
import cmk.gui.htmllib as htmlllib
import cmk.gui.http as http
import cmk.gui.table as table
from cmk.gui.table import Table
from cmk.gui.globals import html


def read_out_simple_table(text):
    assert type(text) in [ str, unicode ]
    # Get the contents of the table as a list of lists
    data = []
    for row in bs(text, 'html5lib').findAll('tr'):
        columns = row.findAll('th')
        if not columns:
            columns = row.findAll('td')
        row_data = []
        for cell in columns:
            cell = re.sub(r'\s', '', re.sub(r'<[^<]*>', '', cell.text))
            row_data.append(cell)
        data.append(row_data)
    return data


def read_out_csv(text, separator):
    # Get the contents of the table as a list of lists
    data = []
    for row in text.split('\n'):
        columns = row.split(separator)
        data.append([re.sub(r'\s', '', re.sub(r'<[^<]*>', '', cell)) for cell in columns])
    data = [row for row in data if not all(cell == '' for cell in row)]
    return data



def test_basic(register_builtin_html):
    id = 0
    title = " TEST "

    table = Table(id, title, searchable=False, sortable=False)
    table.row()
    table.cell("A", "1")
    table.cell("B", "2")
    table.row()
    table.cell("A", "1")
    table.cell("C", "4")
    table.end()

    written_text = "".join(html.response.flush_output())
    assert read_out_simple_table(written_text) == [[u'A', u'B'], [u'1', u'2'], [u'1', u'4']]


def test_plug(register_builtin_html):
    id = 0
    title = " TEST "

    table = Table(id, title, searchable=False, sortable=False)
    table.row()
    table.cell("A", "1")
    html.write("a")
    table.cell("B", "2")
    html.write("b")
    table.row()
    table.cell("A", "1")
    html.write("a")
    table.cell("C", "4")
    html.write("c")
    table.end()

    written_text = "".join(html.response.flush_output())
    assert read_out_simple_table(written_text) == [[u'A', u'B'], [u'1a', u'2b'], [u'1a', u'4c']]


def test_context(register_builtin_html):
    table_id = 0
    rows    = [ (i, i**3) for i in range(10) ]
    header  = ["Number", "Cubical"]

    with table.open_table(table_id=table_id, searchable=False, sortable=False):
        for row in rows:
            table.row()
            for i in range(len(header)):
                table.cell(_(header[i]), row[i])

    written_text = "".join(html.response.flush_output())
    data = read_out_simple_table(written_text)
    assert data.pop(0) == header
    data = [ tuple(map(int, row)) for row in data if row and row[0]]
    assert data == rows


def test_nesting(register_builtin_html):
    id = 0
    title = " TEST "

    table = Table(id, title, searchable=False, sortable=False)
    table.row()
    table.cell("A", "1")
    table.cell("B", "")

    t2 = Table(id+1, title+"2", searchable=False, sortable=False)
    t2.row()
    t2.cell("_", "+")
    t2.cell("|", "-")
    t2.end()

    table.end()
    written_text = "".join(html.response.flush_output())
    assert compare_html(written_text, '''<h3>  TEST </h3>
                            <script type="text/javascript">\nupdate_headinfo(\'1 row\');\n</script>
                            <table class="data oddeven">
                            <tr>  <th>   A  </th>  <th>   B  </th> </tr>
                            <tr class="data odd0">  <td>   1  </td>  <td>
                                <h3> TEST 2</h3>
                                <script type="text/javascript">\nupdate_headinfo(\'1 row\');\n</script>
                                <table class="data oddeven">
                                <tr><th>_</th><th>|</th></tr>
                                <tr class="data odd0"><td>+</td><td>-</td></tr>
                                </table>  </td>
                            </tr>
                            </table>'''), written_text


def test_nesting_context(register_builtin_html):
    id = 0
    title = " TEST "

    with table.open_table(table_id=id, title=title, searchable=False, sortable=False):
        table.row()
        table.cell("A", "1")
        table.cell("B", "")
        with table.open_table(id+1, title+"2", searchable=False, sortable=False):
            table.row()
            table.cell("_", "+")
            table.cell("|", "-")

    written_text = "".join(html.response.flush_output())
    assert compare_html(written_text, '''<h3>  TEST </h3>
                            <script type="text/javascript">\nupdate_headinfo(\'1 row\');\n</script>
                            <table class="data oddeven">
                            <tr>  <th>   A  </th>  <th>   B  </th> </tr>
                            <tr class="data odd0">  <td>   1  </td>  <td>
                                <h3> TEST 2</h3>
                                <script type="text/javascript">\nupdate_headinfo(\'1 row\');\n</script>
                                <table class="data oddeven">
                                <tr><th>_</th><th>|</th></tr>
                                <tr class="data odd0"><td>+</td><td>-</td></tr>
                                </table>  </td>
                            </tr>
                            </table>'''), written_text


@pytest.mark.parametrize("sortable", [ True, False ])
@pytest.mark.parametrize("searchable", [ True, False ])
@pytest.mark.parametrize("limit", [ None, 2 ])
@pytest.mark.parametrize("output_format", [ "html", "csv" ])
def test_table_cubical(register_builtin_html, monkeypatch, sortable, searchable, limit, output_format):
    # TODO: Better mock the access to save_user in table.*
    def save_user_mock(name, data, user, unlock=False):
        pass
    import cmk.gui.config as config
    monkeypatch.setattr(config, "save_user_file", save_user_mock)

    # Test data
    rows = [ (i, i**3) for i in range(10) ]
    header = ["Number", "Cubical"]

    # Table options
    table_id = 0
    title = " TEST "
    separator = ';'
    html.add_var('_%s_sort'   % table_id, "1,0")
    html.add_var('_%s_actions' % table_id, '1')

    # Table construction
    table.begin(table_id      = table_id,
                title         = title,
                sortable      = sortable,
                searchable    = searchable,
                limit         = limit,
                output_format = output_format)
    for row in rows:
        table.row()
        for i in range(len(header)):
            table.cell(_(header[i]), row[i])
    table.end()

    # Get generated html
    written_text = "".join(html.response.flush_output())

    # Data assertions
    assert output_format in ['html', 'csv'], 'Fetch is not yet implemented'
    if output_format == 'html':
        data = read_out_simple_table(written_text)
        assert data.pop(0) == header, 'Wrong header'
    elif output_format == 'csv':
        data = read_out_csv(written_text, separator)
        limit = len(data)
        assert data.pop(0) == header, 'Wrong header'
    else:
        raise Exception('Not yet implemented')

    # Reconstruct table data
    data = [ tuple(map(int, row)) for row in data if row and row[0]]
    if limit is None:
        limit = len(rows)

    # Assert data correctness
    assert len(data) <= limit, 'Wrong number of rows: Got %s, should be <= %s' % (len(data), limit)
    assert data == rows[:limit], "Incorrect data: %s\n\nVS\n%s" % (data, rows[:limit])