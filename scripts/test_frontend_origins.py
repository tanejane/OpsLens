import pytest
from fastapi.testclient import TestClient
import api
from frontend_origins import configured_frontend_origins


def test_explicit_configuration_precedence(monkeypatch):
    monkeypatch.delenv('OPSLENS_FRONTEND_ORIGINS', raising=False)
    monkeypatch.setenv('OPSLENS_FRONTEND_ORIGIN', 'https://legacy.example')
    assert configured_frontend_origins() == ('https://legacy.example',)
    monkeypatch.setenv('OPSLENS_FRONTEND_ORIGINS', 'http://localhost:3000, http://192.168.100.20:3000')
    assert configured_frontend_origins() == ('http://localhost:3000', 'http://192.168.100.20:3000')


@pytest.mark.parametrize('value', ['', '*', 'null', 'https://*.example',
    'https://example/path', 'https://example/', 'https://user:pass@example',
    'https://example?x=1', 'https://example#fragment', 'http://example:bad'])
def test_invalid_configuration_fails_closed(monkeypatch, value):
    monkeypatch.setenv('OPSLENS_FRONTEND_ORIGINS', value)
    with pytest.raises(ValueError):
        configured_frontend_origins()


def test_host_is_not_an_implicit_origin_and_cookie_security_preserved(monkeypatch):
    monkeypatch.setattr(api, 'FRONTEND_ORIGINS', ('https://trusted.example',))
    with TestClient(api.app, base_url='https://attacker.example') as client:
        for origin in ('https://attacker.example', 'null', ''):
            assert client.post('/api/investigation-sessions', headers={'Origin': origin}).status_code == 403
        assert client.post('/api/investigation-sessions', headers={
            'Origin': 'https://trusted.example', 'Sec-Fetch-Site': 'cross-site'}).status_code == 403
        assert client.post('/api/investigation-sessions', headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
        result = client.post('/api/investigation-sessions', headers={'Origin': 'https://trusted.example'})
        assert result.status_code == 200
        for flag in ('HttpOnly', 'SameSite=strict', 'Secure', 'Path=/api'):
            assert flag in result.headers['set-cookie']
        # Preserve non-browser clients; absent Origin is not a grant of session ownership.
        assert client.post('/api/investigation-sessions').status_code == 200
