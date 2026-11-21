from app import formatter


def test_strips_markdown_and_code_blocks():
    raw = "# Hasil\n\n**Deploy** sukses. ```bash\ngit push\n``` Lihat https://x.io"
    out = formatter.for_speech(raw)
    assert "**" not in out and "```" not in out and "https://" not in out
    assert "blok kode" in out


def test_take_sentence_waits_for_punctuation():
    assert formatter.take_sentence(["Halo"]) is None
    assert formatter.take_sentence(["Halo, ini tes. Lanjut"]) == "Halo, ini tes."


def test_flush_limits_sentences():
    parts = ["Satu. Dua. Tiga. Empat. Lima. Enam."]
    out = formatter.flush(parts)
    assert out.count(".") <= formatter.MAX_SENTENCES
