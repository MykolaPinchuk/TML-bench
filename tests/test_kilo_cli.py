import json

from orchestrator.kilo_cli import strip_ansi, write_clean_jsonl


def test_strip_ansi_removes_escape_sequences() -> None:
    s = "\x1b[2K\x1b[1A\x1b[2K\x1b[Ghello"
    assert strip_ansi(s) == "hello"


def test_write_clean_jsonl_filters_and_parses_tmp(tmp_path) -> None:
    src_path = tmp_path / "raw.jsonl"
    dst_path = tmp_path / "clean.jsonl"
    src_path.write_text(
        "\n".join(
            [
                "\x1b[2J\x1b[H{\"b\": 2, \"a\": 1}",
                "not json",
                "{\"ok\": true}",
                "{bad json",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    n = write_clean_jsonl(src_jsonl=src_path, dst_jsonl=dst_path)
    assert n == 2
    lines = [line for line in dst_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 2
    objs = [json.loads(line) for line in lines]
    assert objs[0] == {"a": 1, "b": 2}
    assert objs[1] == {"ok": True}
