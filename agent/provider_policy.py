"""One bounded SDK attempt. No redirects, ambient proxy, tools or automatic retries."""
TIMEOUT_MS = 12000


def http_options():
    from google.genai import types
    return types.HttpOptions(base_url='https://generativelanguage.googleapis.com',
        timeout=TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=1),
        client_args={'trust_env':False,'follow_redirects':False})
