"""Kleines Fenster (nicht Vollbild): keine Seite und kein Setup-Bereich darf rechts abgeschnitten werden."""

from __future__ import annotations

from test_gui import env, pump  # noqa: F401


def _overflow(window) -> list:
    from PySide6.QtWidgets import QScrollArea, QWidget

    out = []
    for area in window.findChildren(QScrollArea):
        inner = area.widget()
        if area.isVisible() and inner is not None and inner.width() > area.viewport().width() + 1:
            vw = area.viewport().width()
            wide = [(w.minimumSizeHint().width(), type(w).__name__, (w.text()[:30] if hasattr(w, "text")
                                                                     and callable(w.text) else ""))
                    for w in inner.findChildren(QWidget) if w.isVisible() and w.minimumSizeHint().width() > vw - 80]
            out.append((inner.width(), vw, sorted(wide)[:6]))
    return out


def _show_optional(window) -> None:
    """Teile, die nur mit Gerät erscheinen (z. B. Fingerabdruck-Sensor), auch zeigen – sie dürfen nicht verbreitern."""
    from alupc.ui.fingerprint_page import FingerprintPage

    for page in window.findChildren(FingerprintPage):
        for w in (page.person_row, page.account_hint, page.delete_btn, page.delete_all_btn, page.finger_combo):
            w.show()
        page.account_hint.setText("Personen sind keine Benutzerkonten – alle entsperren dieses Konto")
        page.usage_label.setText("3 von 10 Plätzen belegt")
    pump(2)


def test_nothing_cut_off_in_small_window(env):  # noqa: F811
    _controller, window, _ = env
    from PySide6.QtWidgets import QApplication

    from alupc.ui import theme

    theme.apply(QApplication.instance(), "hell", "alupc")  # wie die App: eigene Schrift (Inter) – breiter als die Standardschrift
    assert window.minimumWidth() <= 600
    for size in ((1440, 900), (900, 600), (640, 480), (600, 460)):  # vom großen Fenster aus verkleinern
        window.resize(*size)
        pump(3)
        for i in range(len(window.pages)):
            window._go(i)
            pump(4)
            _show_optional(window)
            assert not _overflow(window), (size, f"Seite {i}", _overflow(window))
        window._go(2)
        pump(3)
        setup = window.setup
        for k, (_icon, title, _sub) in enumerate(setup.SECTIONS):
            setup.nav.setCurrentRow(k)
            pump(3)
            assert not _overflow(window), (size, f"Setup → {title}", _overflow(window))
