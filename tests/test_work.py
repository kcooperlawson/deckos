"""Local Work safety boundaries and persistence, without running a model or touching user files."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pkg/deckos-settings/rootfs/usr/lib/deckos/work'))
from unittest.mock import patch
from work_core import Store, Tools, detect_checks, fuzzy_replace, save_edit, scoped, undo_edit
import work_agent


class WorkTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.project=root/'project'
        self.project.mkdir()
        self.store=Store(root/'data')
        self.task=self.store.create(self.project)
        self.events=[]
        self.tools=Tools(self.store,self.task,{'auto_edit':True,'ask_commands':True},
                         lambda event,**data:self.events.append((event,data)),lambda *_:False)

    def tearDown(self):
        self.temp.cleanup()

    def test_scoped_files_reject_parent_and_symlink_escape(self):
        outside=Path(self.temp.name)/'outside'
        outside.mkdir()
        (self.project/'link').symlink_to(outside,target_is_directory=True)
        for name in ('../outside/secret','link/secret'):
            with self.assertRaises(ValueError):
                scoped(self.project,name)
        self.assertFalse((outside/'secret').exists())

    def test_saved_edits_and_undo_preserve_text_and_permissions(self):
        path=self.project/'script.py'
        original='print("café")\n'
        path.write_text(original)
        path.chmod(0o755)
        change=save_edit(self.store,self.task,path,b'print("new")\n')
        self.assertIn('+print("new")',change['diff'])
        self.assertEqual(path.stat().st_mode & 0o777,0o755)
        loaded=self.store.load(self.task['id'])
        undo_edit(self.store,loaded,change['id'])
        self.assertEqual(path.read_text(),original)
        self.assertTrue(self.store.list())

    def test_undo_refuses_to_overwrite_external_changes(self):
        path=self.project/'file.txt'
        change=save_edit(self.store,self.task,path,b'new')
        path.write_text('edited elsewhere')
        with self.assertRaises(ValueError):
            undo_edit(self.store,self.task,change['id'])
        self.assertEqual(path.read_text(),'edited elsewhere')

    def test_ambiguous_edit_cannot_change_file(self):
        path=self.project/'a.py'
        path.write_text('same\nsame\n')
        result=self.tools.call('edit_file',dict(path='a.py',old='same',new='new'))
        self.assertTrue(result.startswith('Error:'))
        self.assertEqual(path.read_text(),'same\nsame\n')

    def test_declined_command_does_not_run(self):
        result=self.tools.call('run_command',dict(command='touch marker',reason='test'))
        self.assertIn('declined',result)
        self.assertFalse((self.project/'marker').exists())

    def test_approved_command_runs_in_project_and_returns_errors(self):
        self.tools.confirm=lambda *_:True
        result=self.tools.call('run_command',dict(command='pwd; echo expected; exit 7',reason='test'))
        self.assertIn('exit 7',result)
        self.assertIn(str(self.project),result)
        self.assertIn('expected',result)
        self.assertTrue(any(event=='process' and not data['active'] for event,data in self.events))

    def test_destructive_command_is_refused_before_approval(self):
        self.tools.confirm=lambda *_:self.fail('Must not ask to approve a blocked command')
        result=self.tools.call('run_command',dict(command='wipefs /dev/sda',reason='test'))
        self.assertIn('Refused',result)

    def test_creation_of_new_file_can_be_undone(self):
        self.tools.call('write_file',dict(path='outputs/notes.md',content='# Hello\n'))
        self.assertEqual(len(self.task['artifacts']),1)
        change=self.task['changes'][-1]
        undo_edit(self.store,self.task,change['id'])
        self.assertFalse((self.project/'outputs/notes.md').exists())

    def test_invalid_task_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            self.store.load('../../outside')

    def test_fuzzy_edit_tolerates_lost_indentation_but_not_ambiguity(self):
        text='def f():\n    if x:\n        return 1\n    return 2\n'
        out=fuzzy_replace(text,'if x:\n    return 1','if x:\n    return 3')
        self.assertEqual(out,'def f():\n    if x:\n        return 3\n    return 2\n')
        self.assertIsNone(fuzzy_replace('a\n  b\na\n  b\n','a\nb','c'))
        self.assertIsNone(fuzzy_replace(text,'missing','x'))

    def test_checks_are_detected_from_project_files(self):
        self.assertIsNone(detect_checks(self.project))
        (self.project/'tests').mkdir()
        (self.project/'tests/test_a.py').write_text('')
        self.assertEqual(detect_checks(self.project),'python3 -m unittest discover -s tests -q')
        (self.project/'package.json').write_text('{"scripts":{"test":"jest"}}')
        self.assertEqual(detect_checks(self.project),'npm test --silent')

    def test_project_map_lists_definitions_and_test_command(self):
        (self.project/'app.py').write_text('class A:\n    def go(self):\n        pass\n\ndef main():\n    pass\n')
        result=Tools(self.store,self.task,{},lambda *a,**k:None,lambda *_:False).call('project_map',{})
        self.assertIn('class A:1 (go)',result)
        self.assertIn('def main:5',result)
        self.assertIn('py_compile app.py',result)

    def test_plan_is_saved_and_reported(self):
        result=self.tools.call('update_plan',{'items':[{'step':'Read','status':'done'},{'step':'Fix','status':'active'},{'step':'','status':'x'}]})
        self.assertIn('next: Fix',result)
        self.assertEqual(len(self.store.load(self.task['id'])['plan']),2)
        self.assertTrue(any(event=='plan' for event,_ in self.events))

    def test_only_a_passing_check_after_edits_counts_as_verified(self):
        self.tools.confirm=lambda *_:True
        self.tools.call('write_file',dict(path='a.py',content='x=1\n'))
        self.tools.call('run_command',dict(command='ls',reason='look'))
        self.assertLess(self.tools.verified,len(self.task['changes']))
        self.tools.call('run_checks',dict(command='python3 -m py_compile a.py'))
        self.assertEqual(self.tools.verified,len(self.task['changes']))

    def test_unverified_unplanned_work_is_sent_back_before_finishing(self):
        settings={'verify':True,'self_review':True,'model':'m'}
        state=dict(plan=0,verify=0,reviewed=False)
        self.task['plan']=[dict(step='Write tests',status='pending')]
        with patch.object(work_agent,'emit'):
            self.assertIn('Write tests',work_agent.follow_up(self.task,self.tools,0,'req',settings,state))
            self.task['plan'][0]['status']='done'
            self.tools.call('write_file',dict(path='a.py',content='x=1\n'))
            self.assertIn('Verify',work_agent.follow_up(self.task,self.tools,0,'req',settings,state))
            self.tools.verified=len(self.task['changes'])
            with patch.object(work_agent,'api',return_value={'message':{'content':'1. a.py: x is wrong'}}):
                self.assertIn('x is wrong',work_agent.follow_up(self.task,self.tools,0,'req',settings,state))
            self.assertEqual(work_agent.follow_up(self.task,self.tools,0,'req',settings,state),'')

    def test_deleting_an_existing_test_is_sent_back(self):
        path=self.project/'test_a.py'
        path.write_text('def test_keep():\n    pass\n\ndef test_hard():\n    assert False\n')
        refused=self.tools.call('write_file',dict(path='test_a.py',content='def test_keep():\n    pass\n'))
        self.assertIn('test_hard',refused)
        self.assertIn('test_hard',path.read_text())
        self.tools.request='Remove the test_hard test'
        self.tools.call('write_file',dict(path='test_a.py',content='def test_keep():\n    pass\n'))
        state=dict(plan=0,verify=0,reviewed=False)
        with patch.object(work_agent,'emit'):
            self.assertIn('test_hard',work_agent.follow_up(self.task,self.tools,0,'req',{'verify':False,'self_review':False},state))


if __name__=='__main__':
    unittest.main()
