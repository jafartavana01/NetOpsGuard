"""
app.run
========
The systemd ExecStart target is now this fixed script, not a direct
`uvicorn app.main:app --host X --port Y` CLI invocation. That static
command couldn't support runtime-configurable host/port/TLS -- systemd
unit files aren't meant to be rewritten on every settings change. This
script reads app.platform_settings at process start instead, so
changing web_port or https_enabled via the Settings GUI just means
"restart aaa-platform.service" (which the GUI already has a scoped
sudo grant to do -- see app.services.service_control), not "rebuild
and reinstall a systemd unit."

Self-signed HTTPS "just working" the first time a fresh install boots
depends on the installer having already generated a default
certificate before the service ever starts (installer/tls_setup.py)
-- this script does not generate one on the fly, so a missing
cert/key with https_enabled=true fails loudly at startup rather than
silently falling back to plaintext HTTP, which would be a much worse
failure mode for something explicitly turned on for security.
"""
from __future__ import annotations

import sys

import uvicorn

from .platform_settings import explicitly_set, load_settings


def main() -> None:
    settings = load_settings()

    kwargs = {
        "host": settings["web_host"],
        "port": settings["web_port"],
    }

    if settings["https_enabled"]:
        from pathlib import Path

        cert_path = Path(settings["tls_cert_path"])
        key_path = Path(settings["tls_key_path"])
        if not cert_path.exists() or not key_path.exists():
            # An EXPLICIT choice and a DEFAULT deserve different
            # handling. An administrator who deliberately turned HTTPS
            # on must not be silently downgraded to plaintext -- that
            # would hand them the opposite of what they asked for.
            #
            # But HTTPS is now on by DEFAULT, and refusing to start
            # because a certificate has not been generated yet would
            # mean a fresh or restored installation never comes up at
            # all. That fails the operator far worse than serving HTTP
            # with a loud warning until they generate one.
            if explicitly_set("https_enabled"):
                print(
                    f"https_enabled is true, but {cert_path} and/or {key_path} "
                    "do not exist. Refusing to start rather than silently fall "
                    "back to plaintext HTTP. Generate or restore a certificate "
                    "first (Platform Settings -> HTTPS in the GUI, or re-run "
                    "installer/tls_setup.py).",
                    file=sys.stderr,
                )
                sys.exit(1)

            print(
                "WARNING: HTTPS is enabled by default, but no certificate was "
                f"found at {cert_path}. Starting on plain HTTP so the platform "
                "is reachable. Generate a certificate under Platform Settings "
                "-> HTTPS, or run installer/tls_setup.py, then restart. Until "
                "then, administrator passwords and device secrets travel "
                "unencrypted.",
                file=sys.stderr,
            )
        else:
            kwargs["ssl_certfile"] = str(cert_path)
            kwargs["ssl_keyfile"] = str(key_path)

    uvicorn.run("app.main:app", **kwargs)


if __name__ == "__main__":
    main()
