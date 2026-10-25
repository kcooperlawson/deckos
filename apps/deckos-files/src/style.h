// DecKoOS look for DecKoOS Files: the Hub's palette, the DecKoOS line icons and a little QSS for the
// chrome. Item views never get QSS (it routes every paint through QStyleSheetStyle); they paint
// with these colours directly.
#pragma once

#include <QColor>
#include <QIcon>
#include <QPixmap>
#include <QPointF>
#include <QString>

class QApplication;
class QPainter;
class QRectF;

namespace Style {

inline const QColor Bg{0x0F, 0x11, 0x15};
inline const QColor Sidebar{0x0B, 0x0D, 0x11};
inline const QColor Surface{0x17, 0x1A, 0x21};
inline const QColor Raised{0x1D, 0x21, 0x2A};
inline const QColor Border{0x26, 0x2B, 0x36};
inline const QColor Hover{0x2A, 0x2F, 0x3B};
inline const QColor Pressed{0x35, 0x3B, 0x49};
inline const QColor Text{0xE8, 0xEA, 0xF0};
inline const QColor Subtext{0x8C, 0x94, 0xA6};
inline const QColor Muted{0x5A, 0x61, 0x72};
inline const QColor Danger{0xFF, 0x6B, 0x6B};
inline const QColor Warning{0xF5, 0xB8, 0x4B};

// Plasma's accent colour (kdeglobals), or the DecKoOS blue.
QColor accent();
QColor accentPartner();  // the violet-shifted gradient partner
QColor selectionFill();  // accent at ~22%
QColor hoverFill();

constexpr int Radius = 10;

void apply(QApplication &app);
QString chromeQss();

// A DecKoOS line icon (assets/icons.py), recoloured per state: subtext normally, text on hover,
// muted when disabled, accent when checked.
QIcon icon(const QString &name);
QPixmap pixmap(const QString &name, const QColor &color, int size, qreal dpr);

// Cached QIcon::fromTheme for file icons.
QIcon themeIcon(const QString &name);

// The brand motif: a small screw head, for plate corners.
void drawScrew(QPainter &p, const QPointF &center, qreal r = 2.2);

QString kicker(const QString &text);  // "PLACES" style labels
}
