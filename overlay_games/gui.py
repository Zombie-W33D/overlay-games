def run(args):
    from PySide6.QtWidgets import (
        QApplication, QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
        QLineEdit, QComboBox, QListWidget, QPushButton, QSplitter, QVBoxLayout,
        QListWidgetItem, QMessageBox, QWidget,
    )
    from PySide6.QtCore import Qt, QSize

    from . import actions, lua_registry, steam, steam_config, trust_conf, hypr

    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Overlay Games")

    class LocalGameDialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Add local game")
            form = QFormLayout(self)
            self.cls = QLineEdit()
            self.name = QLineEdit()
            self.widget = QCheckBox("widget mode (idle/desktop-pet: lets the game size itself)")
            self.picker = QComboBox()
            self.picker.setEditable(False)
            wins = hypr.running_windows()
            if wins:
                self.picker.addItem("— pick from a running window —", None)
                for c, t in wins:
                    self.picker.addItem("%s  (%s)" % (t or c, c), c)
                self.picker.currentIndexChanged.connect(self._on_pick)
            else:
                self.picker.addItem("(no windows running right now)")
                self.picker.setEnabled(False)
            form.addRow("Source", self.picker)
            form.addRow("Window class", self.cls)
            form.addRow("Display name", self.name)
            form.addRow(self.widget)
            btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            btns.accepted.connect(self.accept)
            btns.rejected.connect(self.reject)
            form.addRow(btns)

        def _on_pick(self, _):
            if self.picker.currentData():
                self.cls.setText(self.picker.currentData())

        def values(self):
            return (self.cls.text().strip(),
                    (self.name.text() or self.cls.text()).strip(),
                    self.widget.isChecked())

    class Main(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Overlay Games — trusted click-through manager")
            self.resize(760, 420)

            left = QVBoxLayout()
            left.addWidget(QLabel("Installed Steam games"))
            self.steam_list = QListWidget()
            left.addWidget(self.steam_list)

            right = QVBoxLayout()
            right.addWidget(QLabel("Registered as overlay"))
            self.registered = QListWidget()
            right.addWidget(self.registered)

            middle = QVBoxLayout()
            self.widget_chk = QCheckBox("widget mode (lets it size itself)")
            self.widget_chk.setToolTip(
                "For idle/desktop-pet games that expand by cursor hover: keeps float + "
                "click-through but the game controls its own size (no full-screen enforcement).")
            self.steam_setup_chk = QCheckBox("Steam: launch options + GE-Proton")
            self.steam_setup_chk.setToolTip(
                "Also writes WINE_LAYERED_OVERLAY_ALPHA=1 WINE_LAYERED_OVERLAY_INPUT_SHAPE=1 "
                "into Steam launch options and forces the detected GE-Proton compat tool.\n"
                "Works only when registering a Steam game.")
            self.btn_add = QPushButton("Register →")
            self.btn_remove = QPushButton("← Unregister")
            self.btn_local = QPushButton("Add local game…")
            self.btn_refresh = QPushButton("Refresh")
            middle.addStretch(1)
            middle.addWidget(self.widget_chk)
            middle.addWidget(self.steam_setup_chk)
            for b in (self.btn_add, self.btn_remove, self.btn_local, self.btn_refresh):
                middle.addWidget(b)
            middle.addStretch(1)

            row = QHBoxLayout()
            split = QSplitter()
            wrap_l = QWidget(); wrap_l.setLayout(left); wrap_l.setMinimumWidth(260)
            wrap_m = QWidget(); wrap_m.setLayout(middle); wrap_m.setFixedWidth(180)
            wrap_r = QWidget(); wrap_r.setLayout(right); wrap_r.setMinimumWidth(260)
            split.addWidget(wrap_l); split.addWidget(wrap_m); split.addWidget(wrap_r)
            row.addWidget(split)

            self.status = QLabel("")
            self.status.setWordWrap(True)
            col = QVBoxLayout(self)
            col.addLayout(row, 1)
            col.addWidget(self.status)

            self.btn_add.clicked.connect(self._on_add)
            self.btn_remove.clicked.connect(self._on_remove)
            self.btn_local.clicked.connect(self._on_local)
            self.btn_refresh.clicked.connect(self.refresh)

            self.refresh()

        def refresh(self):
            self.registered.clear()
            for e in lua_registry.read_entries(args.config):
                tag = "steam" if e["kind"] == "steam" else "local"
                widget = " [widget]" if e.get("widget") else ""
                it = QListWidgetItem("%s  (%s)  [%s]%s" % (e["name"], e["class"], tag, widget))
                it.setData(Qt.UserRole, e["class"])
                self.registered.addItem(it)
            self.steam_list.clear()
            for g in steam.installed_games():
                cls = lua_registry.steamp_class(g["appid"])
                reg = any(e["class"] == cls for e in lua_registry.read_entries(args.config))
                it = QListWidgetItem("%s  (%s%s)" % (g["name"], g["appid"], "  ✓" if reg else ""))
                it.setData(Qt.UserRole, g["appid"])
                it.setFlags(it.flags() & ~Qt.ItemIsSelectable if reg else it.flags())
                self.steam_list.addItem(it)
            self.ge_name = steam_config.detect_ge_proton()
            steam_alive = steam_config.steam_is_running()
            if self.ge_name and steam_alive:
                self.steam_setup_chk.setEnabled(True)
                self.steam_setup_chk.setChecked(True)
                self.steam_setup_chk.setText("Steam: launch options + %s" % self.ge_name)
                self.steam_setup_chk.setToolTip(
                    "Steam is running — it keeps these in memory and rewrites the "
                    "files when it exits, so the write may not survive. The tool "
                    "will warn after registering if so.")
                self.status.setText("config: %s — Steam is running" % args.config)
            elif self.ge_name:
                self.steam_setup_chk.setEnabled(True)
                self.steam_setup_chk.setChecked(True)
                self.steam_setup_chk.setText("Steam: launch options + %s" % self.ge_name)
                self.steam_setup_chk.setToolTip(
                    "Also writes WINE_LAYERED_OVERLAY_ALPHA=1 WINE_LAYERED_OVERLAY_INPUT_SHAPE=1 "
                    "into Steam launch options and forces the detected GE-Proton compat tool.\n"
                    "Works only when registering a Steam game. Steam must be restarted after.")
                self.status.setText("config: %s" % args.config)
            else:
                self.steam_setup_chk.setEnabled(False)
                self.steam_setup_chk.setChecked(False)
                self.steam_setup_chk.setText("Steam setup (no GE-Proton detected)")
                self.steam_setup_chk.setToolTip(
                    "No GE-Proton compatibility tool found in Steam yet. Force a "
                    "GE-Proton tool on any game in Steam first, then refresh.")
                self.status.setText("config: %s" % args.config)

        def _on_add(self):
            item = self.steam_list.currentItem()
            if not item:
                return
            appid = item.data(Qt.UserRole)
            g = steam.app_by_id(appid)
            try:
                actions.add_steam(args.config, appid, g["name"] if g else None,
                                  widget=self.widget_chk.isChecked())
            except actions.ActionError as e:
                QMessageBox.warning(self, "overlay-games", str(e))
                return
            setup_msg = ""
            if self.steam_setup_chk.isChecked():
                try:
                    setup_msg = steam_config.apply_steam_setup(appid, self.ge_name)
                    if steam_config.steam_is_running():
                        QMessageBox.information(
                            self, "overlay-games",
                            "Steam launch options + GE-Proton written.\n\n"
                            "But Steam is running and keeps its config in memory: it can "
                            "overwrite these files when it exits, so the change may not stick.\n\n"
                            "Fully quit Steam (Steam menu → Exit), relaunch it, then start the "
                            "game. Use 'list --steam-setup' to verify what Steam actually has.")
                except steam_config.SteamConfigError as e:
                    setup_msg = "Steam setup skipped: %s" % e
            self._after_change("registered Steam %s" % appid, extra=setup_msg)

        def _on_remove(self):
            item = self.registered.currentItem()
            if not item:
                return
            cls = item.data(Qt.UserRole)
            kind = "local"
            if lua_registry.is_steam_class(cls):
                appid = cls.split("_")[-1]
                kind = "steam"
                ok = QMessageBox.question(
                    self, "Unregister?",
                    "Remove %s (%s) from the overlay registry?" % (cls, appid),
                )
                if ok != QMessageBox.Yes:
                    return
            try:
                if kind == "steam":
                    actions.remove_steam(args.config, appid)
                else:
                    actions.remove_local(args.config, args.trust, cls)
            except actions.ActionError as e:
                QMessageBox.warning(self, "overlay-games", str(e))
                return
            self._after_change("removed %s" % cls)

        def _on_local(self):
            dlg = LocalGameDialog(self)
            if dlg.exec() != QDialog.Accepted:
                return
            cls, name, widget = dlg.values()
            try:
                actions.add_local(args.config, args.trust, cls, name, widget=widget)
            except actions.ActionError as e:
                QMessageBox.warning(self, "overlay-games", str(e))
                return
            self._after_change("registered local %s" % cls)

        def _after_change(self, msg, extra=""):
            ok, how = actions.reload_hypr()
            warn = ""
            try:
                actions.reload_trust()
            except actions.ActionError as e:
                warn = "  " + str(e)
            self.refresh()
            if not ok:
                QMessageBox.warning(self, "overlay-games", "config errors:\n" + how)
            self.status.setText("%s — reload %s%s%s" % (msg, "ok" if ok else "FAILED", warn,
                                                        ("  " + extra) if extra else ""))

    w = Main()
    w.show()
    if __import__("os").environ.get("OVERLAY_GAMES_SELFTEST"):
        from PySide6.QtCore import QTimer

        QTimer.singleShot(2500, app.quit)
    return app.exec()