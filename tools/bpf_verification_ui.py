"""PySide6 UI for configuring, running, and browsing BPF verification flows."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "reports"

TEST_OPTIONS = {
    "Configurable Traffic": "tests/integration/stress/test_bpf_env_configurable_traffic.py",
    "Packet Loss Golden Model": "tests/integration/advanced/test_bpf_env_packet_loss_golden_model.py",
    "Random Traffic 5000 Loss": "tests/integration/stress/test_bpf_env_random_traffic_5000_loss.py",
    "Long Program With Packet Loss": "tests/integration/advanced/test_bpf_env_long_program_with_packet_loss.py",
    "Ingress Drop Model": "tests/integration/advanced/test_bpf_env_ingress_drop_model.py",
}

PROTOCOL_MODE_OPTIONS = {
    "TCP": 1,
    "UDP": 2,
    "TCP + UDP": 3,
    "TCP + UDP + IP": 4,
}

ERROR_LEVEL_OPTIONS = {
    "Packet Loss Only": 1,
    "CRC Errors + Packet Loss": 2,
}

TEST_METADATA = {
    "Configurable Traffic": {
        "subtitle": "Configurable packet generation with protocol and error selection.",
        "fields": {"unique_packets", "protocol_mode", "error_level", "seed", "randomize_fields"},
    },
    "Packet Loss Golden Model": {
        "subtitle": "Golden-model loss schedule with deterministic traffic and waveform correlation.",
        "fields": {"unique_packets", "protocol_mode", "seed", "randomize_fields"},
    },
    "Random Traffic 5000 Loss": {
        "subtitle": "Long randomized traffic stress run with deterministic loss injection.",
        "fields": {"packet_count", "loss_percent", "seed"},
    },
    "Long Program With Packet Loss": {
        "subtitle": "Longer BPF program with packet loss during execution.",
        "fields": set(),
    },
    "Ingress Drop Model": {
        "subtitle": "Ingress-style drop reasons before packets enter BPF.",
        "fields": set(),
    },
}


class BpfVerificationWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(REPO_ROOT))
        self.process.readyReadStandardOutput.connect(self._append_stdout)
        self.process.readyReadStandardError.connect(self._append_stderr)
        self.process.finished.connect(self._process_finished)

        self.setWindowTitle("BPF Verification UI")
        self.resize(1400, 900)
        self._field_rows: dict[str, tuple[QLabel, QWidget]] = {}
        self._build_ui()
        self._refresh_reports()
        self._update_command_preview()
        self._update_visible_fields()
        self._apply_styles()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(10)

        root_layout.addWidget(self._build_header())
        root_layout.addWidget(self._build_main_panel(), 1)
        self.setCentralWidget(root)

    def _build_header(self) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)

        title_box = QVBoxLayout()
        title = QLabel("BPF Verification Console")
        title.setObjectName("windowTitleLabel")
        subtitle = QLabel("Configure traffic, launch pytest-based runs, and inspect generated artifacts.")
        subtitle.setObjectName("windowSubtitleLabel")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box, 1)

        self.test_badge = QLabel("")
        self.test_badge.setObjectName("testBadge")
        self.test_badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.test_badge, 0)
        return header

    def _build_main_panel(self) -> QWidget:
        panel = QWidget()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self._build_left_panel(), 0)
        layout.addWidget(self._build_right_panel(), 1)
        return panel

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(self._build_run_group())
        layout.addWidget(self._build_generation_group())
        layout.addStretch(1)

        return panel

    def _build_run_group(self) -> QWidget:
        shell = QWidget()
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(10)

        group = QGroupBox("Test Configuration")
        layout = QFormLayout(group)
        layout.setLabelAlignment(Qt.AlignRight)
        layout.setFormAlignment(Qt.AlignTop)
        layout.setSpacing(8)

        self.test_combo = QComboBox()
        self.test_combo.addItems(TEST_OPTIONS.keys())
        self.test_combo.currentTextChanged.connect(self._on_test_changed)
        self.test_combo.setToolTip("Select which verification scenario to run.")
        self._add_form_row(layout, "test", "Test", self.test_combo)

        self.packet_count_spin = QSpinBox()
        self.packet_count_spin.setRange(1, 100000)
        self.packet_count_spin.setValue(1000)
        self.packet_count_spin.valueChanged.connect(self._update_command_preview)
        self.packet_count_spin.setToolTip("Total number of packet events to run in long random-traffic tests.")
        self._add_form_row(layout, "packet_count", "Packet Count", self.packet_count_spin)

        self.unique_packets_spin = QSpinBox()
        self.unique_packets_spin.setRange(1, 100000)
        self.unique_packets_spin.setValue(40)
        self.unique_packets_spin.valueChanged.connect(self._update_command_preview)
        self.unique_packets_spin.setToolTip(
            "Number of distinct generated packets in configurable/golden-model flows."
        )
        self._add_form_row(layout, "unique_packets", "Unique Packets", self.unique_packets_spin)

        self.loss_percent_spin = QSpinBox()
        self.loss_percent_spin.setRange(0, 100)
        self.loss_percent_spin.setValue(10)
        self.loss_percent_spin.valueChanged.connect(self._update_command_preview)
        self.loss_percent_spin.setToolTip("Percentage of packets selected for packet-loss injection.")
        self._add_form_row(layout, "loss_percent", "Loss Percent", self.loss_percent_spin)

        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(PROTOCOL_MODE_OPTIONS.keys())
        self.protocol_combo.setCurrentText("TCP + UDP")
        self.protocol_combo.currentTextChanged.connect(self._update_command_preview)
        self.protocol_combo.setToolTip("Choose which protocol mix the packet generator should create.")
        self._add_form_row(layout, "protocol_mode", "Protocols", self.protocol_combo)

        self.error_level_combo = QComboBox()
        self.error_level_combo.addItems(ERROR_LEVEL_OPTIONS.keys())
        self.error_level_combo.setCurrentText("CRC Errors + Packet Loss")
        self.error_level_combo.currentTextChanged.connect(self._update_command_preview)
        self.error_level_combo.setToolTip("Select whether to inject only loss pulses or also ingress-style CRC errors.")
        self._add_form_row(layout, "error_level", "Error Level", self.error_level_combo)

        self.seed_edit = QLineEdit("0x1234")
        self.seed_edit.textChanged.connect(self._update_command_preview)
        self.seed_edit.setToolTip(
            "Deterministic random seed for packet generation and loss scheduling. Same seed + same params => same scenario."
        )
        self._add_form_row(layout, "seed", "Seed", self.seed_edit)

        self.run_id_edit = QLineEdit("")
        self.run_id_edit.setPlaceholderText("Optional run label")
        self.run_id_edit.textChanged.connect(self._update_command_preview)
        self.run_id_edit.setToolTip("Optional artifact suffix so reports and waveforms are easier to identify later.")
        self._add_form_row(layout, "run_id", "Run ID", self.run_id_edit)

        self.randomize_fields_edit = QLineEdit("")
        self.randomize_fields_edit.setPlaceholderText("ttl,dscp_ecn,payload_len,payload_bytes,tcp_flags")
        self.randomize_fields_edit.textChanged.connect(self._update_command_preview)
        self.randomize_fields_edit.setToolTip(
            "Comma-separated packet fields to randomize deterministically. "
            "Useful fields: length, payload_len, payload_bytes, ttl, dscp_ecn, src_ip, dst_ip, "
            "identification, flags_fragment, src_port, seq, ack, tcp_flags, tcp_window, ip_protocol."
        )
        self._add_form_row(layout, "randomize_fields", "Randomize Fields", self.randomize_fields_edit)

        shell_layout.addWidget(group)

        runtime_group = QGroupBox("Artifacts And Runtime")
        runtime_layout = QVBoxLayout(runtime_group)
        runtime_layout.setSpacing(6)

        self.reports_check = QCheckBox("Generate Reports")
        self.reports_check.setChecked(True)
        self.reports_check.stateChanged.connect(self._update_command_preview)
        self.reports_check.setToolTip("Write CSV and Markdown report artifacts into the reports directory.")
        runtime_layout.addWidget(self.reports_check)

        self.waveform_check = QCheckBox("Generate Main Waveform")
        self.waveform_check.setChecked(True)
        self.waveform_check.stateChanged.connect(self._update_command_preview)
        self.waveform_check.setToolTip("Generate the main VCD waveform for this run.")
        runtime_layout.addWidget(self.waveform_check)

        self.full_artifacts_check = QCheckBox("Keep Probe Artifacts")
        self.full_artifacts_check.setChecked(False)
        self.full_artifacts_check.stateChanged.connect(self._update_command_preview)
        self.full_artifacts_check.setToolTip(
            "Keep extra probe waveforms/reports for tests that do offset discovery. Usually not needed for normal runs."
        )
        runtime_layout.addWidget(self.full_artifacts_check)

        shell_layout.addWidget(runtime_group)

        self.run_button = QPushButton("Start")
        self.run_button.setObjectName("startButton")
        self.run_button.clicked.connect(self._run_selected_test)
        self.run_button.setToolTip("Launch the selected pytest command.")
        shell_layout.addWidget(self.run_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.clicked.connect(self._stop_process)
        self.stop_button.setEnabled(False)
        self.stop_button.setToolTip("Stop the active pytest process.")
        shell_layout.addWidget(self.stop_button)

        return shell

    def _build_generation_group(self) -> QWidget:
        group = QGroupBox("Packet Generator")
        layout = QGridLayout(group)
        layout.setContentsMargins(10, 14, 10, 10)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)

        self.generator_limit_spin = QSpinBox()
        self.generator_limit_spin.setRange(1, 100000)
        self.generator_limit_spin.setValue(10)
        self.generator_limit_spin.setToolTip("How many generated packets to show in the generator preview command.")
        layout.addWidget(QLabel("Show Limit"), 0, 0)
        layout.addWidget(self.generator_limit_spin, 0, 1)

        self.generator_button = QPushButton("Preview Generated Packets")
        self.generator_button.clicked.connect(self._show_generator_command)
        self.generator_button.setToolTip("Show the standalone packet-generator command for the current parameters.")
        layout.addWidget(self.generator_button, 1, 0, 1, 2)

        return group

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        command_group = QGroupBox("Command Preview")
        command_layout = QVBoxLayout(command_group)
        self.command_preview = QPlainTextEdit()
        self.command_preview.setReadOnly(True)
        self.command_preview.setMaximumHeight(110)
        command_layout.addWidget(self.command_preview)
        layout.addWidget(command_group, 0)

        self.activity_tabs = QTabWidget()

        activity_page = QWidget()
        output_layout = QVBoxLayout(activity_page)
        output_layout.setContentsMargins(10, 10, 10, 10)
        output_layout.setSpacing(8)

        self.output_text = QPlainTextEdit()
        self.output_text.setReadOnly(True)

        output_actions = QHBoxLayout()
        output_actions.addStretch(1)
        clear_button = QPushButton("Clear Logs")
        clear_button.clicked.connect(self.output_text.clear)
        output_actions.addWidget(clear_button)
        output_layout.addLayout(output_actions)
        output_layout.addWidget(self.output_text)
        self.activity_tabs.addTab(activity_page, "Activity")

        artifacts_page = QWidget()
        artifacts_layout = QVBoxLayout(artifacts_page)
        artifacts_layout.setContentsMargins(10, 10, 10, 10)
        artifacts_layout.setSpacing(8)

        artifact_actions = QHBoxLayout()
        artifact_actions.addStretch(1)
        self.refresh_reports_button = QPushButton("Refresh Reports")
        self.refresh_reports_button.clicked.connect(self._refresh_reports)
        self.refresh_reports_button.setToolTip("Refresh the artifact list from the reports directory.")
        artifact_actions.addWidget(self.refresh_reports_button)
        artifacts_layout.addLayout(artifact_actions)

        self.reports_list = QListWidget()
        self.reports_list.itemDoubleClicked.connect(self._open_report_path_hint)
        artifacts_layout.addWidget(self.reports_list)
        self.activity_tabs.addTab(artifacts_page, "Artifacts")

        layout.addWidget(self.activity_tabs, 1)

        return panel

    def _add_form_row(self, layout: QFormLayout, field_key: str, label_text: str, widget: QWidget) -> None:
        label = QLabel(label_text)
        layout.addRow(label, widget)
        self._field_rows[field_key] = (label, widget)

    def _selected_test_path(self) -> str:
        return TEST_OPTIONS[self.test_combo.currentText()]

    def _command_parts(self) -> list[str]:
        parts = ["python", "-m", "pytest", self._selected_test_path(), "-s"]

        if self.reports_check.isChecked():
            parts.append("--bpf-reports")
        if self.waveform_check.isChecked():
            parts.append("--bpf-waveform")
        if self.full_artifacts_check.isChecked():
            parts.append("--bpf-full-artifacts")

        seed_value = self.seed_edit.text().strip() or "0x1234"
        run_id = self.run_id_edit.text().strip()
        randomize_fields = self.randomize_fields_edit.text().strip()

        test_path = self._selected_test_path()
        if test_path.endswith("test_bpf_env_random_traffic_5000_loss.py"):
            parts.extend(
                [
                    "--bpf-packet-count",
                    str(self.packet_count_spin.value()),
                    "--bpf-packet-loss-percent",
                    str(self.loss_percent_spin.value()),
                    "--bpf-packet-rng-seed",
                    seed_value,
                ]
            )
        elif test_path.endswith("test_bpf_env_configurable_traffic.py"):
            parts.extend(
                [
                    "--bpf-unique-packets",
                    str(self.unique_packets_spin.value()),
                    "--bpf-protocol-mode",
                    str(PROTOCOL_MODE_OPTIONS[self.protocol_combo.currentText()]),
                    "--bpf-error-level",
                    str(ERROR_LEVEL_OPTIONS[self.error_level_combo.currentText()]),
                    "--bpf-packet-rng-seed",
                    seed_value,
                ]
            )
        elif test_path.endswith("test_bpf_env_packet_loss_golden_model.py"):
            parts.extend(
                [
                    "--bpf-unique-packets",
                    str(self.unique_packets_spin.value()),
                    "--bpf-protocol-mode",
                    str(PROTOCOL_MODE_OPTIONS[self.protocol_combo.currentText()]),
                    "--bpf-packet-rng-seed",
                    seed_value,
                ]
            )

        if randomize_fields:
            parts.extend(["--bpf-randomize-fields", randomize_fields])

        if run_id:
            parts.extend(["--bpf-run-id", run_id])

        return parts

    def _update_command_preview(self) -> None:
        self.command_preview.setPlainText(" ".join(self._command_parts()))

    def _on_test_changed(self) -> None:
        self._update_visible_fields()
        self._update_command_preview()

    def _update_visible_fields(self) -> None:
        test_name = self.test_combo.currentText()
        metadata = TEST_METADATA[test_name]
        visible_fields = metadata["fields"] | {"test", "run_id"}

        for field_key, (label, widget) in self._field_rows.items():
            visible = field_key in visible_fields
            label.setVisible(visible)
            widget.setVisible(visible)

        self.generator_button.setEnabled("unique_packets" in metadata["fields"])
        self.generator_limit_spin.setEnabled("unique_packets" in metadata["fields"])
        self.test_badge.setText(metadata["subtitle"])

    def _run_selected_test(self) -> None:
        if self.process.state() != QProcess.NotRunning:
            QMessageBox.warning(self, "Run In Progress", "A test run is already active.")
            return

        parts = self._command_parts()
        self.output_text.clear()
        self.output_text.appendPlainText(f"$ {' '.join(parts)}\n")

        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.process.start(parts[0], parts[1:])

    def _stop_process(self) -> None:
        if self.process.state() == QProcess.NotRunning:
            return
        self.process.kill()

    def _append_stdout(self) -> None:
        text = bytes(self.process.readAllStandardOutput()).decode(errors="replace")
        self.output_text.appendPlainText(text.rstrip("\n"))

    def _append_stderr(self) -> None:
        text = bytes(self.process.readAllStandardError()).decode(errors="replace")
        self.output_text.appendPlainText(text.rstrip("\n"))

    def _process_finished(self) -> None:
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._refresh_reports()

    def _generator_command_parts(self) -> list[str]:
        seed_value = self.seed_edit.text().strip() or "0x1234"
        parts = [
            "python",
            "-m",
            "tests.bpf_env.packet_generator",
            "--unique-packets",
            str(self.unique_packets_spin.value()),
            "--protocol-mode",
            str(PROTOCOL_MODE_OPTIONS[self.protocol_combo.currentText()]),
            "--error-level",
            str(ERROR_LEVEL_OPTIONS[self.error_level_combo.currentText()]),
            "--seed",
            seed_value,
            "--show-limit",
            str(self.generator_limit_spin.value()),
        ]
        randomize_fields = self.randomize_fields_edit.text().strip()
        if randomize_fields:
            parts.extend(["--randomize-fields", randomize_fields])
        return parts

    def _show_generator_command(self) -> None:
        self.activity_tabs.setCurrentIndex(0)
        self.output_text.appendPlainText(f"$ {' '.join(self._generator_command_parts())}")

    def _refresh_reports(self) -> None:
        self.reports_list.clear()
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        artifacts = sorted(REPORTS_DIR.glob("*"), key=lambda path: path.stat().st_mtime, reverse=True)
        for artifact in artifacts[:200]:
            item = QListWidgetItem(artifact.name)
            item.setToolTip(str(artifact))
            self.reports_list.addItem(item)

    def _open_report_path_hint(self, item: QListWidgetItem) -> None:
        QMessageBox.information(self, "Artifact Path", item.toolTip())

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f3f4f6;
                color: #202225;
                font-size: 12px;
            }
            QGroupBox {
                border: 1px solid #cfd6de;
                border-radius: 4px;
                margin-top: 10px;
                background: #fbfcfd;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QListWidget, QTabWidget::pane {
                background: white;
                border: 1px solid #c8cfd8;
                border-radius: 3px;
            }
            QPlainTextEdit, QListWidget {
                selection-background-color: #d6e8ff;
            }
            QPushButton {
                background: #eceff3;
                border: 1px solid #c3cad3;
                border-radius: 3px;
                padding: 6px 10px;
            }
            QPushButton:hover {
                background: #e2e7ed;
            }
            QPushButton#startButton {
                background: #5aaa5a;
                color: white;
                font-size: 15px;
                font-weight: 700;
                min-height: 38px;
            }
            QPushButton#startButton:hover {
                background: #499a49;
            }
            QPushButton#stopButton {
                background: #ef6b6b;
                color: white;
                font-size: 15px;
                font-weight: 700;
                min-height: 38px;
            }
            QPushButton#stopButton:hover {
                background: #df5959;
            }
            QLabel#windowTitleLabel {
                font-size: 24px;
                font-weight: 700;
            }
            QLabel#windowSubtitleLabel {
                color: #5f6b7a;
            }
            QLabel#testBadge {
                background: #1f3b5b;
                color: white;
                border-radius: 6px;
                padding: 10px 14px;
                min-width: 340px;
                max-width: 420px;
            }
            QTabBar::tab {
                background: #eceff3;
                border: 1px solid #c8cfd8;
                padding: 8px 12px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom-color: white;
            }
            """
        )


def main() -> int:
    app = QApplication(sys.argv)
    window = BpfVerificationWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
