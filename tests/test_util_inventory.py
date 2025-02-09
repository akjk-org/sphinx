"""Test inventory util functions."""

import posixpath
import zlib
from io import BytesIO

from sphinx.testing.util import SphinxTestApp
from sphinx.util.inventory import InventoryFile

inventory_v1 = b'''\
# Sphinx inventory version 1
# Project: foo
# Version: 1.0
module mod foo.html
module.cls class foo.html
'''

inventory_v2 = b'''\
# Sphinx inventory version 2
# Project: foo
# Version: 2.0
# The remainder of this file is compressed with zlib.
''' + zlib.compress(b'''\
module1 py:module 0 foo.html#module-module1 Long Module desc
module2 py:module 0 foo.html#module-$ -
module1.func py:function 1 sub/foo.html#$ -
module1.Foo.bar py:method 1 index.html#foo.Bar.baz -
CFunc c:function 2 cfunc.html#CFunc -
std cpp:type 1 index.html#std -
std::uint8_t cpp:type 1 index.html#std_uint8_t -
foo::Bar cpp:class 1 index.html#cpp_foo_bar -
foo::Bar::baz cpp:function 1 index.html#cpp_foo_bar_baz -
foons cpp:type 1 index.html#foons -
foons::bartype cpp:type 1 index.html#foons_bartype -
a term std:term -1 glossary.html#term-a-term -
ls.-l std:cmdoption 1 index.html#cmdoption-ls-l -
docname std:doc -1 docname.html -
foo js:module 1 index.html#foo -
foo.bar js:class 1 index.html#foo.bar -
foo.bar.baz js:method 1 index.html#foo.bar.baz -
foo.bar.qux js:data 1 index.html#foo.bar.qux -
a term including:colon std:term -1 glossary.html#term-a-term-including-colon -
''')

inventory_v2_not_having_version = b'''\
# Sphinx inventory version 2
# Project: foo
# Version:
# The remainder of this file is compressed with zlib.
''' + zlib.compress(b'''\
module1 py:module 0 foo.html#module-module1 Long Module desc
''')


def test_read_inventory_v1():
    f = BytesIO(inventory_v1)
    invdata = InventoryFile.load(f, '/util', posixpath.join)
    assert invdata['py:module']['module'] == \
        ('foo', '1.0', '/util/foo.html#module-module', '-')
    assert invdata['py:class']['module.cls'] == \
        ('foo', '1.0', '/util/foo.html#module.cls', '-')


def test_read_inventory_v2():
    f = BytesIO(inventory_v2)
    invdata = InventoryFile.load(f, '/util', posixpath.join)

    assert len(invdata['py:module']) == 2
    assert invdata['py:module']['module1'] == \
        ('foo', '2.0', '/util/foo.html#module-module1', 'Long Module desc')
    assert invdata['py:module']['module2'] == \
        ('foo', '2.0', '/util/foo.html#module-module2', '-')
    assert invdata['py:function']['module1.func'][2] == \
        '/util/sub/foo.html#module1.func'
    assert invdata['c:function']['CFunc'][2] == '/util/cfunc.html#CFunc'
    assert invdata['std:term']['a term'][2] == \
        '/util/glossary.html#term-a-term'
    assert invdata['std:term']['a term including:colon'][2] == \
        '/util/glossary.html#term-a-term-including-colon'


def test_read_inventory_v2_not_having_version():
    f = BytesIO(inventory_v2_not_having_version)
    invdata = InventoryFile.load(f, '/util', posixpath.join)
    assert invdata['py:module']['module1'] == \
        ('foo', '', '/util/foo.html#module-module1', 'Long Module desc')


def _write_appconfig(dir, language, prefix=None):
    prefix = prefix or language
    (dir / prefix).makedirs()
    (dir / prefix / 'conf.py').write_text(f'language = "{language}"', encoding='utf8')
    (dir / prefix / 'index.rst').write_text('index.rst', encoding='utf8')
    assert sorted((dir / prefix).listdir()) == ['conf.py', 'index.rst']
    assert (dir / prefix / 'index.rst').exists()
    return (dir / prefix)


def _build_inventory(srcdir):
    app = SphinxTestApp(srcdir=srcdir)
    app.build()
    app.cleanup()
    return (app.outdir / 'objects.inv')


def test_inventory_localization(tempdir):
    # Build an app using Estonian (EE) locale
    srcdir_et = _write_appconfig(tempdir, "et")
    inventory_et = _build_inventory(srcdir_et)

    # Build the same app using English (US) locale
    srcdir_en = _write_appconfig(tempdir, "en")
    inventory_en = _build_inventory(srcdir_en)

    # Ensure that the inventory contents differ
    assert inventory_et.read_bytes() != inventory_en.read_bytes()


def test_inventory_reproducible(tempdir, monkeypatch):
    with monkeypatch.context() as m:
        # Configure reproducible builds
        # See: https://reproducible-builds.org/docs/source-date-epoch/
        m.setenv("SOURCE_DATE_EPOCH", "0")

        # Build an app using Estonian (EE) locale
        srcdir_et = _write_appconfig(tempdir, "et")
        reproducible_inventory_et = _build_inventory(srcdir_et)

        # Build the same app using English (US) locale
        srcdir_en = _write_appconfig(tempdir, "en")
        reproducible_inventory_en = _build_inventory(srcdir_en)

    # Also build the app using Estonian (EE) locale without build reproducibility enabled
    srcdir_et = _write_appconfig(tempdir, "et", prefix="localized")
    localized_inventory_et = _build_inventory(srcdir_et)

    # Ensure that the reproducible inventory contents are identical
    assert reproducible_inventory_et.read_bytes() == reproducible_inventory_en.read_bytes()

    # Ensure that inventory contents are different between a localized and non-localized build
    assert reproducible_inventory_et.read_bytes() != localized_inventory_et.read_bytes()
