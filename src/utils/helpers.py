from pathlib import Path
from typing import Optional
from typing import Union

def read_uploaded_text(uploaded_file) -> Union[str, None]:
    """Read uploaded file-like object (Streamlit) and return UTF-8 text or None.

    uploaded_file is expected to implement .read() returning bytes.
    """
    if uploaded_file is None:
        return None
    try:
        raw = uploaded_file.read()
        if isinstance(raw, bytes):
            return raw.decode('utf-8')
        return str(raw)
    except Exception:
        return None

def project_root() -> Path:
    """Return the project root path (two levels up from this file)."""
    return Path(__file__).resolve().parents[2]

def env_path(filename: str = '.env') -> Path:
    return project_root() / filename

def safe_get(d: dict, key: str, default=None):
    return d.get(key, default) if isinstance(d, dict) else default
