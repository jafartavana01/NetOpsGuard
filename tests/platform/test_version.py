import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from app import version
from installer import app_install
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('release',ROOT/'scripts/release.py');release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)

class VersionTests(unittest.TestCase):
    def test_increments(self):
        for part,expected in [('revision','1.2.3.5'),('patch','1.2.4.0'),('minor','1.3.0.0'),('major','2.0.0.0')]:
            self.assertEqual(release.bump('1.2.3.4',part),expected)
    def test_invalid_versions(self):
        for value in ['1.2.3','1.2.3.4.5','01.2.3.4','1.0.0.dev','1.0.0.-1']:
            with self.assertRaises(ValueError):release.bump(value)
    def test_offline_metadata(self):
        with tempfile.TemporaryDirectory() as d,patch.object(version,'ROOT',Path(d)):
            p=Path(d);(p/'VERSION').write_text('1.2.3.4\n');(p/'installed_release.json').write_text(json.dumps({'version':'1.2.3.4','commit':'a'*40,'password':'never-return'}))
            self.assertEqual(version.metadata(),{'application':'NetOpsGuard','version':'1.2.3.4','commit':'a'*40})
    def test_stale_commit_is_not_reported(self):
        with tempfile.TemporaryDirectory() as d,patch.object(version,'ROOT',Path(d)):
            p=Path(d);(p/'VERSION').write_text('1.2.3.4');(p/'installed_release.json').write_text(json.dumps({'version':'1.2.3.3','commit':'a'*40}))
            self.assertIsNone(version.metadata()['commit'])
    def test_installer_archive_version_and_unknown_commit(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);src=root/'source';(src/'app').mkdir(parents=True);(src/'app/VERSION').write_text('1.2.3.4')
            dst=root/'installed/app';dst.parent.mkdir()
            with patch.object(app_install,'APP_DIR',dst):app_install.copy_application_source(src)
            self.assertEqual(json.loads((dst/'installed_release.json').read_text()),{'version':'1.2.3.4','commit':None})
    def test_installer_upgrade_preserves_configuration_and_replaces_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);src=root/'source';(src/'app').mkdir(parents=True)
            config=root/'config';config.mkdir();(config/'timezone.json').write_text('{"timezone":"Asia/Tehran"}')
            (config/'secret_encryption.key').write_text('fixture-key')
            dst=root/'installed/app';dst.parent.mkdir()
            with patch.object(app_install,'APP_DIR',dst),patch.object(app_install,'CONFIG_DIR',config):
                for value in ['1.2.3.4','1.2.3.5']:
                    (src/'app/VERSION').write_text(value);app_install.copy_application_source(src)
                    self.assertEqual(json.loads((dst/'installed_release.json').read_text())['version'],value)
            self.assertEqual((config/'timezone.json').read_text(),'{"timezone":"Asia/Tehran"}')
            self.assertEqual((config/'secret_encryption.key').read_text(),'fixture-key')

class ReleaseIntegration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.env={**os.environ,'GIT_AUTHOR_NAME':'Test','GIT_COMMITTER_NAME':'Test','GIT_AUTHOR_EMAIL':'test@example.test','GIT_COMMITTER_EMAIL':'test@example.test'}
        self.remote=self.root/'remote.git';self.run_git(self.root,'init','--bare',str(self.remote))
        self.one=self.root/'one';self.run_git(self.root,'clone',str(self.remote),str(self.one));self.run_git(self.one,'checkout','-b','main')
        (self.one/'app').mkdir();(self.one/'app/VERSION').write_text('1.2.3.4\n');self.run_git(self.one,'add','.');self.run_git(self.one,'commit','-m','initial');self.run_git(self.one,'push','origin','main')
        self.two=self.root/'two';self.run_git(self.root,'clone','-b','main',str(self.remote),str(self.two))
    def run_git(self,cwd,*args):return subprocess.check_output(['git',*args],cwd=cwd,env=self.env,stderr=subprocess.DEVNULL,text=True).strip()
    def publish(self,cwd):return subprocess.run(['python',str(ROOT/'scripts/release.py')],cwd=cwd,env=self.env,capture_output=True,text=True)
    def test_publish_tag_and_version_same_commit(self):
        result=self.publish(self.one);self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.run_git(self.remote,'rev-parse','refs/heads/main'),self.run_git(self.remote,'rev-parse','refs/tags/v1.2.3.5'))
    def test_stale_release_rejected_without_bump(self):
        self.assertEqual(self.publish(self.one).returncode,0)
        self.assertNotEqual(self.publish(self.two).returncode,0)
        self.assertEqual((self.two/'app/VERSION').read_text(),'1.2.3.4\n')
    def test_concurrent_release_has_one_winner(self):
        jobs=[subprocess.Popen(['python',str(ROOT/'scripts/release.py')],cwd=p,env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for p in (self.one,self.two)]
        for job in jobs:job.communicate(timeout=20)
        self.assertEqual(sum(j.returncode==0 for j in jobs),1)
        self.assertEqual(self.run_git(self.remote,'tag'),'v1.2.3.5')
        self.assertEqual(self.run_git(self.remote,'show','main:app/VERSION'),'1.2.3.5')
    def test_server_rejection_publishes_neither_tag_nor_main(self):
        old=self.run_git(self.remote,'rev-parse','main')
        hook=self.remote/'hooks/pre-receive';hook.write_text('#!/bin/sh\nexit 1\n');hook.chmod(0o755)
        self.assertNotEqual(self.publish(self.one).returncode,0)
        self.assertEqual(self.run_git(self.remote,'rev-parse','main'),old);self.assertEqual(self.run_git(self.remote,'tag'),'')

    def test_queued_automatic_release_does_not_increment_again(self):
        self.assertEqual(self.publish(self.one).returncode,0)
        self.run_git(self.one,'fetch','--tags')
        result=subprocess.run(['python',str(ROOT/'scripts/release.py'),'--automatic'],cwd=self.one,env=self.env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.run_git(self.remote,'tag'),'v1.2.3.5')

    def test_protected_branch_prepare_then_tag_publishes_no_main_write(self):
        r=subprocess.run(['python',str(ROOT/'scripts/release.py'),'--prepare'],cwd=self.one,env=self.env,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(self.run_git(self.remote,'tag'),'')
        self.assertEqual(self.run_git(self.remote,'show','main:app/VERSION'),'1.2.3.4')
        # Simulate reviewed PR merge via a permitted fast-forward.
        self.run_git(self.one,'push','origin','HEAD:main')
        merged=self.run_git(self.remote,'rev-parse','main')
        hook=self.remote/'hooks/pre-receive';hook.write_text('#!/bin/sh\nwhile read old new ref; do [ "$ref" != refs/heads/main ] || exit 1; done\n');hook.chmod(0o755)
        r=subprocess.run(['python',str(ROOT/'scripts/release.py'),'--publish-prepared'],cwd=self.one,env=self.env,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(self.run_git(self.remote,'rev-parse','main'),merged)
        self.assertEqual(self.run_git(self.remote,'rev-parse','v1.2.3.5'),merged)
    def test_automatic_after_documentation_does_not_increment(self):
        self.assertEqual(self.publish(self.one).returncode,0);self.run_git(self.one,'fetch','--tags')
        (self.one/'README.md').write_text('documentation');self.run_git(self.one,'add','.');self.run_git(self.one,'commit','-m','docs');self.run_git(self.one,'push','origin','HEAD:main')
        r=subprocess.run(['python',str(ROOT/'scripts/release.py'),'--automatic'],cwd=self.one,env=self.env,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(self.run_git(self.remote,'tag'),'v1.2.3.5')
