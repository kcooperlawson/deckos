"""Native DecKoOS Bench: run benchmarks, explore history, and compare saved results."""
import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'hub'))

from PySide6.QtCore import QPointF, QRectF, QProcess, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontDatabase, QIcon, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame,
                               QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
                               QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSpinBox,
                               QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

import hub_style as S
from hub_widgets import Card, button, icon_label, label, row
from bench_data import comparisons, metrics, series, title
from report import ENV_NAMES, fmt, run_report, compare_report
from bench_experiment import SETTINGS
from runners import ALL, SYSTEM
import score as SC

ICONS = {'cpu': 'cpu', 'memory': 'memory', 'disk': 'drives', 'gpu': 'gpu', 'ai': 'ai', 'game': 'gaming'}
NAV = [('overview', 'Score', 'gauge'), ('history', 'History', 'clock'),
       ('run', 'Lab', 'flask'), ('compare', 'Compare', 'sliders')]
PART_ICONS = {'cpu': 'cpu', 'memory': 'memory', 'storage': 'drives', 'graphics': 'gpu', 'ai': 'ai'}


def stylesheet():
    return S.qss() + f'''
QLabel#heroTitle {{ font-size: 25pt; font-weight: 600; }}
QLabel#score {{ font-family: "Inter Display"; font-size: 24pt; font-weight: 600; }}
QLabel#eyebrow {{ color: {S.P.accent}; font-size: 9pt; font-weight: 600; }}
QLineEdit, QSpinBox {{ background: {S.SURFACE}; border: 1px solid {S.BORDER}; border-radius: 7px; padding: 8px 10px; }}
QLineEdit:focus, QSpinBox:focus {{ border-color: {S.P.accent}; }}
QTableWidget {{ background: {S.SURFACE}; alternate-background-color: {S.RAISED}; border: none; gridline-color: {S.BORDER}; selection-background-color: #263652; }}
QTableWidget::item {{ padding: 9px; border-bottom: 1px solid {S.BORDER}; }}
QTableWidget::item:selected {{ color: {S.TEXT}; }}
QHeaderView::section {{ background: {S.SURFACE}; color: {S.SUBTEXT}; padding: 9px; border: none; border-bottom: 1px solid {S.BORDER}; font-size: 9pt; }}
QProgressBar {{ background: {S.BORDER}; border: none; border-radius: 4px; min-height: 8px; max-height: 8px; }}
QProgressBar::chunk {{ background: {S.P.accent}; border-radius: 4px; }}
QFrame#hero {{ border: 1px solid #354166; border-radius: 12px;
 background: qlineargradient(x1:0,y1:1,x2:1,y2:0,stop:0 #182131,stop:0.65 #1A2036,stop:1 #29213D); }}
QFrame#hero QLabel {{ background: transparent; }}
QLabel#badge {{ background: #23354A; color: #9DC0FF; border-radius: 5px; padding: 4px 8px; font-size: 8pt; font-weight: 600; }}
QLabel#up {{ background: rgba(61,214,140,0.14); color: {S.SUCCESS}; border-radius: 6px; padding: 4px 9px; font-weight: 600; }}
QLabel#down {{ background: rgba(255,107,107,0.14); color: {S.DANGER}; border-radius: 6px; padding: 4px 9px; font-weight: 600; }}
QLabel#flat {{ background: {S.RAISED}; color: {S.SUBTEXT}; border-radius: 6px; padding: 4px 9px; font-weight: 600; }}
QLabel#partScore {{ font-family: "Inter Display"; font-size: 21pt; font-weight: 700; }}
QLabel#scoreTitle {{ font-family: "Inter Display"; font-size: 22pt; font-weight: 700; }}
QFrame#part {{ background: {S.SURFACE}; border: 1px solid {S.BORDER}; border-radius: 12px; }}
QFrame#part QLabel {{ background: transparent; }}
'''


def plain(text='', kind=None):
    lab = label(str(text), kind)
    lab.setTextFormat(Qt.PlainText)
    return lab


def clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            clear(item.layout())


def table(headers):
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.verticalHeader().hide()
    widget.verticalHeader().setDefaultSectionSize(46)
    widget.setShowGrid(False)
    widget.setSelectionBehavior(QTableWidget.SelectRows)
    widget.setSelectionMode(QTableWidget.SingleSelection)
    widget.setEditTriggers(QTableWidget.NoEditTriggers)
    widget.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    return widget


def fill_table(widget, rows):
    widget.setRowCount(len(rows))
    for i, values in enumerate(rows):
        for j, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            if j:
                item.setForeground(QColor(S.SUBTEXT))
            widget.setItem(i, j, item)


class Hero(QFrame):
    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor('#52607D'), 1))
        p.setBrush(QColor('#1A2133'))
        for x, y in ((10, 10), (self.width()-10, 10), (10, self.height()-10),
                     (self.width()-10, self.height()-10)):
            p.drawEllipse(QPointF(x, y), 2.5, 2.5)
            p.drawLine(QPointF(x-1, y+1), QPointF(x+1, y-1))


class ScoreRing(QWidget):
    """The score in a gradient ring. The arc is score / (score + the reference), so it fills with the score but never
    completes: the reference PC sits at half, twice the reference at two thirds."""

    def __init__(self):
        super().__init__()
        self.value, self.caption, self.detail = None, 'No score yet', ''
        self.setFixedSize(250, 250)
        self.setAccessibleName('DecKoOS Score')

    def set(self, value, caption, detail=''):
        self.value, self.caption, self.detail = value, caption, detail
        self.setAccessibleDescription(f'{caption}: {value:,}' if value else caption)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(18, 18, self.width() - 36, self.height() - 36)
        start, span = 225 * 16, -270 * 16
        p.setPen(QPen(QColor(S.BORDER), 14, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(r, start, span)
        if self.value:
            frac = self.value / (self.value + SC.BASE)
            grad = QLinearGradient(r.topLeft(), r.bottomRight())
            grad.setColorAt(0, QColor(S.P.accent))
            grad.setColorAt(1, QColor(S.P.grad_b))
            glow = QColor(S.P.accent)
            glow.setAlpha(45)
            p.setPen(QPen(glow, 26, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(r, start, int(span * frac))
            p.setPen(QPen(grad, 14, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(r, start, int(span * frac))
        p.setPen(QColor(S.TEXT))
        p.setFont(QFont('Inter Display', 34, QFont.Bold))
        p.drawText(QRectF(0, 78, self.width(), 60), Qt.AlignCenter, f'{self.value:,}' if self.value else '—')
        p.setFont(QFont('Inter', 9, QFont.DemiBold))
        p.setPen(QColor(S.P.accent))
        p.drawText(QRectF(0, 140, self.width(), 20), Qt.AlignCenter, self.caption.upper())
        p.setFont(QFont('Inter', 9))
        p.setPen(QColor(S.SUBTEXT))
        p.drawText(QRectF(0, 162, self.width(), 20), Qt.AlignCenter, self.detail)
        p.end()


class Bar(QWidget):
    """A part's score against the reference: the bar's tick is the reference PC."""

    def __init__(self):
        super().__init__()
        self.value = 0
        self.setFixedHeight(10)

    def set(self, value):
        self.value = value or 0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        full = SC.BASE * 3  # the bar's end: three times the reference
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(S.BORDER))
        p.drawRoundedRect(QRectF(0, 2, w, h - 4), 3, 3)
        if self.value:
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0, QColor(S.P.accent))
            grad.setColorAt(1, QColor(S.P.grad_b))
            p.setBrush(grad)
            p.drawRoundedRect(QRectF(0, 2, max(6, w * min(1, self.value / full)), h - 4), 3, 3)
        x = w * SC.BASE / full
        p.setPen(QPen(QColor(S.SUBTEXT), 2))
        p.drawLine(QPointF(x, 0), QPointF(x, h))
        p.end()


class Trend(QWidget):
    """Date-spaced history points; no invented interpolation or combined scores."""
    def __init__(self):
        super().__init__()
        self.points, self.unit = [], ''
        self.setMinimumHeight(210)
        self.setAccessibleName('Historical benchmark averages')

    def set_series(self, points, unit):
        self.points, self.unit = points[-30:], unit
        self.setToolTip('\n'.join(f'{name}: {fmt(value, unit)}' for _, value, name in self.points))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(QFont('Inter', 9))
        if not self.points:
            p.setPen(QColor(S.SUBTEXT))
            p.drawText(self.rect(), Qt.AlignCenter, 'Your first benchmark starts the story.\nRun a test to see performance over time.')
            return
        area = QRectF(68, 18, max(30, self.width()-92), self.height()-57)
        vals = [v for _, v, _ in self.points]
        low, high = min(vals), max(vals)
        pad = (high-low)*.3 or abs(high)*.05 or 1
        low, high = low-pad, high+pad
        for i in range(4):
            y = area.top() + i * area.height()/3
            p.setPen(QPen(QColor(S.BORDER), 1, Qt.DashLine))
            p.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            p.setPen(QColor(S.SUBTEXT))
            p.drawText(QRectF(0, y-10, 58, 20), Qt.AlignRight | Qt.AlignVCenter, fmt(high-(high-low)*i/3))
        start, end = self.points[0][0], self.points[-1][0]
        pts = [QPointF(area.left() + (stamp-start)/(end-start)*area.width() if end != start else area.center().x(),
                       area.bottom()-(v-low)/(high-low)*area.height()) for stamp, v, _ in self.points]
        path = QPainterPath(pts[0])
        for point in pts[1:]:
            path.lineTo(point)
        fill = QPainterPath(path)
        fill.lineTo(pts[-1].x(), area.bottom())
        fill.lineTo(pts[0].x(), area.bottom())
        fill.closeSubpath()
        gradient = QLinearGradient(0, area.top(), 0, area.bottom())
        top, bottom = QColor(S.P.accent), QColor(S.P.accent)
        top.setAlpha(65)
        bottom.setAlpha(0)
        gradient.setColorAt(0, top)  # the accent, like the line
        gradient.setColorAt(1, bottom)
        p.fillPath(fill, gradient)
        p.setPen(QPen(QColor(S.P.accent), 2.5))
        p.drawPath(path)
        p.setBrush(QColor(S.SURFACE))
        for point in pts:
            p.drawEllipse(point, 4, 4)
        p.setBrush(QColor(S.P.accent))
        p.drawEllipse(pts[-1], 5, 5)
        p.setPen(QColor(S.SUBTEXT))
        for alignment, stamp in ((Qt.AlignLeft, start), (Qt.AlignRight, end)):
            p.drawText(QRectF(area.left(), area.bottom()+16, area.width(), 22), alignment,
                       time.strftime('%d %b · %H:%M', time.localtime(stamp)))
        p.end()


class Worker(QProcess):
    """Each operation has its own process and newline-delimited events."""
    def __init__(self, owner, callback, done):
        super().__init__(owner)
        self.buffer = b''
        self.callback, self.done = callback, done
        self.group_ready = False
        self.group_pid = 0
        self.stderr = ''
        self.readyReadStandardOutput.connect(self.read_events)
        self.readyReadStandardError.connect(self.read_errors)
        self.finished.connect(self.finished_work)
        self.errorOccurred.connect(self.process_error)

    def launch(self, args):
        self.start(sys.executable, ['-u', str(HERE / 'bench_worker.py'), *args])

    def read_errors(self):
        self.stderr = (self.stderr + bytes(self.readAllStandardError()).decode(errors='replace'))[-4000:]

    def read_events(self):
        self.buffer += bytes(self.readAllStandardOutput())
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            try:
                data = json.loads(line)
                if data['event'] == 'ready':
                    self.group_ready = True
                    self.group_pid = self.processId()
                self.callback(data)
            except (ValueError, KeyError):
                continue

    def process_error(self, error):
        if error == QProcess.FailedToStart:
            self.callback(dict(event='error', text=self.errorString()))
            self.done(1)

    def finished_work(self, code, _status):
        self.read_events()
        self.read_errors()
        self.done(code)

    def stop(self, force=False):
        if self.group_ready and self.group_pid and os.name == 'posix':
            try:
                os.killpg(self.group_pid, signal.SIGKILL if force else signal.SIGTERM)
            except ProcessLookupError:
                pass
        elif self.state() != QProcess.NotRunning:
            self.kill() if force else self.terminate()


class Bench(QWidget):
    def __init__(self, demo=False):
        super().__init__()
        self.demo = demo
        self.runs, self.environment, self.statuses = [], {}, {}
        self.scan = self.active = self.comparison = None
        self.selected = None
        self.comparison_rows = []
        self.busy = self.saved = False
        self.setObjectName('root')
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowTitle('DecKoOS Bench' + (' — Demo' if demo else ''))
        self.setWindowIcon(QIcon.fromTheme('deckos-bench', S.brand_icon('bench-logo.svg')))
        self.resize(1280, 880)
        self.setMinimumSize(1050, 720)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        side = QFrame()
        side.setObjectName('sidebar')
        side.setFixedWidth(214)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(18, 23, 18, 20)
        sl.setSpacing(6)
        brand = row(icon_label('gauge', S.P.accent, 30), plain('DecKoOS Bench', 'brand'), stretch=False)
        sl.addWidget(brand)
        sl.addWidget(plain('Score your PC', 'muted'))
        sl.addSpacing(30)
        sl.addWidget(plain('WORKSPACE', 'kicker'))
        self.nav, self.pages = {}, {}
        self.nav_group = QButtonGroup(self)
        self.stack = QStackedWidget()
        for key, name, ic in NAV:
            b = button('  ' + name, 'nav', lambda _=False, k=key: self.navigate(k), icon=ic)
            b.setCheckable(True)
            self.nav_group.addButton(b)
            self.nav[key] = b
            sl.addWidget(b)
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setContentsMargins(28, 24, 28, 24)
            layout.setSpacing(18)
            self.pages[key] = layout
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.stack.addWidget(scroll)
        sl.addStretch()
        mini = Card()
        mini.body.setContentsMargins(12, 12, 12, 12)
        mini.body.addWidget(plain('THE DECKOS SCORE', 'eyebrow'))
        mini.body.addWidget(plain('One number for your PC.\nEvery run kept.', 'sub'))
        sl.addWidget(mini)
        sl.addSpacing(12)
        sl.addWidget(plain('●  Demo · sample results' if demo else '●  Local results · private by default', 'muted'))
        outer.addWidget(side)
        outer.addWidget(self.stack, 1)
        self.build_overview()
        self.build_run()
        self.build_history()
        self.build_compare()
        self.navigate('overview')
        if demo:
            from bench_demo import snapshot
            self.runs, self.environment, self.statuses = snapshot()
            self.refresh_views()
        else:
            self.refresh_views()
            QTimer.singleShot(0, self.refresh_data)

    def heading(self, key, title_, subtitle, action=None):
        layout = self.pages[key]
        text = QVBoxLayout()
        text.setSpacing(4)
        text.addWidget(plain(title_, 'title'))
        text.addWidget(plain(subtitle, 'sub'))
        line = QHBoxLayout()
        line.addLayout(text, 1)
        if action:
            line.addWidget(action)
        layout.addLayout(line)

    def navigate(self, key):
        self.nav[key].setChecked(True)
        self.stack.setCurrentIndex([x[0] for x in NAV].index(key))

    def build_overview(self):
        self.heading('overview', 'DecKoOS Score', 'One number for your whole PC, and how it changes over time.')
        layout = self.pages['overview']
        hero = Hero()
        hero.setObjectName('hero')
        h = QHBoxLayout(hero)
        h.setContentsMargins(26, 22, 30, 22)
        h.setSpacing(26)
        self.ring = ScoreRing()
        h.addWidget(self.ring, 0, Qt.AlignVCenter)
        info = QVBoxLayout()
        info.setSpacing(8)
        info.addStretch()
        self.score_kicker = plain('YOUR LATEST SCORE', 'eyebrow')
        self.score_title = plain('', 'scoreTitle')
        self.score_machine = plain('', 'sub')
        self.score_delta = plain('', 'flat')
        self.score_best = plain('', 'muted')
        badges = QHBoxLayout()
        badges.setSpacing(10)
        badges.addWidget(self.score_delta)
        badges.addWidget(self.score_best)
        badges.addStretch()
        for w in (self.score_kicker, self.score_title, self.score_machine):
            info.addWidget(w)
        info.addLayout(badges)
        info.addSpacing(6)
        self.score_button = button('Run DecKoOS Score', 'primary', self.start_score, icon='play',
                                   tip='Every system test, three times, with the score\'s own AI model: about 12 minutes')
        self.score_stop = button('Stop', slot=self.stop_run, icon='stop')
        self.score_stop.hide()
        info.addWidget(row(self.score_button, self.score_stop,
                           button('Lab tests', slot=lambda: self.navigate('run'), icon='flask'), stretch=True))
        self.score_progress = QProgressBar()
        self.score_progress.setTextVisible(False)
        self.score_progress.hide()
        self.score_status = plain('', 'muted')
        info.addWidget(self.score_progress)
        info.addWidget(self.score_status)
        info.addStretch()
        h.addLayout(info, 1)
        layout.addWidget(hero)
        self.parts_layout = QHBoxLayout()
        self.parts_layout.setSpacing(12)
        self.part_widgets = {}
        for key in SC.ORDER:
            tile = QFrame()
            tile.setObjectName('part')
            v = QVBoxLayout(tile)
            v.setContentsMargins(16, 14, 16, 14)
            v.setSpacing(6)
            v.addWidget(row(icon_label(PART_ICONS[key], S.P.accent, 20), plain(SC.PARTS[key][0], 'cardTitle'), stretch=True))
            number, bar, note = plain('—', 'partScore'), Bar(), plain('', 'muted')
            for w in (number, bar, note):
                v.addWidget(w)
            self.part_widgets[key] = (number, bar, note)
            self.parts_layout.addWidget(tile, 1)
        layout.addLayout(self.parts_layout)
        history = Card('Score history', 'Your DecKoOS Scores over time', 'clock')
        self.score_trend = Trend()
        self.score_trend.setMinimumHeight(190)
        history.body.addWidget(self.score_trend)
        self.score_hint = plain('', 'muted')
        history.body.addWidget(self.score_hint)
        layout.addWidget(history)
        bottom = QHBoxLayout()
        bottom.setSpacing(14)
        how = Card('How it works', 'What the score means', 'info')
        how.body.addWidget(plain(
            f'Each part scores its key measurements against a fixed reference PC, which scores {SC.BASE:,} in every '
            f'part. Twice as fast is twice the points. The DecKoOS Score combines the five: graphics and CPU count most, '
            f'then local AI, memory and storage. Scores of the same version (this is version {SC.VERSION}) compare across '
            f'PCs and over time. The range is the lowest and highest of the three repetitions.', 'sub'))
        bottom.addWidget(how, 3)
        machine = Card('This machine', 'Hardware & software', 'system')
        self.machine_text = plain('Reading system details…', 'sub')
        machine.body.addWidget(self.machine_text)
        machine.body.addStretch()
        bottom.addWidget(machine, 2)
        layout.addLayout(bottom)
        trend_card = Card('Every measurement', 'Each test over time', 'gauge')
        self.trend_metric = QComboBox()
        self.trend_metric.setMinimumWidth(260)
        self.trend_metric.setMaximumWidth(390)
        self.trend_metric.currentIndexChanged.connect(self.change_trend)
        trend_card.actions.addWidget(self.trend_metric)
        self.trend = Trend()
        trend_card.body.addWidget(self.trend)
        self.trend_hint = plain('', 'muted')
        trend_card.body.addWidget(self.trend_hint)
        layout.addWidget(trend_card)
        self.notice = plain('', 'muted')
        layout.addWidget(self.notice)
        layout.addStretch()

    def run_score(self, run):
        """A run's score: the saved one when it's this version's, else worked out now (older runs, lab runs)."""
        saved = run.get('score')
        return saved if isinstance(saved, dict) and saved.get('version') == SC.VERSION else SC.score(run)

    def render_score(self):
        scored = [(run, self.run_score(run)) for run in self.runs]
        full = [(run, sc) for run, sc in scored if sc['total'] is not None]
        latest = full[-1] if full else next(((r, sc) for r, sc in reversed(scored) if sc['partial'] is not None), None)
        env = self.environment
        if not latest:
            self.ring.set(None, 'No score yet', 'Run it to get yours')
            self.score_title.setText('Score your PC')
            self.score_machine.setText(' · '.join(x for x in (env.get('cpu'), env.get('gpu')) if x) or
                                       'CPU, graphics, local AI, memory and storage, in one number.')
            self.score_delta.hide()
            self.score_best.setText('About 12 minutes. Close games and big apps first.')
        else:
            run, sc = latest
            number, caption = SC.headline(sc)
            spread = f"{sc['low']:,} – {sc['high']:,}" if sc.get('low') and sc['low'] != sc['high'] else ''
            self.ring.set(sc['total'] or sc['partial'], caption, spread)
            self.score_title.setText(f"{title(run)} · {time.strftime('%d %b %Y', time.localtime(run['started']))}")
            e = run.get('environment', {})
            self.score_machine.setText(' · '.join(x for x in (e.get('cpu'), e.get('gpu')) if x))
            earlier = [sc2['total'] for r2, sc2 in full if r2['started'] < run['started']]
            if sc['total'] is not None and earlier:
                change = (sc['total'] - earlier[-1]) / earlier[-1] * 100
                kind = 'up' if change > 0.5 else 'down' if change < -0.5 else 'flat'
                self.score_delta.setObjectName(kind)
                self.score_delta.setText(('▲ ' if kind == 'up' else '▼ ' if kind == 'down' else '') +
                                         f'{abs(change):.1f}% since last time' if kind != 'flat' else 'Same as last time')
                self.score_delta.style().unpolish(self.score_delta)
                self.score_delta.style().polish(self.score_delta)
                self.score_delta.show()
            else:
                self.score_delta.hide()
            best = max((sc2['total'] for _, sc2 in full), default=None)
            if sc['total'] is None:
                missing = [SC.PARTS[k][0] for k, p in sc['parts'].items() if 'missing' in p]
                self.score_best.setText('Partial: ' + ', '.join(missing) + ' not measured')
            else:
                self.score_best.setText(f'Best {best:,}  ·  {len(full)} score run{"s" if len(full) != 1 else ""}')
        parts = latest[1]['parts'] if latest else {}
        for key, (number, bar, note) in self.part_widgets.items():
            p = parts.get(key, {})
            if 'score' in p:
                number.setText(f"{p['score']:,}")
                bar.set(p['score'])
                note.setText(f"{p['score'] / SC.BASE:.1f}× the reference")
                note.setToolTip(f"{p['low']:,} – {p['high']:,} across the repetitions")
            else:
                number.setText('—')
                bar.set(0)
                note.setText(p.get('missing', 'Not measured yet'))
                note.setToolTip(SC.AI_MODEL if key == 'ai' else '')
        self.score_trend.set_series([(r['started'], sc['total'], title(r)) for r, sc in full], 'points')
        self.score_hint.setText(f'{len(full)} DecKoOS Score{"s" if len(full) != 1 else ""} · version {SC.VERSION} · '
                                'higher is better' if full else 'Your first score starts the chart.')

    def build_run(self):
        self.heading('run', 'Make your next measurement', 'Choose a suite, give it a name, and let Bench take it from here.',
                     button('Refresh tools', slot=self.refresh_data, icon='refresh'))
        layout = self.pages['run']
        options = Card('Session', 'Set up your benchmark', 'sliders')
        line = QHBoxLayout()
        self.suite = QComboBox()
        self.suite.addItems(['System suite', 'Game benchmarks', 'Custom selection'])
        self.suite.currentIndexChanged.connect(self.choose_suite)
        self.run_label = QLineEdit()
        self.run_label.setPlaceholderText('Session name · e.g. New driver baseline')
        self.run_label.setMaxLength(100)
        self.repeat = QSpinBox()
        self.repeat.setRange(1, 30)
        self.repeat.setValue(3)
        self.repeat.setSuffix(' repetitions')
        self.repeat.valueChanged.connect(self.selection_changed)
        self.repeat.setToolTip('Three or more repetitions enable comparison ranges.')
        line.addWidget(self.suite)
        line.addWidget(self.run_label, 1)
        line.addWidget(self.repeat)
        options.body.addLayout(line)
        layout.addWidget(options)
        # An experiment: the selected tests with one setting changed, A and B in turn, then Compare.
        experiment = Card('Experiment', 'Does one setting make a difference?', 'flask')
        self.experiment_on = QCheckBox('Run the tests both ways')
        self.experiment_on.toggled.connect(self.selection_changed)
        experiment.actions.addWidget(self.experiment_on)
        pick = QHBoxLayout()
        self.experiment_setting = QComboBox()
        for key, setting in SETTINGS.items():
            self.experiment_setting.addItem(setting.name, key)
        self.experiment_a, self.experiment_b = QComboBox(), QComboBox()
        self.experiment_setting.currentIndexChanged.connect(self.choose_setting)
        pick.addWidget(self.experiment_setting, 2)
        pick.addWidget(plain('A', 'kicker'))
        pick.addWidget(self.experiment_a, 1)
        pick.addWidget(plain('B', 'kicker'))
        pick.addWidget(self.experiment_b, 1)
        experiment.body.addLayout(pick)
        experiment.body.addWidget(plain('Bench switches the setting between turns (A B B A…), so warming up or a '
                                        'background task can\'t favour one side, and puts it back afterwards. '
                                        'Each repetition is one turn per side.', 'muted'))
        self.choose_setting()
        layout.addWidget(experiment)
        grid = QGridLayout()
        grid.setSpacing(12)
        self.checks, self.runner_status = {}, {}
        for i, (key, cls) in enumerate(ALL.items()):
            card = Card(cls.group, cls.title, ICONS[cls.group])
            check = QCheckBox('Include')
            check.setAccessibleName('Include ' + cls.title)
            check.setChecked(cls in SYSTEM)
            check.toggled.connect(self.selection_changed)
            card.actions.addWidget(check)
            card.body.addWidget(plain(cls.about, 'sub'))
            state = plain('Checking availability…', 'muted')
            card.body.addWidget(state)
            self.checks[key], self.runner_status[key] = check, state
            grid.addWidget(card, i//2, i%2)
        layout.addLayout(grid)
        footer = QHBoxLayout()
        self.estimate = plain('Checking benchmark tools…', 'sub')
        footer.addWidget(self.estimate, 1)
        self.start_button = button('Start benchmark', 'primary', self.start_run, icon='play')
        self.start_button.setEnabled(False)
        footer.addWidget(self.start_button)
        layout.addLayout(footer)
        self.progress_card = Card('Session activity', 'Ready when you are', 'gauge')
        self.progress_title = plain('Results are saved automatically after each session.', 'sub')
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setValue(0)
        self.stop_button = button('Stop', slot=self.stop_run, icon='stop')
        self.stop_button.setEnabled(False)
        self.elapsed_label = plain('', 'muted')
        self.progress_card.actions.addWidget(self.elapsed_label)
        self.progress_card.actions.addWidget(self.stop_button)
        self.run_clock = QTimer(self)
        self.run_clock.timeout.connect(self.update_elapsed)
        self.progress_card.body.addWidget(self.progress_title)
        self.progress_card.body.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.log.setFixedHeight(118)
        self.log.setPlaceholderText('Progress and benchmark messages appear here.')
        self.progress_card.body.addWidget(self.log)
        layout.addWidget(self.progress_card)
        layout.addStretch()

    def build_history(self):
        self.heading('history', 'Your benchmark history', 'Every session, every measurement, in one place.',
                     button('Refresh', slot=self.refresh_data, icon='refresh'))
        layout = self.pages['history']
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search sessions by name, date, or suite…')
        self.search.textChanged.connect(self.filter_history)
        layout.addWidget(self.search)
        self.history_table = table(['Session', 'Score', 'Date', 'Tests', 'Duration', 'Status'])
        self.history_table.setMinimumHeight(215)
        self.history_table.setMaximumHeight(310)
        self.history_table.itemSelectionChanged.connect(self.select_history)
        layout.addWidget(self.history_table)
        self.detail = Card('Selected session', 'Run details', 'details')
        self.detail_title = plain('Select a session to explore its results.', 'cardTitle')
        self.detail_meta = plain('', 'sub')
        self.detail.body.addWidget(self.detail_title)
        self.detail.body.addWidget(self.detail_meta)
        self.details_table = table(['Measurement', 'Average', 'Spread (min–max)', 'Samples'])
        self.details_table.setMinimumHeight(240)
        self.detail.body.addWidget(self.details_table)
        self.detail_environment = plain('', 'muted')
        self.detail.body.addWidget(self.detail_environment)
        self.report_button = button('Export report', slot=self.export_run, icon='download')
        self.baseline_button = button('Use as baseline', slot=self.use_baseline, icon='sliders')
        self.report_button.setEnabled(False)
        self.baseline_button.setEnabled(False)
        self.detail.actions.addWidget(self.baseline_button)
        self.detail.actions.addWidget(self.report_button)
        layout.addWidget(self.detail)
        layout.addStretch()

    def build_compare(self):
        self.heading('compare', 'See the difference', 'Compare the same measurements across two saved sessions.')
        layout = self.pages['compare']
        pick = Card('A / B comparison', 'Choose two sessions', 'sliders')
        line = QHBoxLayout()
        self.compare_a, self.compare_b = QComboBox(), QComboBox()
        for name, combo in [('A · Baseline', self.compare_a), ('B · Candidate', self.compare_b)]:
            group = QVBoxLayout()
            group.addWidget(plain(name, 'kicker'))
            group.addWidget(combo)
            line.addLayout(group, 1)
            combo.currentIndexChanged.connect(self.update_comparison)
        pick.body.addLayout(line)
        self.compare_note = plain('Save two sessions to start comparing.', 'sub')
        pick.body.addWidget(self.compare_note)
        layout.addWidget(pick)
        self.compare_summary = QHBoxLayout()
        layout.addLayout(self.compare_summary)
        card = Card('Measurements', 'What changed', 'gauge')
        self.compare_export = button('Export comparison', slot=self.export_comparison, icon='download')
        self.compare_export.setEnabled(False)
        card.actions.addWidget(self.compare_export)
        self.compare_table = table(['Measurement', 'Baseline', 'Candidate', 'Change', 'Verdict'])
        self.compare_table.setMinimumHeight(300)
        card.body.addWidget(self.compare_table)
        card.body.addWidget(plain('Verdicts use 95% bootstrap ranges and need at least three repetitions per session. '
                                  '“Within noise” means these samples do not establish a difference.', 'muted'))
        layout.addWidget(card)
        self.compare_environment = plain('', 'sub')
        layout.addWidget(self.compare_environment)
        layout.addStretch()

    def refresh_data(self):
        if self.demo:
            self.refresh_views()
            return
        if self.scan and self.scan.state() != QProcess.NotRunning:
            return
        if self.busy:
            self.notice.setText('Hardware refresh is paused while a benchmark is running.')
            return
        self.notice.setText('Reading saved results and checking available tests…')
        self.scan = Worker(self, self.scan_event, self.scan_done)
        self.scan.launch(['scan'])

    def scan_event(self, data):
        if data['event'] == 'history':
            self.runs = data['runs']
            self.history_errors = data['errors']
            self.refresh_views()
        elif data['event'] == 'snapshot':
            self.environment, self.statuses = data['environment'], data['runners']
            self.refresh_views()
        elif data['event'] == 'error':
            self.notice.setText('Could not refresh: ' + data['text'])

    def scan_done(self, code):
        if code == 0:
            errors = getattr(self, 'history_errors', [])
            self.notice.setText(f'{len(errors)} unreadable result file(s) skipped.' if errors else
                                'Results stay on this computer. Export a report whenever you want to share one.')
            if errors:
                self.notice.setToolTip('\n'.join(errors))

    def refresh_views(self):
        self.render_score()
        previous = self.trend_metric.currentText()
        self.trends = series(self.runs)
        self.trend_metric.blockSignals(True)
        self.trend_metric.clear()
        for trend in self.trends:
            self.trend_metric.addItem(trend['name'])
        index = self.trend_metric.findText(previous)
        self.trend_metric.setCurrentIndex(max(0, index))
        self.trend_metric.blockSignals(False)
        self.change_trend()
        env = self.environment
        self.machine_text.setText('\n\n'.join(str(env[k]) for k in ('cpu', 'gpu') if env.get(k)) +
                                  (f"\n\n{env.get('ram_gb', '—')} GB RAM · {env.get('scheduler', '—')}\n{env.get('kernel', '')}" if env else
                                   'System details will appear here.'))
        for key, status in self.statuses.items():
            text = 'Ready' if status['available'] else status['reason']
            if key == 'game-beamng' and status['available']:
                text = 'Experimental · long-running physics workload'
            self.runner_status[key].setText(text)
            self.runner_status[key].setStyleSheet(f"color: {S.SUCCESS if status['available'] else S.WARNING};")
        self.selection_changed()
        self.filter_history()
        old_a, old_b = self.compare_a.currentData(), self.compare_b.currentData()
        for combo in (self.compare_a, self.compare_b):
            combo.blockSignals(True)
            combo.clear()
            for run in self.runs:
                combo.addItem(title(run) + ' · ' + time.strftime('%d %b %H:%M', time.localtime(run['started'])), run['id'])
        for combo, old, default in ((self.compare_a, old_a, max(0, len(self.runs)-2)),
                                    (self.compare_b, old_b, len(self.runs)-1)):
            index = combo.findData(old)
            combo.setCurrentIndex(index if index >= 0 else default)
            combo.blockSignals(False)
        self.update_comparison()

    def change_trend(self):
        index = self.trend_metric.currentIndex()
        if index < 0 or not getattr(self, 'trends', []):
            self.trend.set_series([], '')
            self.trend_hint.setText('Completed tests create your history. Failed tests are excluded.')
            return
        trend = self.trends[index]
        self.trend.set_series(trend['points'], trend['unit'])
        self.trend_hint.setText(f"{len(trend['points'])} sessions · {trend['unit']} · " +
                               ('Higher is better' if trend['higher'] else 'Lower is better') +
                               ' · Each point is one session’s average')

    def choose_setting(self):
        setting = SETTINGS[self.experiment_setting.currentData()]
        for combo, default in ((self.experiment_a, 0), (self.experiment_b, 1)):
            combo.clear()
            for value in setting.values:
                combo.addItem(setting.label(value), value)
            combo.setCurrentIndex(default)

    def choose_suite(self):
        choice = self.suite.currentIndex()
        if choice < 2:
            for key, check in self.checks.items():
                check.setChecked((ALL[key].group == 'game') if choice == 1 else (ALL[key].group != 'game'))
        self.selection_changed()

    def selection_changed(self):
        if not hasattr(self, 'start_button'):
            return
        selected = [key for key, check in self.checks.items() if check.isChecked()]
        ready = [key for key in selected if self.statuses.get(key, {}).get('available')]
        both = hasattr(self, 'experiment_on') and self.experiment_on.isChecked()
        mins = sum(ALL[key].minutes for key in ready)*self.repeat.value()*(2 if both else 1)
        self.estimate.setText(f'{len(ready)} ready / {len(selected)} selected · roughly {mins:.0f} min + cooldowns\n'
                              'Unavailable tests are skipped. Three or more repetitions are recommended.')
        self.start_button.setEnabled(bool(ready) and not self.busy)

    def filter_history(self):
        query = self.search.text().strip().lower()
        selected_id = self.selected['id'] if self.selected else None
        self.filtered = [r for r in reversed(self.runs) if query in
                         (title(r) + ' ' + r.get('kind', '') + ' ' + time.strftime('%Y-%m-%d %d %b', time.localtime(r['started']))).lower()]
        self.history_table.blockSignals(True)
        rows = []
        for r in self.filtered:
            errors = sum(bool(x.get('error')) for x in r['results'])
            state = 'Stopped' if r.get('status') == 'cancelled' else 'Partial' if errors else 'Complete'
            sc = self.run_score(r)
            rows.append([title(r), f"{sc['total']:,}" if sc['total'] is not None else
                         (f"{sc['partial']:,} (partial)" if sc['partial'] is not None else '—'),
                         time.strftime('%d %b %Y · %H:%M', time.localtime(r['started'])),
                         len(r['results']), f"{r.get('seconds', 0)/60:.1f} min", state])
        fill_table(self.history_table, rows)
        self.history_table.blockSignals(False)
        index = next((i for i, r in enumerate(self.filtered) if r['id'] == selected_id), 0)
        if self.filtered:
            self.history_table.selectRow(index)
            self.select_history()
        else:
            self.selected = None
            self.detail_title.setText('No matching sessions.' if query else 'Run a benchmark to start your history.')
            self.detail_meta.clear()
            self.detail_environment.clear()
            self.details_table.setRowCount(0)
            self.report_button.setEnabled(False)
            self.baseline_button.setEnabled(False)

    def select_history(self):
        index = self.history_table.currentRow()
        if index < 0 or index >= len(self.filtered):
            return
        self.selected = run = self.filtered[index]
        self.detail_title.setText(title(run))
        self.detail_meta.setText(f"{run.get('repeat', '—')} repetitions · {run.get('seconds', 0)/60:.1f} minutes · " +
                                 ('Sample data' if self.demo else run['id']))
        rows = []
        for result in run['results']:
            if result.get('error'):
                rows.append([result['title'] + ' · ' + result['error'], '—', '—', '—'])
            for metric in result['metrics'].values():
                values = metric['values']
                rows.append([metric['name'] + (' (partial)' if result.get('error') else ''),
                             fmt(sum(values)/len(values), metric['unit']), f'{fmt(min(values))} – {fmt(max(values))}', len(values)])
        fill_table(self.details_table, rows)
        env = run['environment']
        sensor_text = []
        for result in run['results']:
            peaks = result.get('sensors', {})
            if peaks.get('cpu_temp'):
                sensor_text.append(peaks['cpu_temp']['max'])
        self.detail_environment.setText('\n'.join([f"{ENV_NAMES.get(k, k)}: {v}" for k, v in env.items() if v not in (None, '')]) +
                                        (f'\nPeak CPU temperature: {max(sensor_text):.1f} °C' if sensor_text else ''))
        self.report_button.setEnabled(True)
        self.baseline_button.setEnabled(len(self.runs) > 1)

    def open_session(self, run):
        self.search.clear()
        self.selected = run
        self.filter_history()
        self.navigate('history')

    def use_baseline(self):
        if self.selected:
            self.compare_a.setCurrentIndex(self.compare_a.findData(self.selected['id']))
            self.navigate('compare')

    def comparison_runs(self):
        a = next((r for r in self.runs if r['id'] == self.compare_a.currentData()), None)
        b = next((r for r in self.runs if r['id'] == self.compare_b.currentData()), None)
        return a, b

    def update_comparison(self):
        if self.comparison and self.comparison.state() != QProcess.NotRunning:
            self.comparison.stop(force=True)
            self.comparison.waitForFinished(100)
        self.comparison_rows = []
        self.compare_export.setEnabled(False)
        clear(self.compare_summary)
        fill_table(self.compare_table, [])
        self.compare_environment.clear()
        a, b = self.comparison_runs()
        if not a or not b or a['id'] == b['id']:
            self.compare_note.setText('Choose two different sessions to compare.')
            return
        diffs = [k for k in sorted(set(a['environment']) | set(b['environment'])) if a['environment'].get(k) != b['environment'].get(k)]
        self.compare_environment.setText('Environment changes\n' + '\n'.join(
            f"{ENV_NAMES.get(k, k)}: {a['environment'].get(k, '—')} → {b['environment'].get(k, '—')}" for k in diffs)
            if diffs else 'Recorded environment settings match. Unrecorded settings and background activity can still differ.')
        self.compare_note.setText('Calculating comparison ranges…')
        if self.demo:
            self.show_comparison(comparisons(a, b))
        else:
            self.comparison = Worker(self, self.comparison_event, self.comparison_done)
            self.comparison.launch(['compare', '--a', a['_folder'], '--b', b['_folder']])

    def comparison_event(self, data):
        if data['event'] == 'comparison':
            self.show_comparison(data['rows'])
        elif data['event'] == 'error':
            self.compare_note.setText(data['text'])

    def comparison_done(self, code):
        if code and self.compare_note.text() == 'Calculating comparison ranges…':
            self.compare_note.setText('Comparison could not finish. Refresh history and try again.')

    def show_comparison(self, rows):
        self.comparison_rows = rows
        self.compare_note.setText(f'{len(rows)} matching measurements · B relative to A' if rows else
                                 'No compatible completed measurements in these sessions.')
        names = {'better': 'Better', 'worse': 'Worse', 'same': 'Within noise', 'unsure': 'Need 3+ runs'}
        colors = {'better': S.SUCCESS, 'worse': S.DANGER, 'same': S.SUBTEXT, 'unsure': S.WARNING}
        for key in ('better', 'same', 'worse'):
            card = Card()
            card.body.addWidget(plain(names[key].upper(), 'kicker'))
            value = plain(str(sum(r['verdict'] == key for r in rows)), 'score')
            value.setStyleSheet(f'color: {colors[key]};')
            card.body.addWidget(value)
            self.compare_summary.addWidget(card)
        fill_table(self.compare_table, [[r['name'], fmt(r['a'], r['unit']), fmt(r['b'], r['unit']),
                                        f"{r['diff']:+.1f}%", names[r['verdict']]] for r in rows])
        for index, r in enumerate(rows):
            self.compare_table.item(index, 4).setForeground(QColor(colors[r['verdict']]))
            self.compare_table.item(index, 3).setToolTip(f"95% range: {r['low']:+.1f}% to {r['high']:+.1f}%" if r['low'] is not None else
                                                        'At least three repetitions per session are needed.')
        self.compare_export.setEnabled(bool(rows))

    def export_html(self, contents, suggested):
        path, _ = QFileDialog.getSaveFileName(self, 'Export benchmark report', suggested, 'HTML report (*.html)')
        if not path:
            return
        try:
            Path(path).write_text(contents, encoding='utf-8')
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve())))
        except OSError as error:
            QMessageBox.warning(self, 'Could not export report', str(error))

    def export_run(self):
        if self.selected:
            self.export_html(run_report(self.selected), 'deckos-bench-report.html')

    def export_comparison(self):
        a, b = self.comparison_runs()
        if a and b:
            self.export_html(compare_report(a, b), 'deckos-bench-comparison.html')

    def start_run(self):
        if self.busy:
            return
        keys = [key for key, check in self.checks.items() if check.isChecked()]
        if not any(self.statuses.get(k, {}).get('available') for k in keys):
            return
        self.busy, self.saved = True, False
        self.last_saved = {}
        self.run_started = time.monotonic()
        self.run_clock.start(1000)
        self.log.clear()
        self.progress.setValue(0)
        self.progress_title.setText('Preparing your benchmark…')
        self.stop_button.setEnabled(True)
        self.experiment_ids = None
        for control in [self.suite, self.run_label, self.repeat, *self.checks.values(), self.experiment_on,
                        self.experiment_setting, self.experiment_a, self.experiment_b]:
            control.setEnabled(False)
        self.selection_changed()
        if self.demo:
            self.demo_tick = 0
            self.demo_timer = QTimer(self)
            self.demo_timer.timeout.connect(self.advance_demo)
            self.demo_timer.start(350)
            self.log.appendPlainText('Demo session · no benchmarks will run and no results will be written.')
            return
        self.active = Worker(self, self.run_event, self.run_done)
        args = ['--keys', ','.join(keys), '--repeat', str(self.repeat.value()), '--label', self.run_label.text().strip()]
        if self.experiment_on.isChecked():
            a, b = self.experiment_a.currentData(), self.experiment_b.currentData()
            if a == b:
                self.log.appendPlainText('Choose two different values for A and B.')
                self.run_done(1)
                return
            self.active.launch(['experiment', *args, '--setting', self.experiment_setting.currentData(),
                                '--value-a', a, '--value-b', b])
        else:
            self.active.launch(['run', *args])

    def start_score(self):
        if self.busy:
            return
        self.busy, self.saved, self.score_mode = True, False, True
        self.last_saved = {}
        self.run_started = time.monotonic()
        self.run_clock.start(1000)
        self.log.clear()
        self.score_button.setEnabled(False)
        self.score_stop.show()
        self.score_stop.setEnabled(True)
        self.score_progress.setValue(0)
        self.score_progress.show()
        self.score_status.setText('Getting ready… Leave the PC alone until it finishes: other work lowers the score.')
        if self.demo:
            self.demo_tick = 0
            self.demo_timer = QTimer(self)
            self.demo_timer.timeout.connect(self.advance_demo)
            self.demo_timer.start(350)
            return
        self.active = Worker(self, self.run_event, self.run_done)
        self.active.launch(['score'])

    def update_elapsed(self):
        seconds = int(time.monotonic() - self.run_started)
        self.elapsed_label.setText(f"{seconds // 60:02d}:{seconds % 60:02d} elapsed")

    def advance_demo(self):
        self.demo_tick += 1
        self.progress.setValue(min(100, self.demo_tick*10))
        if getattr(self, 'score_mode', False):
            self.score_progress.setValue(min(100, self.demo_tick*10))
            self.score_status.setText(f'Demo · part {min(5, self.demo_tick // 2 + 1)} of 5')
        self.progress_title.setText(f'Demo · measuring CPU performance · step {self.demo_tick} of 10')
        if self.demo_tick >= 10:
            self.demo_timer.stop()
            self.saved = True
            self.log.appendPlainText('Demo complete. The sample history is unchanged.')
            self.run_done(0)

    def run_event(self, data):
        event = data['event']
        if event == 'log':
            self.log.appendPlainText(data['text'])
        elif event == 'progress':
            text = f"{ALL[data['key']].title} · " + \
                (f"repetition {data['repetition']} of {data['repeat']}" if data['repetition'] else 'preparing')
            value = int(100*(data['index'] + max(0, data['repetition']-1)/data['repeat'])/data['total'])
            self.progress_title.setText(text)
            self.progress.setValue(value)
            if getattr(self, 'score_mode', False):
                self.score_status.setText(f"Part {data['index'] + 1} of {data['total']} · {text}")
                self.score_progress.setValue(value)
        elif event == 'result':
            result = data['result']
            self.log.appendPlainText(result['title'] + ': ' + (result.get('error') or 'complete'))
        elif event == 'saved':
            self.saved = True
            self.last_saved = data['run']
            self.runs.append(data['run'])
            self.runs.sort(key=lambda r: r['started'])
            self.selected = data['run']
            self.log.appendPlainText('Saved: ' + data['folder'])
        elif event == 'experiment':
            self.experiment_ids = (data['a'], data['b'])
        elif event == 'error':
            self.log.appendPlainText('Error: ' + data['text'])

    def run_done(self, code):
        self.run_clock.stop()
        self.busy = False
        if getattr(self, 'score_mode', False):
            self.score_mode = False
            self.score_button.setEnabled(True)
            self.score_stop.hide()
            self.score_progress.hide()
            self.score_status.setText('' if self.saved else
                                      'The score run stopped before it finished. Lab › the log says why.')
        self.stop_button.setEnabled(False)
        for control in [self.suite, self.run_label, self.repeat, *self.checks.values(), self.experiment_on,
                        self.experiment_setting, self.experiment_a, self.experiment_b]:
            control.setEnabled(True)
        cancelled = getattr(self, 'last_saved', {}).get('status') == 'cancelled'
        if self.saved:
            self.progress.setValue(100)
            self.progress_title.setText('Stopped · completed samples saved in History.' if cancelled else
                                        'Session saved. Explore your results in History.' if not self.demo else 'Demo complete.')
        else:
            self.progress_title.setText('Session stopped or failed. See the log below; no new report was saved.')
            if self.active and self.active.stderr:
                self.log.appendPlainText(self.active.stderr)
        if not getattr(self, "closing", False):
            self.refresh_views()
            ids = getattr(self, 'experiment_ids', None)
            if ids:  # straight to the answer: A against B
                self.compare_a.setCurrentIndex(self.compare_a.findData(ids[0]))
                self.compare_b.setCurrentIndex(self.compare_b.findData(ids[1]))
                self.navigate('compare')

    def stop_run(self):
        if not self.busy:
            return
        self.stop_button.setEnabled(False)
        self.progress_title.setText('Stopping the workload and saving completed samples…')
        if self.demo:
            self.demo_timer.stop()
            self.run_done(0)
        elif self.active:
            active = self.active
            active.stop()
            QTimer.singleShot(5000, lambda: active.stop(force=True))

    def closeEvent(self, event):
        if self.busy:
            answer = QMessageBox.question(self, 'Benchmark running', 'Stop the current benchmark and close Bench?')
            if answer != QMessageBox.Yes:
                event.ignore()
                return
        self.closing = True
        for worker in (self.active, self.scan, self.comparison):
            if worker and worker.state() != QProcess.NotRunning:
                worker.stop()
                if not worker.waitForFinished(1500):
                    worker.stop(force=True)
                    worker.waitForFinished(1000)
        event.accept()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--page', choices=[x[0] for x in NAV], default='overview')
    parser.add_argument('--screenshot', type=Path, help='render all demo pages into this directory')
    args = parser.parse_args()
    if args.screenshot:
        args.demo = True
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    app = QApplication(sys.argv)
    app.setApplicationName('DecKoOS Bench')
    app.setDesktopFileName('deckos-bench')
    for font in (HERE.parents[2] / 'share/fonts/deckos').glob('*.otf'):
        QFontDatabase.addApplicationFont(str(font))
    app.setFont(QFont('Inter', 10))
    app.setStyleSheet(stylesheet())
    window = Bench(args.demo)
    window.navigate(args.page)
    window.show()
    if args.screenshot:
        args.screenshot.mkdir(parents=True, exist_ok=True)
        def capture():
            for key, _, _ in NAV:
                window.navigate(key)
                app.processEvents()
                window.grab().save(str(args.screenshot / f'bench-{key}.png'))
            app.quit()
        QTimer.singleShot(300, capture)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
