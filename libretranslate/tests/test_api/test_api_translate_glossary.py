import sys

import pytest
from argostranslate import package

from libretranslate.app import create_app
from libretranslate.main import get_args

if not any(p.from_code == "en" and p.to_code == "id" for p in package.get_installed_packages()):
    pytest.skip("needs the en-id model", allow_module_level=True)

TEXT = "Acme Corp opens a new shop in Springfield next month."


def make_client(tmp_path=None, default_terms=None):
    sys.argv = ['', '--load-only', 'en,id', '--req-limit', '-1']
    if default_terms:
        path = tmp_path / "glossary.txt"
        path.write_text("\n".join(default_terms), encoding="utf-8")
        sys.argv += ['--glossary-file', str(path)]
    return create_app(get_args()).test_client()


@pytest.fixture(scope="module")
def client():
    return make_client()


def post(client, **kwargs):
    return client.post("/translate", json={"source": "en", "target": "id", **kwargs})


def test_glossary_passes_terms_through(client):
    response = post(client, q=TEXT, glossary=["Acme Corp", "Springfield"])
    text = response.get_json()["translatedText"]
    assert response.status_code == 200
    assert "Acme Corp" in text
    assert "Springfield" in text
    assert "XTERM" not in text
    assert "glossaryMissing" not in response.get_json()


def test_glossary_form_data(client):
    response = client.post("/translate", data={
        "q": TEXT, "source": "en", "target": "id", "glossary": ["Acme Corp", "Springfield"],
    })
    assert "Acme Corp" in response.get_json()["translatedText"]


def test_glossary_batch_and_alternatives(client):
    response = post(client, q=[TEXT, "I like acme corp."], glossary=["Acme Corp"], alternatives=2)
    data = response.get_json()
    assert "Acme Corp" in data["translatedText"][0]
    assert "acme corp" in data["translatedText"][1]
    assert not any("XTERM" in alt.upper() for alts in data["alternatives"] for alt in alts)


def test_glossary_html(client):
    response = post(client, q='<p><a href="https://acme.example/">Acme Corp</a> sells good shoes.</p>',
                    format="html", glossary=["Acme Corp"])
    text = response.get_json()["translatedText"]
    assert '<a href="https://acme.example/">Acme Corp</a>' in text
    assert "XTERM" not in text


def test_glossary_invalid(client):
    assert post(client, q=TEXT, glossary=5).status_code == 400


def test_glossary_absent_changes_nothing(client):
    assert "XTERM" not in post(client, q=TEXT).get_json()["translatedText"]


def test_default_glossary_file(tmp_path):
    client = make_client(tmp_path, ["Acme Corp"])
    assert "Acme Corp" in post(client, q=TEXT).get_json()["translatedText"]
