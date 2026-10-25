"""Offscreen Work UI checks. Demo mode never probes models or runs commands."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pkg/deckos-settings/rootfs/usr/lib/deckos/work'))
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from work_app import Work, Process, qss


class WorkUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(qss())

    def setUp(self):
        self.patch=patch.object(Process,'launch')
        self.launch=self.patch.start()
        self.window=Work(demo=True)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.launch.assert_not_called()
        self.patch.stop()

    def test_demo_has_task_history_changes_and_outputs(self):
        self.assertEqual(self.window.task_list.count(),3)
        self.assertEqual(self.window.change_list.count(),1)
        self.assertEqual(self.window.artifact_list.count(),2)
        self.assertIn('Sample conversation',self.window.chat.toPlainText())

    def test_delete_key_removes_a_task_after_asking(self):
        self.window.task_list.setCurrentRow(1)
        self.window.task_list.setFocus()
        with patch('work_app.QMessageBox.question',return_value=QMessageBox.Yes) as asked:
            QTest.keyClick(self.window.task_list,Qt.Key_Delete)
        asked.assert_called_once()
        self.assertEqual(self.window.task_list.count(),2)

    def test_busy_disables_task_switches_and_send(self):
        self.window.set_busy(True)
        self.assertFalse(self.window.send_button.isEnabled())
        self.assertFalse(self.window.task_list.isEnabled())
        self.assertTrue(self.window.stop_button.isEnabled())
        self.window.set_busy(False)
        self.assertTrue(self.window.send_button.isEnabled())

    def test_stream_and_approval_display(self):
        self.window.handle_event({'event':'token','text':'A streamed answer'})
        self.window.render_chat()
        self.assertIn('A streamed answer',self.window.chat.toPlainText())
        self.window.handle_event({'event':'approval','title':'Run tests','detail':'python3 -m unittest'})
        self.assertTrue(self.window.approval.isVisible())
        self.assertIn('unittest',self.window.approval_detail.toPlainText())
        self.window.answer(False)
        self.assertFalse(self.window.approval.isVisible())

    def test_demo_send_does_not_start_an_agent(self):
        self.window.input.setPlainText('Change a file')
        QTest.mouseClick(self.window.send_button,Qt.LeftButton)
        self.assertIn('Demo mode',self.window.status.text())

    def test_enter_sends_and_shift_enter_adds_a_line(self):
        sent=[]
        self.window.send=lambda:sent.append(self.window.input.toPlainText())
        self.window.input.setPlainText('hi')
        QTest.keyClick(self.window.input,Qt.Key_Return,Qt.ShiftModifier)
        self.assertEqual(sent,[])
        self.assertIn('\n',self.window.input.toPlainText())
        QTest.keyClick(self.window.input,Qt.Key_Return)
        self.assertEqual(len(sent),1)

    def test_chat_text_is_light_whatever_the_desktop_palette(self):
        from PySide6.QtGui import QColor
        self.assertGreater(QApplication.instance().palette().text().color().lightness(),180)


if __name__=='__main__':
    unittest.main()
