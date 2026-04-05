from __future__ import annotations

import os
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
    QSplitter,
    QVBoxLayout,
    QWidget,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "reports"

TEST_OPTIONS = {
    "Configurable Traffic": "tests/integration/test_bpf_env_configurable_traffic.py",
    "Packet Loss Golden Model": "tests/integration/test_bpf_env_packet_loss_golden_model.py",
    "Random Traffic 5000 Loss": "tests/integration/test_bpf_env_random_traffic_5000_loss.py",
    "Long Program With Packet Loss": "tests/integration/test_bpf_env_long_program_with_packet_loss.py",
    "Ingress Drop Model": "tests/integration/test_bpf_env_ingress_drop_model.py",
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
        self._build_ui()
        self._refresh_reports()
        self._update_command_preview()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        root_layout.addWidget(splitter)
        self.setCentralWidget(root)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        layout.addWidget(self._build_run_group())
        layout.addWidget(self._build_generation_group())
        layout.addWidget(self._build_artifact_group())
        layout.addStretch(1)

        return panel

    def _build_run_group(self) -> QWidget:
        group = QGroupBox("Run Configuration")
        layout = QFormLayout(group)

        self.test_combo = QComboBox()
        self.test_combo.addItems(TEST_OPTIONS.keys())
        self.test_combo.currentTextChanged.connect(self._update_command_preview)
        layout.addRow("Test", self.test_combo)

        self.packet_count_spin = QSpinBox()
        self.packet_count_spin.setRange(1, 100000)
        self.packet_count_spin.setValue(1000)
        self.packet_count_spin.valueChanged.connect(self._update_command_preview)
        layout.addRow("Packet Count", self.packet_count_spin)

        self.unique_packets_spin = QSpinBox()
        self.unique_packets_spin.setRange(1, 100000)
        self.unique_packets_spin.setValue(40)
        self.unique_packets_spin.valueChanged.connect(self._update_command_preview)
        layout.addRow("Unique Packets", self.unique_packets_spin)

        self.loss_percent_spin = QSpinBox()
        self.loss_percent_spin.setRange(0, 100)
        self.loss_percent_spin.setValue(10)
        self.loss_percent_spin.valueChanged.connect(self._update_command_preview)
        layout.addRow("Loss Percent", self.loss_percent_spin)

        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(PROTOCOL_MODE_OPTIONS.keys())
        self.protocol_combo.setCurrentText("TCP + UDP")
        self.protocol_combo.currentTextChanged.connect(self._update_command_preview)
        layout.addRow("Protocols", self.protocol_combo)

        self.error_level_combo = QComboBox()
        self.error_level_combo.addItems(ERROR_LEVEL_OPTIONS.keys())
        self.error_level_combo.setCurrentText("CRC Errors + Packet Loss")
        self.error_level_combo.currentTextChanged.connect(self._update_command_preview)
        layout.addRow("Error Level", self.error_level_combo)

        self.seed_edit = QLineEdit("0x1234")
        self.seed_edit.textChanged.connect(self._update_command_preview)
        layout.addRow("Seed", self.seed_edit)

        self.run_id_edit = QLineEdit("")
        self.run_id_edit.setPlaceholderText("Optional run label")
        self.run_id_edit.textChanged.connect(self._update_command_preview)
        layout.addRow("Run ID", self.run_id_edit)

        self.reports_check = QCheckBox("Generate Reports")
        self.reports_check.setChecked(True)
        self.reports_check.stateChanged.connect(self._update_command_preview)
        layout.addRow(self.reports_check)

        self.waveform_check = QCheckBox("Generate Main Waveform")
        self.waveform_check.setChecked(True)
        self.waveform_check.stateChanged.connect(self._update_command_preview)
        layout.addRow(self.waveform_check)

        self.full_artifacts_check = QCheckBox("Keep Probe Artifacts")
        self.full_artifacts_check.setChecked(False)
        self.full_artifacts_check.stateChanged.connect(self._update_command_preview)
        layout.addRow(self.full_artifacts_check)

        button_row = QHBoxLayout()
        self.run_button = QPushButton("Run Test")
        self.run_button.clicked.connect(self._run_selected_test)
        button_row.addWidget(self.run_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self._stop_process)
        self.stop_button.setEnabled(False)
        button_row.addWidget(self.stop_button)

        layout.addRow(button_row)

        return group

    def _build_generation_group(self) -> QWidget:
        group = QGroupBox("Packet Generator")
        layout = QGridLayout(group)

        self.generator_limit_spin = QSpinBox()
        self.generator_limit_spin.setRange(1, 100000)
        self.generator_limit_spin.setValue(10)
        layout.addWidget(QLabel("Show Limit"), 0, 0)
        layout.addWidget(self.generator_limit_spin, 0, 1)

        self.generator_button = QPushButton("Preview Generated Packets")
        self.generator_button.clicked.connect(self._show_generator_command)
        layout.addWidget(self.generator_button, 1, 0, 1, 2)

        return group

    def _build_artifact_group(self) -> QWidget:
        group = QGroupBox("Artifacts")
        layout = QVBoxLayout(group)

        self.refresh_reports_button = QPushButton("Refresh Reports")
        self.refresh_reports_button.clicked.connect(self._refresh_reports)
        layout.addWidget(self.refresh_reports_button)

        self.reports_list = QListWidget()
        self.reports_list.itemDoubleClicked.connect(self._open_report_path_hint)
        layout.addWidget(self.reports_list)

        return group

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        command_group = QGroupBox("Command Preview")
        command_layout = QVBoxLayout(command_group)
        self.command_preview = QPlainTextEdit()
        self.command_preview.setReadOnly(True)
        self.command_preview.setMaximumBlockCount(200)
        command_layout.addWidget(self.command_preview)
        layout.addWidget(command_group, 0)

        output_group = QGroupBox("Run Output")
        output_layout = QVBoxLayout(output_group)
        self.output_text = QPlainTextEdit()
        self.output_text.setReadOnly(True)
        output_layout.addWidget(self.output_text)
        layout.addWidget(output_group, 1)

        return panel

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

        if run_id:
            parts.extend(["--bpf-run-id", run_id])

        return parts

    def _update_command_preview(self) -> None:
        self.command_preview.setPlainText(" ".join(self._command_parts()))

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
        return [
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

    def _show_generator_command(self) -> None:
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


def main() -> int:
    app = QApplication(sys.argv)
    window = BpfVerificationWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
