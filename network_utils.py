import ssl
import warnings
from typing import Optional

import urllib3
import requests

# Disable only once
_PATCHED = False

def install_insecure_ssl(verify: bool | str | None = False, *, suppress_warnings: bool = True) -> None:
    """Globally disable (or customise) TLS verification for *all* outgoing
    `requests` *and* `httpx` HTTP clients.

    Parameters
    ----------
    verify
        What to pass as the ``verify`` kwarg in every outgoing request.
        ``False``  -> skip verification entirely (default).
        ``str``    -> path to an alternative CA bundle (e.g. certifi.where()   
                      or a custom PEM containing your corporate root CA).
    suppress_warnings
        If ``True`` (default) we silence ``InsecureRequestWarning`` to avoid
        console noise when verification is disabled.
    """
    global _PATCHED
    if _PATCHED:
        return

    if suppress_warnings:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        warnings.filterwarnings(
            "ignore",
            category=urllib3.exceptions.InsecureRequestWarning,
        )

    # ------------------------------------------------------------------
    # Monkey-patch requests
    # ------------------------------------------------------------------
    _orig_request = requests.Session.request

    def _patched_request(self, *args, **kwargs):
        # Respect an explicit verify kwarg supplied by caller, otherwise inject
        kwargs.setdefault("verify", verify)
        return _orig_request(self, *args, **kwargs)

    requests.Session.request = _patched_request  # type: ignore[method-assign]

    # ------------------------------------------------------------------
    # Monkey-patch httpx (used by openai>=1.0.0)
    # ------------------------------------------------------------------
    try:
        import httpx

        class _PatchedHTTPTransport(httpx.HTTPTransport):
            def __init__(self, **kw):
                kw.setdefault("verify", verify)
                super().__init__(**kw)

        # Replace default transport used by httpx.Client when none is provided
        httpx._transports.default_pyopenssl_transport = _PatchedHTTPTransport  # type: ignore[attr-defined]
    except ImportError:
        # httpx not installed – nothing to patch
        pass

    # ------------------------------------------------------------------
    # Monkey-patch stdlib ssl context for libraries that rely directly on
    # ssl.create_default_context (e.g. urllib3, pinecone-client)
    # ------------------------------------------------------------------
    if verify is False:
        ssl._create_default_https_context = ssl._create_unverified_context  # type: ignore[attr-defined]
    elif isinstance(verify, str):
        # Custom CA bundle path provided
        _orig_create_ctx = ssl.create_default_context

        def _custom_context(*args, **kwargs):
            kwargs.setdefault("cafile", verify)
            return _orig_create_ctx(*args, **kwargs)

        ssl._create_default_https_context = _custom_context  # type: ignore[attr-defined]

    # Also patch urllib3's create_urllib3_context so PoolManager disables cert checks
    _orig_create_urllib3_context = urllib3.util.ssl_.create_urllib3_context  # type: ignore[attr-defined]

    def _patched_create_urllib3_context(*args, **kwargs):
        ctx = _orig_create_urllib3_context(*args, **kwargs)
        if verify is False:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    urllib3.util.ssl_.create_urllib3_context = _patched_create_urllib3_context  # type: ignore[attr-defined]

    _PATCHED = True

__all__ = ["install_insecure_ssl"] 