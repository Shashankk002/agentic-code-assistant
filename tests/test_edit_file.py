from tools.edit_file import edit_file


def test_edit_file_replaces_unique_match(tmp_path):
    f = tmp_path / "unique.txt"
    f.write_text("hello world")

    result = edit_file(str(f), "hello", "goodbye")

    assert "Successfully updated" in result
    assert f.read_text() == "goodbye world"


def test_edit_file_refuses_ambiguous_match(tmp_path):
    f = tmp_path / "ambiguous.txt"
    f.write_text("foo\nfoo\n")

    result = edit_file(str(f), "foo", "bar")

    # Must refuse rather than guess which occurrence to replace.
    assert "occurs 2 times" in result
    assert f.read_text() == "foo\nfoo\n"  # file must be untouched


def test_edit_file_refuses_missing_text(tmp_path):
    f = tmp_path / "no_match.txt"
    f.write_text("hello world")

    result = edit_file(str(f), "goodbye", "hi")

    assert "not found" in result
    assert f.read_text() == "hello world"


def test_edit_file_missing_file(tmp_path):
    missing = tmp_path / "does_not_exist.txt"

    result = edit_file(str(missing), "a", "b")

    assert "File not found" in result
