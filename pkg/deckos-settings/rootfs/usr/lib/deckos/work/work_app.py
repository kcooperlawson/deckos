"""DeckOS Work: a native, local workspace for code, documents and images."""
import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'hub'))
from PySide6.QtCore import QDir, QProcess, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase, QIcon, QKeySequence, QPixmap, QShortcut, QTextCursor, QPalette, QColor
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFileSystemModel,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
    QScrollArea, QSpinBox, QSplitter, QStackedWidget, QTabWidget, QTextBrowser, QTreeView,
    QVBoxLayout, QWidget)
import hub_style as S
from hub_widgets import Card, button, icon_label, label, row
from work_core import DATA, Store, atomic_json, preferences, scoped, undo_edit


def text(value='',kind=None):
    lab=label(str(value),kind)
    lab.setTextFormat(Qt.PlainText)
    return lab


def qss():
    return S.qss()+f'''
QLineEdit,QSpinBox {{ background:{S.SURFACE};border:1px solid {S.BORDER};border-radius:7px;padding:8px; }}
QTextBrowser {{ background:{S.BG};border:none;padding:12px; }}
QListWidget,QTreeView {{ background:transparent;border:none;outline:none; }}
QListWidget::item {{ padding:11px 8px;border-radius:6px;color:{S.SUBTEXT}; }}
QListWidget::item:selected {{ background:#1A2A43;color:{S.TEXT}; }}
QTreeView::item {{ padding:5px; }}
QHeaderView::section {{ background:{S.SURFACE};color:{S.SUBTEXT};border:none;padding:6px; }}
QTabWidget::pane {{ border:1px solid {S.BORDER};border-radius:8px; }}
QTabBar::tab {{ background:transparent;color:{S.SUBTEXT};padding:10px 13px; }}
QTabBar::tab:selected {{ color:{S.TEXT};border-bottom:2px solid {S.P.accent}; }}
QLabel#hero {{ font-size:27pt;font-weight:600; }}
#approval {{ background:#282216;border:1px solid #735B2B;border-radius:9px; }}
#composer {{ background:{S.SURFACE};border:1px solid {S.BORDER};border-radius:11px; }}
#composer QPlainTextEdit {{ background:transparent;border:none;font-family:Inter;font-size:11pt; }}
#status {{ color:{S.SUBTEXT};font-size:9pt; }}
QSplitter::handle {{ background:{S.BORDER};width:1px; }}
'''


class Process(QProcess):
    def __init__(self,owner,callback,done):
        super().__init__(owner)
        self.callback,self.done=callback,done
        self.buffer=b''
        self.pid_group=0
        self.children=set()
        self.readyReadStandardOutput.connect(self.read)
        self.readyReadStandardError.connect(self.stderr)
        self.finished.connect(self.finish)
        self.errorOccurred.connect(self.error)

    def launch(self,command,request):
        self.started.connect(lambda:self.write((json.dumps(request)+'\n').encode()))
        self.start(sys.executable,['-u',str(HERE/'work_agent.py'),command])

    def read(self):
        self.buffer+=bytes(self.readAllStandardOutput())
        while b'\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\n',1)
            try:
                event=json.loads(line)
                if not isinstance(event,dict) or 'event' not in event:
                    raise ValueError()
                if event['event']=='ready':
                    self.pid_group=self.processId()
                elif event['event']=='process':
                    self.children.add(event['pid']) if event['active'] else self.children.discard(event['pid'])
                self.callback(event)
            except ValueError:
                self.callback({'event':'console','text':line.decode(errors='replace')+'\n'})

    def stderr(self):
        self.callback({'event':'console','text':bytes(self.readAllStandardError()).decode(errors='replace')})

    def error(self,error):
        if error==QProcess.FailedToStart:
            self.callback({'event':'error','text':self.errorString()})
            self.done(1)

    def finish(self,code,_status):
        self.read()
        self.stderr()
        self.done(code)

    def approve(self,value):
        self.write((json.dumps({'approve':bool(value)})+'\n').encode())

    def stop(self,force=False):
        sig=signal.SIGKILL if force else signal.SIGTERM
        for pid in [*self.children,*([self.pid_group] if self.pid_group else [])]:
            try:
                os.killpg(pid,sig)
            except ProcessLookupError:
                pass
        if not self.pid_group and self.state()!=QProcess.NotRunning:
            self.kill() if force else self.terminate()


class Work(QWidget):
    def __init__(self,demo=False,workspace=None):
        super().__init__()
        self.demo=demo
        self.store=Store()
        self.settings=preferences() if not demo else dict(model='gpt-oss:20b',auto_edit=True,ask_commands=True,
            image_model='stabilityai/stable-diffusion-xl-base-1.0',image_size=1024,image_steps=20)
        self.task=None
        self.workspace=str(workspace or self.settings.get('workspace',''))
        self.active=self.probe=None
        self.busy=False
        self.attached=[]
        self.streaming=''
        self.pending_prompt=''
        self.setObjectName('root')
        self.setAttribute(Qt.WA_StyledBackground,True)
        self.setWindowTitle('DeckOS Work'+(' — Demo' if demo else ''))
        self.setWindowIcon(QIcon(str(HERE.parents[2]/'share/deckos/branding/work-logo.svg')))
        self.resize(1440,930)
        self.setMinimumSize(1120,740)
        outer=QHBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        outer.setSpacing(0)
        side=QFrame()
        side.setObjectName('sidebar')
        side.setFixedWidth(225)
        sl=QVBoxLayout(side)
        sl.setContentsMargins(15,24,15,20)
        sl.addWidget(row(icon_label('ai',S.P.accent,30),text('DeckOS Work','brand'),stretch=False))
        sl.addWidget(text('Your ideas. Your machine.','muted'))
        sl.addSpacing(24)
        self.new_button=button('New task','primary',self.new_task,icon='plus')
        sl.addWidget(self.new_button)
        self.folder_button=button('Open project folder',slot=self.choose_workspace,icon='folder')
        sl.addWidget(self.folder_button)
        self.folder_label=text('No folder selected','muted')
        sl.addWidget(self.folder_label)
        sl.addSpacing(12)
        sl.addWidget(text('RECENT TASKS','kicker'))
        self.task_list=QListWidget()
        self.task_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.task_list.setTextElideMode(Qt.ElideRight)
        self.task_list.itemClicked.connect(self.select_task)
        sl.addWidget(self.task_list,1)
        sl.addWidget(button('Workspace','nav',lambda:self.stack.setCurrentIndex(0),icon='code'))
        sl.addWidget(button('Image studio','nav',lambda:self.stack.setCurrentIndex(1),icon='image'))
        sl.addWidget(button('Models && tools','nav',lambda:self.stack.setCurrentIndex(2),icon='sliders'))
        sl.addSpacing(10)
        sl.addWidget(text('●  Local models · no API credits','muted'))
        if demo:
            sl.addWidget(text('DEMO · sample conversation','eyebrow'))
        outer.addWidget(side)
        self.stack=QStackedWidget()
        outer.addWidget(self.stack,1)
        self.build_workspace()
        self.build_images()
        self.build_settings()
        self.render_timer=QTimer(self)
        self.render_timer.setSingleShot(True)
        self.render_timer.timeout.connect(self.render_chat)
        QShortcut(QKeySequence('Ctrl+Return'),self,self.send)
        if demo:
            self.demo_data()
        else:
            self.refresh_tasks()
            if self.workspace and Path(self.workspace).is_dir():
                self.set_workspace(self.workspace)
            self.render_chat()
            QTimer.singleShot(0,self.check_tools)

    def build_workspace(self):
        page=QWidget()
        layout=QVBoxLayout(page)
        layout.setContentsMargins(25,22,25,20)
        head=QHBoxLayout()
        self.task_title=text('Make something worth keeping.','title')
        head.addWidget(self.task_title,1)
        self.mode=QComboBox()
        self.mode.addItems(['Work','Code','Create'])
        head.addWidget(self.mode)
        self.model_combo=QComboBox()
        self.model_combo.setMinimumWidth(170)
        self.model_combo.currentTextChanged.connect(self.model_changed)
        head.addWidget(self.model_combo)
        layout.addLayout(head)
        split=QSplitter(Qt.Horizontal)
        center=QWidget()
        cv=QVBoxLayout(center)
        cv.setContentsMargins(0,0,12,0)
        self.chat=QTextBrowser()
        self.chat.setOpenExternalLinks(False)
        palette=self.chat.palette()
        palette.setColor(QPalette.Link,QColor(S.P.accent))
        self.chat.setPalette(palette)
        self.chat.anchorClicked.connect(self.open_link)
        self.chat.document().setDefaultStyleSheet('body{font-family:Inter;color:#E8EAF0;} pre,code{font-family:monospace;background:#171A21;} h3{color:#8C94A6;}')
        cv.addWidget(self.chat,1)
        self.approval=QFrame()
        self.approval.setObjectName('approval')
        av=QVBoxLayout(self.approval)
        self.approval_title=text('Approve this command?','cardTitle')
        self.approval_detail=QPlainTextEdit()
        self.approval_detail.setReadOnly(True)
        self.approval_detail.setMaximumHeight(100)
        av.addWidget(self.approval_title)
        av.addWidget(self.approval_detail)
        av.addWidget(row(button('Allow once','primary',lambda:self.answer(True)),
                         button('Decline',slot=lambda:self.answer(False))))
        cv.addWidget(self.approval)
        self.approval.hide()
        composer=QFrame()
        composer.setObjectName('composer')
        compose=QVBoxLayout(composer)
        compose.setContentsMargins(12,10,12,10)
        self.input=QPlainTextEdit()
        self.input.setPlaceholderText('Describe the work. Read a project, fix code, make a report, create an image…')
        self.input.setFixedHeight(83)
        compose.addWidget(self.input)
        controls=QHBoxLayout()
        self.attach_button=button('Attach files',slot=self.attach,icon='plus')
        controls.addWidget(self.attach_button)
        self.attachment_label=text('','muted')
        controls.addWidget(self.attachment_label,1)
        self.stop_button=button('Stop',slot=self.stop,icon='stop')
        self.stop_button.setEnabled(False)
        controls.addWidget(self.stop_button)
        self.send_button=button('Start task','primary',self.send,icon='arrow-up')
        controls.addWidget(self.send_button)
        compose.addLayout(controls)
        cv.addWidget(composer)
        self.status=text('Choose a project folder to get started.','status')
        cv.addWidget(self.status)
        split.addWidget(center)
        self.tabs=QTabWidget()
        self.tabs.setMinimumWidth(285)
        files=QWidget()
        fl=QVBoxLayout(files)
        self.files=QTreeView()
        self.file_model=QFileSystemModel(self)
        self.file_model.setFilter(QDir.NoDotAndDotDot | QDir.AllDirs | QDir.Files)
        self.files.setModel(self.file_model)
        self.files.setHeaderHidden(True)
        for i in range(1,4):
            self.files.hideColumn(i)
        self.files.doubleClicked.connect(self.preview_file)
        fl.addWidget(self.files)
        self.file_preview=QPlainTextEdit()
        self.file_preview.setReadOnly(True)
        self.file_preview.setPlaceholderText('Double-click a file to preview it.')
        self.file_preview.setMaximumHeight(230)
        fl.addWidget(self.file_preview)
        self.tabs.addTab(files,'Files')
        changes=QWidget()
        cl=QVBoxLayout(changes)
        self.change_list=QListWidget()
        self.change_list.currentRowChanged.connect(self.show_change)
        self.diff=QPlainTextEdit()
        self.diff.setReadOnly(True)
        self.diff.setPlaceholderText('Edits appear here with a diff and a backup.')
        self.undo_button=button('Undo selected edit',slot=self.undo,icon='undo')
        cl.addWidget(self.change_list,1)
        cl.addWidget(self.diff,2)
        cl.addWidget(self.undo_button)
        self.tabs.addTab(changes,'Changes')
        self.artifact_list=QListWidget()
        self.artifact_list.itemDoubleClicked.connect(self.open_artifact)
        self.tabs.addTab(self.artifact_list,'Outputs')
        self.console=QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(1500)
        self.console.setPlaceholderText('Tool actions and terminal output appear here.')
        self.tabs.addTab(self.console,'Activity')
        self.plan_list=QListWidget()
        self.plan_list.setWordWrap(True)
        self.tabs.addTab(self.plan_list,'Plan')
        split.addWidget(self.tabs)
        split.setSizes([780,360])
        layout.addWidget(split,1)
        self.stack.addWidget(page)

    def build_images(self):
        page=QWidget()
        layout=QVBoxLayout(page)
        layout.setContentsMargins(30,26,30,26)
        layout.addWidget(text('Image studio','title'))
        layout.addWidget(text('Turn a prompt—or an existing image—into a local PNG.','sub'))
        line=QHBoxLayout()
        card=Card('Create locally','Describe your image','image')
        self.image_prompt=QPlainTextEdit()
        self.image_prompt.setPlaceholderText('A cinematic mountain landscape at dusk, blue and violet light, no text…')
        self.image_prompt.setMinimumHeight(170)
        card.body.addWidget(self.image_prompt)
        self.image_source=QLineEdit()
        self.image_source.setPlaceholderText('Optional input image for an edit')
        card.body.addWidget(row(self.image_source,button('Browse',slot=self.choose_input_image),stretch=False))
        self.image_path=QLineEdit('outputs/generated-image.png')
        card.body.addWidget(text('Save inside your project','kicker'))
        card.body.addWidget(self.image_path)
        self.image_generate=button('Generate on this PC','primary',self.generate,icon='image')
        card.body.addWidget(self.image_generate)
        card.body.addWidget(text('First use downloads the image model. The chat model temporarily leaves GPU memory while the image is generated.','muted'))
        line.addWidget(card,2)
        preview=Card('Output','Your next idea, made visible','eye')
        self.image_preview=QLabel('Your generated image will appear here.\nNo cloud rendering. No API key.')
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setMinimumSize(330,360)
        self.image_preview.setStyleSheet(f'background:{S.SIDEBAR};border-radius:8px;color:{S.SUBTEXT};')
        preview.body.addWidget(self.image_preview,1)
        line.addWidget(preview,3)
        layout.addLayout(line,1)
        self.image_status=text('Set up image tools in Models & tools before the first generation.','sub')
        layout.addWidget(self.image_status)
        self.stack.addWidget(page)

    def build_settings(self):
        page=QWidget()
        layout=QVBoxLayout(page)
        layout.setContentsMargins(30,26,30,26)
        layout.setSpacing(15)
        layout.addWidget(text('Your local engine','title'))
        layout.addWidget(text('Models live on this PC. Packages and image weights need a one-time download.','sub'))
        models=Card('Chat & vision','Use the models you already have','ai')
        self.models_text=text('Checking Ollama…','sub')
        models.body.addWidget(self.models_text)
        models.body.addWidget(row(button('Refresh models & tools',slot=self.check_tools,icon='refresh'),
                                  button('Open Ollama model library',slot=lambda:QDesktopServices.openUrl(QUrl('https://ollama.com/library')),icon='external')))
        layout.addWidget(models)
        access=Card('Workspace access','Stay in control of the work','shield')
        self.auto_edit=QCheckBox('Allow edits inside the selected project; keep a backup of each edit')
        self.auto_edit.setChecked(self.settings.get('auto_edit',True))
        self.ask_commands=QCheckBox('Ask before running terminal commands')
        self.ask_commands.setChecked(self.settings.get('ask_commands',True))
        access.body.addWidget(self.auto_edit)
        access.body.addWidget(self.ask_commands)
        access.body.addWidget(text('File tools stay in your selected project. Approved terminal commands run as your Linux user and can access other locations.','muted'))
        self.auto_edit.toggled.connect(self.save_settings)
        self.verify=QCheckBox('Make it run the project\'s checks after changing code, and fix what fails')
        self.verify.setChecked(self.settings.get('verify',True))
        self.self_review=QCheckBox('Review each finished change with a second pass before answering')
        self.self_review.setChecked(self.settings.get('self_review',True))
        quality=Card('Quality','Slower, but more careful','check')
        quality.body.addWidget(self.verify)
        quality.body.addWidget(self.self_review)
        quality.body.addWidget(text('Local models make more mistakes than large hosted ones. These checks catch many of them; each adds a little time to a task.','muted'))
        self.verify.toggled.connect(self.save_settings)
        self.self_review.toggled.connect(self.save_settings)
        self.ask_commands.toggled.connect(self.save_settings)
        layout.addWidget(access)
        layout.addWidget(quality)
        runtime=Card('Creation tools','Documents, spreadsheets & images','package')
        self.runtime_text=text('Checking the isolated creation runtime…','sub')
        runtime.body.addWidget(self.runtime_text)
        self.image_model=QLineEdit(self.settings.get('image_model','stabilityai/stable-diffusion-xl-base-1.0'))
        runtime.body.addWidget(text('Image model · Hugging Face ID or local folder','kicker'))
        runtime.body.addWidget(self.image_model)
        self.device=QComboBox()
        self.device.addItems(['AMD ROCm','NVIDIA CUDA','CPU (slow)'])
        self.image_size=QComboBox()
        self.image_size.addItems(['512','768','1024'])
        self.image_size.setCurrentText(str(self.settings.get('image_size',1024)))
        self.image_steps=QSpinBox()
        self.image_steps.setRange(1,60)
        self.image_steps.setValue(self.settings.get('image_steps',20))
        self.image_steps.setSuffix(' steps')
        runtime.body.addWidget(row(self.device,self.image_size,self.image_steps,stretch=False))
        self.docs_setup=button('Install document tools',slot=lambda:self.install_tools(False),icon='download')
        self.images_setup=button('Install image tools','primary',lambda:self.install_tools(True),icon='download')
        runtime.body.addWidget(row(self.docs_setup,self.images_setup))
        runtime.body.addWidget(text('Image tools and weights use several GB. The default SDXL model uses its published model license. You can select another compatible Diffusers model.','muted'))
        runtime.body.addWidget(button('View model license',slot=lambda:QDesktopServices.openUrl(QUrl('https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0')),icon='external'))
        self.image_model.editingFinished.connect(self.save_settings)
        self.image_size.currentTextChanged.connect(self.save_settings)
        self.image_steps.valueChanged.connect(self.save_settings)
        layout.addWidget(runtime)
        layout.addStretch()
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        self.stack.addWidget(scroll)

    def save_settings(self,*_):
        self.settings.update(auto_edit=self.auto_edit.isChecked(),ask_commands=self.ask_commands.isChecked(),
                             verify=self.verify.isChecked(),self_review=self.self_review.isChecked(),
                             image_model=self.image_model.text().strip(),image_size=int(self.image_size.currentText()),
                             image_steps=self.image_steps.value(),workspace=self.workspace)
        if not self.demo:
            atomic_json(DATA/'preferences.json',self.settings)

    def model_changed(self,name):
        if name:
            self.settings['model']=name
            if hasattr(self,'image_model'):
                self.save_settings()

    def choose_workspace(self):
        if self.busy:
            return
        folder=QFileDialog.getExistingDirectory(self,'Choose a project folder',self.workspace)
        if folder:
            self.set_workspace(folder)
            self.new_task()

    def set_workspace(self,folder):
        self.workspace=str(Path(folder).resolve())
        self.folder_label.setText(Path(folder).name)
        self.folder_label.setToolTip(self.workspace)
        if not self.demo:
            self.file_model.setRootPath(self.workspace)
            self.files.setRootIndex(self.file_model.index(self.workspace))
            self.save_settings()

    def new_task(self):
        if self.busy:
            return
        if self.demo:
            self.status.setText('Demo mode · no files or models are changed.')
            return
        if not self.workspace or not Path(self.workspace).is_dir():
            self.choose_workspace()
            return
        self.task=self.store.create(self.workspace,self.mode.currentText())
        self.streaming=''
        self.task_title.setText('New task')
        self.console.clear()
        self.refresh_tasks()
        self.refresh_panels()
        self.render_chat()
        self.stack.setCurrentIndex(0)

    def refresh_tasks(self):
        self.task_list.clear()
        for task in self.store.list():
            item=QListWidgetItem(task['title'])
            item.setData(Qt.UserRole,task['id'])
            item.setToolTip(task['workspace'])
            self.task_list.addItem(item)

    def select_task(self,item):
        if self.busy or self.demo:
            return
        try:
            self.task=self.store.load(item.data(Qt.UserRole))
            self.set_workspace(self.task['workspace'])
            self.task_title.setText(self.task['title'])
            self.streaming=''
            self.refresh_panels()
            self.render_chat()
            self.stack.setCurrentIndex(0)
        except (OSError,ValueError) as error:
            self.status.setText(str(error))

    def render_chat(self):
        messages=(self.task or {}).get('messages',[])
        content=[]
        if not messages:
            content=['# A workspace for the work ahead.\n\nRead and change a codebase. Turn notes into a report. Build a spreadsheet. Create an image.\n\n**Choose a folder, then describe the result you want.**\n\nYour local model works with real tools and saves the conversation so you can continue later.']
        for message in messages[-60:]:
            if message.get('auto'):
                content.append('### Quality check\n\n*'+message['content'].splitlines()[0][:300]+'*')
            elif message['role'] in ('user','assistant') and message.get('content'):
                content.append(('### You\n\n' if message['role']=='user' else '### DeckOS Work\n\n')+message['content'])
        if self.pending_prompt:
            content.append('### You\n\n'+self.pending_prompt)
        if self.streaming:
            content.append('### DeckOS Work\n\n'+self.streaming)
        self.chat.setMarkdown('\n\n---\n\n'.join(content))
        self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())

    def refresh_panels(self):
        task=self.task or {}
        self.change_list.clear()
        for change in task.get('changes',[]):
            item=QListWidgetItem(('↶ ' if change.get('undone') else '● ')+Path(change['path']).name)
            item.setToolTip(change['path'])
            self.change_list.addItem(item)
        self.artifact_list.clear()
        for artifact in task.get('artifacts',[]):
            item=QListWidgetItem(artifact['name']+'\n'+artifact['kind'].upper())
            item.setData(Qt.UserRole,artifact['path'])
            self.artifact_list.addItem(item)
        self.plan_list.clear()
        for item in task.get('plan',[]):
            self.plan_list.addItem({'done':'✓  ','active':'▸  '}.get(item['status'],'○  ')+item['step'])
        if task.get('changes'):
            self.change_list.setCurrentRow(len(task['changes'])-1)

    def show_change(self,index):
        changes=(self.task or {}).get('changes',[])
        self.diff.setPlainText(changes[index]['diff'] if 0<=index<len(changes) else '')
        self.undo_button.setEnabled(not self.busy and 0<=index<len(changes) and not changes[index].get('undone'))

    def undo(self):
        if self.busy or self.demo or not self.task:
            return
        index=self.change_list.currentRow()
        if index<0:
            return
        try:
            path=undo_edit(self.store,self.task,self.task['changes'][index]['id'])
            self.status.setText('Undone: '+path)
            self.refresh_panels()
        except (OSError,ValueError) as error:
            QMessageBox.warning(self,'Could not undo',str(error))

    def preview_file(self,index):
        path=Path(self.file_model.filePath(index))
        if path.is_file():
            try:
                if path.stat().st_size>1_000_000:
                    self.file_preview.setPlainText('Preview limited to text files under 1 MB.')
                else:
                    self.file_preview.setPlainText(path.read_text(errors='replace')[:30000])
            except OSError as error:
                self.file_preview.setPlainText(str(error))

    def open_link(self,url):
        if url.scheme() in ('https','http'):
            QDesktopServices.openUrl(url)
        elif url.isLocalFile() and self.workspace:
            try:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(scoped(self.workspace,url.toLocalFile()))))
            except ValueError as error:
                self.status.setText(str(error))

    def open_artifact(self,item):
        if self.demo:
            return
        try:
            path=scoped(self.workspace,item.data(Qt.UserRole))
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except ValueError as error:
            self.status.setText(str(error))

    def attach(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Attach files for this task',self.workspace)
        self.attached=list(dict.fromkeys(self.attached+paths))[:8]
        self.attachment_label.setText(f'{len(self.attached)} attached' if self.attached else '')
        self.attachment_label.setToolTip('\n'.join(self.attached))

    def set_busy(self,value):
        self.busy=value
        for control in (self.new_button,self.folder_button,self.send_button,self.attach_button,self.mode,
                        self.model_combo,self.image_generate,self.docs_setup,self.images_setup):
            control.setEnabled(not value)
        self.stop_button.setEnabled(value)
        self.task_list.setEnabled(not value)
        self.show_change(self.change_list.currentRow())

    def run_process(self,command,request):
        self.stop_requested=False
        self.set_busy(True)
        self.active=Process(self,self.handle_event,self.finished)
        self.active.launch(command,request)

    def send(self):
        if self.busy:
            return
        prompt=self.input.toPlainText().strip()
        if not prompt:
            return
        if self.demo:
            self.status.setText('Demo mode · no models or tools will run.')
            return
        if not self.task:
            self.new_task()
        if not self.task:
            return
        if not self.settings.get('model'):
            self.status.setText('Choose a downloaded model in Models & tools.')
            return
        self.pending_prompt=prompt
        self.streaming=''
        self.input.clear()
        self.render_chat()
        self.save_settings()
        request=dict(task=self.task['id'],prompt=prompt,settings=self.settings,attachments=self.attached)
        self.attached=[]
        self.attachment_label.clear()
        self.run_process('ask',request)

    def handle_event(self,data):
        event=data['event']
        if event=='token':
            self.streaming+=data['text']
            if not self.render_timer.isActive():
                self.render_timer.start(100)
        elif event=='message':
            if self.task:
                self.task['messages'].append(data['message'])
            self.streaming=''
            self.render_chat()
        elif event=='task':
            self.task=data['task']
            self.pending_prompt=''
            self.task_title.setText(self.task['title'])
            self.refresh_tasks()
            self.refresh_panels()
            self.render_chat()
        elif event=='approval':
            self.approval_title.setText(data['title'])
            self.approval_detail.setPlainText(data['detail'])
            self.approval.show()
            self.status.setText('Waiting for your approval.')
            self.stack.setCurrentIndex(0)
        elif event in ('status','notice','error'):
            self.status.setText(data['text'])
            self.image_status.setText(data['text'])
            if event!='status':
                self.console.appendPlainText(data['text'])
        elif event=='console':
            self.console.moveCursor(QTextCursor.End)
            self.console.insertPlainText(data['text'])
        elif event=='tool':
            self.console.appendPlainText('\n'+data['name']+' '+json.dumps(data['args'],ensure_ascii=False)[:3000])
            self.status.setText('Using '+data['name'].replace('_',' ')+'…')
        elif event=='tool_result':
            self.console.appendPlainText(data['text'][-6000:])
        elif event=='usage':
            self.status.setText(f"Local generation · {data['tokens_per_second']} tokens/s")
        elif event=='plan':
            if self.task:
                self.task['plan']=data['plan']
            self.refresh_panels()
        elif event=='change':
            if self.task:
                self.task['changes'].append(data['change'])
            self.refresh_panels()
        elif event=='artifact':
            if self.task:
                self.task['artifacts']=[a for a in self.task['artifacts'] if a['path']!=data['artifact']['path']]+[data['artifact']]
            self.refresh_panels()
            path=Path(data['artifact']['path'])
            if path.suffix.lower()=='.png':
                pix=QPixmap(str(path))
                self.image_preview.setPixmap(pix.scaled(self.image_preview.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
        elif event=='probe':
            current=self.settings.get('model','')
            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            for model in data['models']:
                self.model_combo.addItem(model['name'])
            index=self.model_combo.findText(current)
            self.model_combo.setCurrentIndex(index if index>=0 else 0)
            self.model_combo.blockSignals(False)
            self.settings['model']=self.model_combo.currentText()
            self.models_text.setText('\n'.join(m['name']+' · '+', '.join(m.get('capabilities',[])) for m in data['models']) or 'Ollama is unavailable or no model is downloaded. Use DeckOS Assistant setup first.')
            runtime=data['runtime']
            self.runtime_text.setText('Documents: '+('ready' if runtime.get('documents') else 'not installed')+' · Images: '+
                                      ('ready' if runtime.get('images') else 'not installed')+' · '+runtime.get('device','GPU not detected'))

    def answer(self,value):
        self.approval.hide()
        if self.active:
            self.active.approve(value)

    def finished(self,code):
        self.set_busy(False)
        self.approval.hide()
        self.pending_prompt=''
        if not getattr(self,'closing',False):
            if self.task and not self.demo:
                try:
                    self.task=self.store.load(self.task['id'])
                    if self.task.get('status')=='running' or getattr(self,'stop_requested',False):
                        self.task['status']='stopped'
                        self.store.save(self.task)
                except (OSError,ValueError):
                    pass
            self.refresh_panels()
            self.render_chat()
            if code==0:
                self.status.setText('Task saved · ready for the next step.')

    def stop(self):
        if self.active and self.busy:
            self.stop_requested=True
            process=self.active
            process.stop()
            self.status.setText('Stopping and saving completed work…')
            QTimer.singleShot(4000,lambda:process.stop(force=True) if process.state()!=QProcess.NotRunning else None)

    def check_tools(self):
        if self.demo or self.busy or (self.probe and self.probe.state()!=QProcess.NotRunning):
            return
        self.probe=Process(self,self.handle_event,lambda _:None)
        self.probe.launch('probe',{})

    def install_tools(self,images):
        if self.demo or self.busy:
            return
        self.save_settings()
        self.stack.setCurrentIndex(0)
        self.tabs.setCurrentWidget(self.console)
        self.status.setText('Installing local tools. Image runtime downloads several GB; progress is in Activity.')
        self.run_process('setup',dict(images=images,device=['rocm','cuda','cpu'][self.device.currentIndex()]))

    def choose_input_image(self):
        path,_=QFileDialog.getOpenFileName(self,'Choose an image',self.workspace,'Images (*.png *.jpg *.jpeg *.webp)')
        if path:
            self.image_source.setText(path)

    def generate(self):
        if self.demo or self.busy:
            return
        prompt=self.image_prompt.toPlainText().strip()
        if not prompt:
            return
        if not self.task:
            self.new_task()
        if not self.task:
            return
        self.save_settings()
        self.run_process('image',dict(task=self.task['id'],prompt=prompt,path=self.image_path.text(),
                                     input_image=self.image_source.text(),settings=self.settings))

    def demo_data(self):
        self.workspace='/home/demo/Projects/DeckOS'
        self.folder_label.setText('DeckOS')
        self.model_combo.addItems(['gpt-oss:20b','gemma4:12b'])
        self.task=dict(id='demo',title='Refine the benchmark report',workspace=self.workspace,changes=[],artifacts=[],messages=[
            {'role':'user','content':'Review the benchmark report layout, make it easier to scan, and write a short release brief.'},
            {'role':'assistant','content':'I’ll read the report renderer and its tests, then update the layout and create the brief.'},
            {'role':'user','auto':True,'content':'You changed 1 file(s) since the last passing check. Verify with run_checks.'},
            {'role':'assistant','content':'## A clearer performance story\n\nThe report now leads with the measurements that matter, keeps uncertainty beside each score, and puts hardware details together.\n\n- Updated `bench/report.py` with clearer spacing and labels.\n- Checked the existing tests: **13 passed**.\n- Created [release-brief.docx](outputs/release-brief.docx).\n\nThe changes and the generated document are ready to review in the panel on the right.\n\n*Sample conversation · no tools were run.*'}])
        self.task['changes']=[dict(id='demo',path=self.workspace+'/bench/report.py',diff='--- report.py\n+++ report.py\n@@ -1,2 +1,3 @@\n-<h2>Results</h2>\n+<h2>Your performance, measured</h2>\n+<p>Every score includes its spread.</p>\n',undone=False)]
        self.task['plan']=[dict(step='Read the report renderer and its tests',status='done'),
                           dict(step='Make the layout easier to scan',status='done'),
                           dict(step='Run the tests',status='done'),dict(step='Write the release brief',status='done')]
        self.task['artifacts']=[dict(name='release-brief.docx',kind='docx',path='outputs/release-brief.docx'),dict(name='benchmark-summary.xlsx',kind='xlsx',path='outputs/benchmark-summary.xlsx')]
        self.task_title.setText(self.task['title'])
        for name in ['Refine the benchmark report','Plan the next release','Explore a wallpaper concept']:
            self.task_list.addItem(name)
        self.task_list.setCurrentRow(0)
        self.models_text.setText('gpt-oss:20b · reasoning & tools\ngemma4:12b · vision & tools')
        self.runtime_text.setText('Demo · document and image tools shown as configured')
        self.status.setText('Demo · sample results · your data stays on your machine')
        self.console.setPlainText('read_file · bench/report.py\nsearch_files · metric_rows\nedit_file · bench/report.py\nrun_command · python3 -m unittest discover -s tests\ncreate_document · outputs/release-brief.docx')
        self.refresh_panels()
        self.tabs.setCurrentIndex(1)
        self.render_chat()

    def closeEvent(self,event):
        if self.busy and QMessageBox.question(self,'Task running','Stop the current task and close DeckOS Work?')!=QMessageBox.Yes:
            event.ignore()
            return
        self.closing=True
        for process in (self.active,self.probe):
            if process and process.state()!=QProcess.NotRunning:
                process.stop()
                if not process.waitForFinished(1500):
                    process.stop(force=True)
                    process.waitForFinished(1000)
        event.accept()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo',action='store_true')
    parser.add_argument('--workspace',type=Path)
    parser.add_argument('--screenshot',type=Path)
    args=parser.parse_args()
    if args.screenshot:
        args.demo=True
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    app=QApplication(sys.argv)
    app.setApplicationName('DeckOS Work')
    app.setDesktopFileName('deckos-work')
    for font in (HERE.parents[2]/'share/fonts/deckos').glob('*.otf'):
        QFontDatabase.addApplicationFont(str(font))
    app.setFont(QFont('Inter',10))
    app.setStyleSheet(qss())
    palette=app.palette()  # Markdown links take their colour from the application palette
    palette.setColor(QPalette.Link,QColor(S.P.accent))
    app.setPalette(palette)
    window=Work(args.demo,args.workspace)
    window.show()
    if args.screenshot:
        args.screenshot.mkdir(parents=True,exist_ok=True)
        def capture():
            for index,name in enumerate(['workspace','images','settings']):
                window.stack.setCurrentIndex(index)
                app.processEvents()
                window.grab().save(str(args.screenshot/f'work-{name}.png'))
            app.quit()
        QTimer.singleShot(300,capture)
    sys.exit(app.exec())


if __name__=='__main__':
    main()
