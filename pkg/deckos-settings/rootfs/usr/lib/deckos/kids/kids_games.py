"""Kid mode's own games, built in: Bubble pop and Memory match. Mouse, touch, arrow keys and a controller (through
KidMode's pad) all work; no internet, no ads, nothing to buy. Each game paints itself over the child's theme and
says `back` when the child wants the home screen again.
"""
import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from kids_themes import Scene, emoji

GAMES = [("bubbles", "Bubble pop", "🫧"), ("memory", "Memory match", "🧠")]


class Game(QWidget):
    back = Signal()

    def __init__(self, theme_id):
        super().__init__()
        self.scene = Scene(theme_id, seed=3)
        self.tick = 0
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.clock = QTimer(self, interval=33, timeout=self.step)  # 30 frames a second while it's being played

    def showEvent(self, e):
        super().showEvent(e)
        self.start()
        self.clock.start()
        self.setFocus()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.clock.stop()

    def step(self):
        self.tick += 1
        self.update()

    def back_rect(self):
        return QRectF(24, 20, 150, 56)

    def paint_frame(self, p, title, score):
        """The theme behind, a big Back button and the score: what both games share."""
        self.scene.paint(p, QRectF(self.rect()), self.tick // 6)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 90))
        p.drawRoundedRect(self.back_rect(), 28, 28)
        p.setPen(QColor("#FFFFFF"))
        f = QFont("Inter Display", 18, QFont.Bold)
        p.setFont(f)
        p.drawText(self.back_rect(), Qt.AlignCenter, "← Back")
        p.setPen(QColor(self.scene.t["text"]))  # dark on the light themes, so it's easy to read
        p.drawText(QRectF(0, 20, self.width(), 56), Qt.AlignCenter, title)
        p.drawText(QRectF(self.width() - 324, 20, 300, 56), Qt.AlignRight | Qt.AlignVCenter, score)

    def mousePressEvent(self, e):
        if self.back_rect().contains(e.position()):
            self.back.emit()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Escape, Qt.Key_Backspace):
            self.back.emit()
        else:
            self.key(e.key())

    def key(self, k):
        pass


class BubblePop(Game):
    """Bubbles float up with a little friend inside; pop them. Arrow keys or the stick move the wand."""

    FRIENDS = "🐱🐶🐰🐸🐼🦊🐵🐧🐢🐞⭐🍓"

    def start(self):
        self.bubbles, self.popped, self.score = [], [], 0
        self.wand = QPointF(self.width() / 2, self.height() / 2)

    def step(self):
        w, h = self.width(), self.height()
        if len(self.bubbles) < 9 and random.random() < 0.05:
            r = random.uniform(38, 62)
            self.bubbles.append({"x": random.uniform(r + 40, w - r - 40), "y": h + r, "r": r,
                                 "v": random.uniform(1.2, 2.6), "phase": random.random() * 6,
                                 "who": random.choice(self.FRIENDS),
                                 "hue": random.choice(("#7AB8FF", "#FF8FC8", "#8FF0C8", "#FFD27A", "#C8A8FF"))})
        for b in self.bubbles:
            b["y"] -= b["v"]
        self.bubbles = [b for b in self.bubbles if b["y"] > -b["r"] - 10]
        self.popped = [(x, y, t + 1, who) for x, y, t, who in self.popped if t < 18]
        super().step()

    def pop_at(self, pos):
        for b in reversed(self.bubbles):
            x = b["x"] + 10 * math.sin(self.tick * 0.05 + b["phase"])
            if (QPointF(x, b["y"]) - pos).manhattanLength() < b["r"] * 1.3:
                self.bubbles.remove(b)
                self.popped.append((x, b["y"], 0, b["who"]))
                self.score += 1
                return

    def mousePressEvent(self, e):
        if self.back_rect().contains(e.position()):
            self.back.emit()
        else:
            self.pop_at(e.position())

    def key(self, k):
        d = {Qt.Key_Left: (-60, 0), Qt.Key_Right: (60, 0), Qt.Key_Up: (0, -60), Qt.Key_Down: (0, 60)}.get(k)
        if d:
            self.wand = QPointF(min(max(self.wand.x() + d[0], 40), self.width() - 40),
                                min(max(self.wand.y() + d[1], 100), self.height() - 40))
        elif k in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.pop_at(self.wand)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self.paint_frame(p, "Bubble pop", f"⭐ {self.score}")
        for b in self.bubbles:
            x = b["x"] + 10 * math.sin(self.tick * 0.05 + b["phase"])
            g = QRadialGradient(QPointF(x - b["r"] * 0.35, b["y"] - b["r"] * 0.35), b["r"] * 1.2)
            g.setColorAt(0, QColor(255, 255, 255, 200))
            c = QColor(b["hue"])
            c.setAlpha(110)
            g.setColorAt(1, c)
            p.setPen(QPen(QColor(255, 255, 255, 180), 2))
            p.setBrush(g)
            p.drawEllipse(QPointF(x, b["y"]), b["r"], b["r"])
            emoji(p, b["who"], x, b["y"], b["r"] * 0.9)
        for x, y, t, who in self.popped:  # a burst, and the friend hops out
            p.setPen(QPen(QColor(255, 255, 255, 255 - t * 14), 3))
            for i in range(8):
                a = i * math.pi / 4
                p.drawLine(QPointF(x + math.cos(a) * (20 + t * 3), y + math.sin(a) * (20 + t * 3)),
                           QPointF(x + math.cos(a) * (30 + t * 4), y + math.sin(a) * (30 + t * 4)))
            emoji(p, who, x, y - t * 4, 40)
        # The wand, for the keyboard and controller
        p.setPen(QPen(QColor("#FFFFFF"), 4))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(self.wand, 26, 26)
        p.drawLine(self.wand + QPointF(-36, 0), self.wand + QPointF(-16, 0))
        p.drawLine(self.wand + QPointF(16, 0), self.wand + QPointF(36, 0))


class MemoryMatch(Game):
    """Turn two cards; a pair stays face up. Twelve cards, so a game is a few minutes."""

    PICTURES = "🐶🐱🦁🐸🐵🦄🐙🐢🍎🍌🚗🚀"
    COLS = 4

    def start(self):
        pics = random.sample(self.PICTURES, 6) * 2
        random.shuffle(pics)
        self.cards = [{"pic": c, "up": False, "done": False} for c in pics]
        self.turned, self.focus, self.moves, self.wait = [], 0, 0, 0

    def card_rects(self):
        rows = math.ceil(len(self.cards) / self.COLS)
        size = min((self.width() - 160) / self.COLS, (self.height() - 160) / rows) - 18
        left = (self.width() - (size + 18) * self.COLS) / 2
        top = 110 + (self.height() - 130 - (size + 18) * rows) / 2
        return [QRectF(left + (i % self.COLS) * (size + 18), top + (i // self.COLS) * (size + 18), size, size)
                for i in range(len(self.cards))]

    def step(self):
        if self.wait:
            self.wait -= 1
            if not self.wait:  # not a pair: turn them back
                for i in self.turned:
                    self.cards[i]["up"] = False
                self.turned = []
        super().step()

    def turn(self, i):
        c = self.cards[i]
        if self.wait or c["up"] or c["done"]:
            return
        c["up"] = True
        self.turned.append(i)
        if len(self.turned) == 2:
            self.moves += 1
            a, b = (self.cards[j] for j in self.turned)
            if a["pic"] == b["pic"]:
                a["done"] = b["done"] = True
                self.turned = []
            else:
                self.wait = 30  # a second to look before they turn back

    def mousePressEvent(self, e):
        if self.back_rect().contains(e.position()):
            self.back.emit()
            return
        if all(c["done"] for c in self.cards):
            self.start()
            return
        for i, r in enumerate(self.card_rects()):
            if r.contains(e.position()):
                self.focus = i
                self.turn(i)

    def key(self, k):
        if all(c["done"] for c in self.cards) and k in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.start()
            return
        step = {Qt.Key_Left: -1, Qt.Key_Right: 1, Qt.Key_Up: -self.COLS, Qt.Key_Down: self.COLS}.get(k)
        if step is not None:
            self.focus = max(0, min(len(self.cards) - 1, self.focus + step))
        elif k in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.turn(self.focus)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self.paint_frame(p, "Memory match", f"Turns: {self.moves}")
        tiles = self.scene.t["tiles"]
        for i, (c, r) in enumerate(zip(self.cards, self.card_rects())):
            path = QPainterPath()
            path.addRoundedRect(r, 22, 22)
            if c["up"] or c["done"]:
                p.fillPath(path, QColor("#FFFFFF"))
                emoji(p, c["pic"], r.center().x(), r.center().y(), r.height() * 0.32)
                if c["done"]:
                    p.fillPath(path, QColor(80, 200, 120, 60))
            else:
                p.fillPath(path, QColor(tiles[i % len(tiles)]))
                p.setPen(QColor(255, 255, 255, 220))
                p.setFont(QFont("Inter Display", int(r.height() * 0.28), QFont.Bold))
                p.drawText(r, Qt.AlignCenter, "?")
            if i == self.focus:
                p.setPen(QPen(QColor("#FFFFFF"), 6))
                p.setBrush(Qt.NoBrush)
                p.drawPath(path)
        if all(c["done"] for c in self.cards):
            box = QRectF(self.width() / 2 - 260, self.height() / 2 - 90, 520, 180)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 160))
            p.drawRoundedRect(box, 30, 30)
            p.setPen(QColor("#FFFFFF"))
            p.setFont(QFont("Inter Display", 26, QFont.Bold))
            p.drawText(box.adjusted(0, 18, 0, -60), Qt.AlignCenter, f"You found them all! 🎉")
            p.setFont(QFont("Inter Display", 16))
            p.drawText(box.adjusted(0, 90, 0, -10), Qt.AlignCenter, f"In {self.moves} turns. Tap to play again.")


def make(game_id, theme_id):
    return {"bubbles": BubblePop, "memory": MemoryMatch}[game_id](theme_id)
