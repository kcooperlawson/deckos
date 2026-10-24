"""Local Work safety boundaries and persistence, without running a model or touching user files."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pkg/deckos-settings/rootfs/usr/lib/deckos/work'))
from work_core import Store, Tools, save_edit, scoped, undo_edit


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


if __name__=='__main__':
    unittest.main()
