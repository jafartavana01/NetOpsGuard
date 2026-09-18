"""
installer.systemd_setup
=========================
Creates systemd services for the management API and for tac_plus-ng
(spec section 33), running each under the least-privilege service
account rather than root, with sane restart behavior and explicit
dependency ordering.

tac_plus-ng needs to bind TCP/49, a privileged port, while running as a
non-root user. AmbientCapabilities=CAP_NET_BIND_SERVICE is used for
that rather than running the daemon as root -- this is the standard
systemd mechanism for granting a single capability to an unprivileged
process.

CONFIRMED (from the built binary's own `-h` output, captured by
installer.upstream_build.discover_runtime_usage() and verified against
a live install): the config file is a bare positional argument, NOT a
`-C <file>` flag -- unlike legacy tac_plus, tac_plus-ng has no `-C`
option at all. Passing `-C` caused it to exit immediately with status
64 (EX_USAGE). The correct invocation is:

    tac_plus-ng [options] <configuration file> [<id>]

`-f` ("force staying in foreground") is used to keep it attached for
systemd Type=simple, which the same usage output confirms exists
specifically for this purpose -- so Type=simple is correct, not
Type=forking. The full option list as reported by this build:

    -P   parse configuration file, then quit
    -1   enable single-process ("degraded") mode
    -v   show version, then quit
    -b   force going to background
    -f   force staying in foreground
    -i <child-id>    select child configuration id
    -I <spawnd-id>   select spawnd configuration id
    -p <pid-file>    write master proc[ess id]

`-i`/`-I` (selecting a specific `id = ...` block when a config defines
several) are not used here -- our generated config defines exactly one
`spawnd` and one `tac_plus-ng` block, and the binary has run correctly
against that without needing either flag. If a future config ever
defines multiple same-typed blocks, this is the place to revisit.
"""
from __future__ import annotations

from pathlib import Path

from . import utils
from .app_install import SERVICE_USER, SERVICE_GROUP, INSTALL_ROOT, LOG_DIR

SYSTEMD_DIR = Path("/etc/systemd/system")

MANAGEMENT_UNIT_NAME = "aaa-platform.service"
TAC_PLUS_NG_UNIT_NAME = "tac-plus-ng.service"

MANAGEMENT_UNIT_TEMPLATE = """[Unit]
Description=AAA Management Platform (Web GUI / REST API)
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User={user}
Group={group}
WorkingDirectory={install_root}
Environment=AAA_PLATFORM_CONFIG=/etc/aaa-platform/config
ExecStart={python_bin} -m app.run
Restart=on-failure
RestartSec=3
StandardOutput=append:{log_dir}/application.log
StandardError=append:{log_dir}/application.log

# Hardening
# NOTE: NoNewPrivileges is deliberately NOT set here (unlike the
# tac_plus-ng unit below). This service legitimately needs to run
# `sudo -n systemctl ...` against the narrow, exact-match sudoers rule
# in installer/sudoers_setup.py to control tac_plus-ng (spec section
# 34) -- sudo's setuid escalation is exactly what NoNewPrivileges
# blocks, so setting it here would silently break service control
# with no obvious error. Every other hardening option that doesn't
# conflict with that requirement is still applied.
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
RestrictNamespaces=true
LockPersonality=true
PrivateDevices=true

# Every file this service creates is group-readable at most.
#
# A security audit found the generated tac_plus-ng configuration being
# written 0644 -- world-readable, containing every device's shared
# secret. The application now chmods those files explicitly, and this
# makes the same mistake impossible at the OS level for any file the
# service creates, including ones added later by code that forgets.
UMask=0027

# NOT set, deliberately:
#   RestrictAddressFamilies -- an incorrect list silently breaks either
#     the PostgreSQL socket or device SSH, and the safe list depends on
#     what the resolver and TLS stack use at runtime. Worth adding once
#     it can be verified on a real deployment rather than guessed.
#   CapabilityBoundingSet -- binding the management GUI to port 443 is
#     a supported configuration and needs CAP_NET_BIND_SERVICE, so a
#     bounding set chosen for the default port 8420 would break it.
ReadWritePaths={log_dir} /opt/aaa-platform/generated /opt/aaa-platform/backups /var/lib/aaa-platform /var/lib/sudo /etc/aaa-platform/config /etc/aaa-platform/tls

[Install]
WantedBy=multi-user.target
"""

TAC_PLUS_NG_UNIT_TEMPLATE = """[Unit]
Description=tac_plus-ng TACACS+/RADIUS daemon
After=network.target aaa-platform.service
Wants=aaa-platform.service

[Service]
Type=simple
User={user}
Group={group}
ExecStart={binary_path} -f /opt/aaa-platform/generated/tac_plus-ng.conf
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=3
AmbientCapabilities=CAP_NET_BIND_SERVICE
StandardOutput=append:{log_dir}/tac_plus-ng.log
StandardError=append:{log_dir}/tac_plus-ng.log

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
RestrictNamespaces=true
LockPersonality=true
PrivateDevices=true
UMask=0027

# CapabilityBoundingSet is NOT narrowed here even though the required
# capability is known (CAP_NET_BIND_SERVICE, for port 49): the daemon's
# full capability requirements were never verified against a real run,
# and a bounding set that is too tight fails at bind time with an error
# that looks nothing like its cause. AmbientCapabilities above already
# grants only the one capability it needs to acquire.
ReadWritePaths={log_dir}

[Install]
WantedBy=multi-user.target
"""


TACACS_WATCH_UNIT_TEMPLATE = """[Unit]
Description=NetOpsGuard TACACS+/RADIUS client observer
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={user}
Group={group}
WorkingDirectory={install_root}
ExecStart={python_bin} -m app.services.tacacs_watch
Environment=PYTHONPATH={install_root}
Restart=on-failure
RestartSec=10

# The ONLY reason this unit exists as a separate service.
#
# Observing connections to a port another process owns needs raw packet
# access. Granting CAP_NET_RAW to the web application would give a
# network-facing service the ability to read any traffic on the host --
# a large increase in what a flaw there could reach. This process does
# one thing, reads no payload, and holds no database connection.
AmbientCapabilities=CAP_NET_RAW
CapabilityBoundingSet=CAP_NET_RAW

NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
RestrictNamespaces=true
LockPersonality=true
UMask=0027
ReadWritePaths=/var/lib/aaa-platform

[Install]
WantedBy=multi-user.target
"""


TACACS_WATCH_UNIT_NAME = "netopsguard-tacacs-watch.service"
TACACS_WATCH_UNIT = TACACS_WATCH_UNIT_NAME


def write_tacacs_watch_unit(python_bin: str) -> Path:
    """
    Writes the client-observer unit.

    Kept OPTIONAL by the caller: the discovery feature degrades to
    log-only when this is not running, so an operator who would rather
    not grant CAP_NET_RAW anywhere simply does not enable it.
    """
    content = TACACS_WATCH_UNIT_TEMPLATE.format(
        user=SERVICE_USER,
        group=SERVICE_GROUP,
        install_root=INSTALL_ROOT,
        python_bin=python_bin,
    )
    path = SYSTEMD_DIR / TACACS_WATCH_UNIT_NAME
    path.write_text(content, encoding="utf-8")
    utils.ok(f"Wrote {path}")
    return path


def write_management_unit(python_bin: str = "/usr/bin/python3") -> Path:
    """
    WorkingDirectory is INSTALL_ROOT (/opt/aaa-platform), NOT APP_DIR
    (/opt/aaa-platform/app) -- caught via a real failed install
    (ModuleNotFoundError: No module named 'app'). ExecStart imports
    `app.main:app` as a package; that only resolves if the process's
    cwd is app/'s *parent*, so Python can find `app` as a package on
    sys.path. With cwd already inside app/, Python looked for a
    nested app/app/ that doesn't exist.
    """
    content = MANAGEMENT_UNIT_TEMPLATE.format(
        user=SERVICE_USER,
        group=SERVICE_GROUP,
        install_root=INSTALL_ROOT,
        python_bin=python_bin,
        log_dir=LOG_DIR,
    )
    path = SYSTEMD_DIR / MANAGEMENT_UNIT_NAME
    path.write_text(content, encoding="utf-8")
    utils.ok(f"Wrote {path}")
    return path


def write_tac_plus_ng_unit(binary_path: str) -> Path:
    content = TAC_PLUS_NG_UNIT_TEMPLATE.format(
        user=SERVICE_USER,
        group=SERVICE_GROUP,
        binary_path=binary_path,
        log_dir=LOG_DIR,
    )
    path = SYSTEMD_DIR / TAC_PLUS_NG_UNIT_NAME
    path.write_text(content, encoding="utf-8")
    utils.ok(f"Wrote {path}")
    return path


def reload_and_enable(units: list[str], *, start: bool = True) -> None:
    utils.run(["systemctl", "daemon-reload"])
    for unit in units:
        utils.run(["systemctl", "enable", unit])
        if start:
            utils.run(["systemctl", "restart", unit])
    utils.ok(f"Enabled and started: {', '.join(units)}")


def service_status(unit: str) -> str:
    result = utils.run(["systemctl", "is-active", unit], check=False)
    return result.stdout.strip() or "unknown"


def run_first_start_diagnostic(unit: str, *, wait_seconds: int = 3) -> tuple[bool, str]:
    """
    After starting a service for the first time, confirms it is
    actually still running rather than trusting the initial `systemctl
    restart` exit code (systemd reports success as soon as the process
    is spawned, even if it immediately crashes or double-forks in a way
    that breaks Type=simple). If it isn't active, returns diagnostic
    output explaining why.

    Both units redirect StandardOutput/StandardError to a log FILE
    (spec section 24: separate application logs from TACACS+ logs),
    not to the journal -- so `journalctl` alone only ever shows
    systemd's own lifecycle messages ("Started" / "Main process
    exited" / "Failed"), never the actual crash output. This was
    discovered the hard way: a real failed install where the journal
    gave no usable signal at all, and the real Python traceback was
    sitting in the log file the whole time. To avoid costing another
    round-trip next time, this now tails the unit's own log file in
    addition to the journal whenever one is known.
    """
    import time
    time.sleep(wait_seconds)
    status = service_status(unit)
    if status == "active":
        return True, status

    journal = utils.run(
        ["journalctl", "-u", unit, "-n", "40", "--no-pager"], check=False
    )
    output = journal.stdout + journal.stderr

    log_file = _LOG_FILE_BY_UNIT.get(unit)
    if log_file and log_file.exists():
        tail = utils.run(["tail", "-n", "60", str(log_file)], check=False)
        output += (
            f"\n\n--- last 60 lines of {log_file} (journalctl doesn't see this; "
            f"StandardOutput/StandardError are file-redirected for this unit) ---\n"
            f"{tail.stdout}{tail.stderr}"
        )
    return False, output


_LOG_FILE_BY_UNIT = {
    MANAGEMENT_UNIT_NAME: LOG_DIR / "application.log",
    TAC_PLUS_NG_UNIT_NAME: LOG_DIR / "tac_plus-ng.log",
}
