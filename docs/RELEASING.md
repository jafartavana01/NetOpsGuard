# Application releases

`app/VERSION` is the authoritative NetOpsGuard application version, in `MAJOR.MINOR.PATCH.REVISION` format. The previously unversioned repository is initialized at `1.0.0.0`; this number does not certify production readiness or native device compatibility. The first published revision is `1.0.0.1`. The tac_plus-ng build version and commit are separate.

## Normal publication

With GitHub Actions enabled and repository contents-write permission, application changes pushed or merged to `main` trigger **Publish application version**. The workflow verifies the current main checkout, increments REVISION, and publishes the version commit plus matching `vMAJOR.MINOR.PATCH.REVISION` tag in one atomic Git push. A failed test, concurrent main update, existing tag or rejected push prevents publication. Never install an unpublished local bump as a released version.

Jobs are serialized. If several updates arrive together, the verified checkout may include them in one published release; the next queued job will not increment an already released application tree. Documentation-only and test-only changes do not trigger an automatic release. Version-only publication and `[skip ci]` prevent recursion. Local testing and unmerged pull requests never increment the version.

For an explicit major/minor/patch release, open **Actions → Publish application version → Run workflow**, select **main**, choose the increment, and leave **publish_prepared** off. Normal updates use `revision`; a patch/minor/major increment resets lower fields to zero. Documentation-only releases can be requested explicitly this way. Wait for the entire job to succeed and verify its tag before announcing publication. Git tags are the release record; this workflow does not create a separate GitHub Release announcement.

If main changes during verification, publication fails rather than rebasing or overwriting it. Rerun on a fresh checkout of main after review. A failure can leave an unpublished local version commit on the runner; do not push that stale commit manually. No force-push is used.

## Protected main: release pull request

Do not bypass branch protection to enable automatic commits. If main requires pull requests, use this supported alternative:

1. From a clean, verified checkout of current main, create a release branch.
2. Run `python scripts/release.py --prepare --part revision` (or patch/minor/major). This creates only the version commit; it publishes nothing.
3. Push the release branch, open a pull request, and merge through the normal review and required checks. If main or its version changed, recreate the release branch from current main and review again.
4. Run **Publish application version** manually on main with **publish_prepared** enabled. It verifies the merged tree and creates its immutable tag without writing main. The increment selector is ignored in this mode.

A rejected automatic job on a protected branch is not a published release. Keep protection intact and use the release PR path. Tag creation must also be allowed by the repository's tag rules. Do not overwrite a published tag to repair a failed deployment; publish another revision.

## Installed metadata

The installer copies `app/VERSION` with the application and writes `app/installed_release.json` containing that version and the clean source checkout's commit. Dirty checkouts and source archives show an unrecorded commit rather than a misleading one. There are no GitHub requests during normal version display. The sidebar, Settings and diagnostics show installed metadata; authenticated `GET /api/system/version` returns only application name, version and commit.

Deploy the exact reviewed release tag using the existing installation/upgrade procedure. Preserve the database, encryption material and configuration backups described in [Upgrade and recovery](UPGRADE.md). Application version publication does not upgrade servers automatically.
