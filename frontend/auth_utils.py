import os
import requests
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv

# Resolve the absolute path to the root .env relative to this file
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:5000")


def clear_auth_state() -> None:
    """Clear all authentication-related keys from st.session_state."""
    keys_to_clear = ["access_token", "refresh_token", "username"]
    for key in keys_to_clear:
        if key in st.session_state:
            st.session_state[key] = None


def authorized_request(method: str, url: str, **kwargs) -> requests.Response:
    """Make an authorized HTTP request to the backend with automatic token refresh.

    Attaches Bearer access token, handles silent refresh on 401, updates session state
    tokens, and redirects to login on session expiry.

    Args:
        method: The HTTP method (GET, POST, etc.)
        url: The absolute backend endpoint URL.
        kwargs: Standard request kwargs (headers, json, data, etc.)

    Returns:
        The final requests.Response object.
    """
    # Initialize headers dictionary if not present
    headers = kwargs.get("headers", {})
    if headers is None:
        headers = {}

    # Attach Bearer token
    access_token = st.session_state.get("access_token")
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    kwargs["headers"] = headers

    # Execute original request
    try:
        response = requests.request(method, url, **kwargs)
    except Exception as exc:
        raise exc

    # Attempt silent token refresh on 401 Unauthorized
    if response.status_code == 401:
        refresh_token = st.session_state.get("refresh_token")
        if refresh_token:
            try:
                refresh_res = requests.post(
                    f"{BACKEND_URL}/auth/refresh",
                    json={"refresh_token": refresh_token},
                    timeout=10,
                )
                if refresh_res.status_code == 200:
                    data = refresh_res.json()
                    st.session_state.access_token = data.get("access_token")
                    st.session_state.refresh_token = data.get("refresh_token")  # rotated token

                    # Retry original request with new access token
                    headers["Authorization"] = f"Bearer {st.session_state.access_token}"
                    kwargs["headers"] = headers
                    return requests.request(method, url, **kwargs)
            except Exception:
                pass

        # If refresh fails, reset credentials and trigger login page reload
        clear_auth_state()
        st.session_state.session_expired_flag = True
        st.rerun()

    return response
