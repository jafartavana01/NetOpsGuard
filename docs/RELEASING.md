# Application versions and repository updates

`app/VERSION` is the authoritative NetOpsGuard application version, in `MAJOR.MINOR.PATCH.REVISION` format. The tac_plus-ng build version and Git commit are separate identifiers.

## Repository updates

Application updates are committed directly to the repository after verification, or merged through a reviewed pull request when branch protection requires it. GitHub Actions is not required. There is no automatic release workflow or automatic tag creation.

Include the version increment with each verified application update: normally increase REVISION by one, for example `1.0.0.1` to `1.0.0.2`. A patch release changes `1.0.0.2` to `1.0.1.0`; minor and major releases likewise reset the lower fields. Documentation-only changes need no increment unless a release is explicitly intended. Tests and local development never increment the version automatically.

Before committing, verify the latest main version and avoid overwriting concurrent updates. Do not force-push to publish an update. Update the changelog where operator-facing behavior changes. A version number does not replace database or native-device verification.

The optional `scripts/release.py` command remains available to maintainers who deliberately want Git version/tag publication from a clean verified checkout. It is not run automatically and is not needed to install repository updates.

## Installed metadata

The installer copies `app/VERSION` with the application and writes `app/installed_release.json` containing that version and the clean source checkout's commit. Dirty checkouts and source archives show an unrecorded commit rather than a misleading one. There are no GitHub requests during normal version display. The sidebar, Settings and diagnostics show installed metadata; authenticated `GET /api/system/version` returns only application name, version and commit.

Deploy the reviewed repository commit using the existing installation/upgrade procedure. Preserve the database, encryption material and configuration backups described in [Upgrade and recovery](UPGRADE.md). Updating the GitHub repository does not upgrade installed servers automatically.
