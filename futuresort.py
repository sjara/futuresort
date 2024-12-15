"""
A GUI for scheduling Kilosort to run at a future time.
"""

import sys
import time
import json
import os
from datetime import datetime, timedelta
from qtpy.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                            QDateTimeEdit, QLineEdit, QSpacerItem, QSizePolicy)
from qtpy.QtCore import QTimer, Qt, QDateTime, QObject, Signal, QThread
from qtpy.QtGui import QFont
import kilosort

# Configuration import
try:
    import config
except ImportError:
    print("No configuration file found. Using default settings.")
    
    # Fallback configuration if config.py is missing
    class config:
        DEBUG_MODE = False
        DEFAULT_DATA_FILE = "debug_data.txt"
        DEFAULT_RESULTS_DIR = "debug_results"
        DEFAULT_PROBE_FILE = "debug_probe.json"
        DEFAULT_SCHEDULE_DELAY = 5
        KILOSORT_SETTINGS = {}

# Global debug variables
DEBUG_MODE = config.DEBUG_MODE
DEBUG_DATA_FILE = config.DEFAULT_DATA_FILE
DEBUG_RESULTS_DIR = config.DEFAULT_RESULTS_DIR
DEBUG_PROBE_FILE = config.DEFAULT_PROBE_FILE
DEBUG_SCHEDULE_DELAY = config.DEFAULT_SCHEDULE_DELAY
DEBUG_SCHEDULE_TIME = datetime.now() + timedelta(seconds=DEBUG_SCHEDULE_DELAY)

# Modify run_kilosort to use config settings
def run_kilosort(data_file, results_dir, probe_file):
    probe = kilosort.io.load_probe(probe_file)
    
    # Use settings from config, with ability to override
    settings = config.KILOSORT_SETTINGS.copy()
    settings['n_chan_bin'] = probe['n_chan']
    
    ops, st, clu, tF, Wall, similar_templates, is_ref, est_contam_rate, kept_spikes = \
        kilosort.run_kilosort(settings=settings, filename=data_file,
                              probe=probe, results_dir=results_dir)
    return "Kilosort finished"


class WorkerSignals(QObject):
    output = Signal(str)
    finished = Signal()


class SchedulerThread(QThread):
    def __init__(self, scheduled_time, data_file, probe_file, results_dir):
        super().__init__()
        self.scheduled_time = scheduled_time
        self.data_file = data_file
        self.probe_file = probe_file
        self.results_dir = results_dir
        self.running = True
        self.signals = WorkerSignals()

    def run(self):
        while self.running:
            now = datetime.now()
            if now >= self.scheduled_time:
                try:
                    print("Starting execution...\n")
                    # Run kilosort with the provided parameters
                    result = run_kilosort(self.data_file, self.results_dir, self.probe_file)
                    print(f"Execution completed: {result}\n")
                except Exception as e:
                    print(f"Error during execution: {str(e)}")
                
                self.signals.finished.emit()
                break
            time.sleep(1)

    def stop(self):
        self.running = False


class SchedulerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FutureSort: Kilosort scheduler")
        self.scheduled_job = None
        self.running = False
        
        # Initialize debug values if in debug mode
        if DEBUG_MODE:
            self.data_file = DEBUG_DATA_FILE
            self.results_dir = DEBUG_RESULTS_DIR
            self.probe_file = DEBUG_PROBE_FILE
        else:
            self.data_file = None
            self.results_dir = None
            self.probe_file = None
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Create bold font for labels
        bold_font = QFont()
        bold_font.setBold(True)
        
        # Data file selection
        data_layout = QHBoxLayout()
        data_label = QLabel("Data file:")
        data_label.setFont(bold_font)
        self.data_edit = QLineEdit()
        self.data_edit.setReadOnly(True)
        if DEBUG_MODE:
            self.data_edit.setText(self.data_file)
        data_button = QPushButton("Select")
        data_button.setFixedWidth(70)  # Fixed width for all "Select" buttons
        data_button.clicked.connect(self.select_data_file)
        data_layout.addWidget(data_label)
        data_layout.addWidget(self.data_edit)
        data_layout.addWidget(data_button)
        layout.addLayout(data_layout)
        
        # Results folder selection
        results_layout = QHBoxLayout()
        results_label = QLabel("Results folder:")
        results_label.setFont(bold_font)
        self.results_edit = QLineEdit()
        self.results_edit.setReadOnly(True)
        if DEBUG_MODE:
            self.results_edit.setText(self.results_dir)
        results_button = QPushButton("Select")
        results_button.setFixedWidth(70)
        results_button.clicked.connect(self.select_results_dir)
        results_layout.addWidget(results_label)
        results_layout.addWidget(self.results_edit)
        results_layout.addWidget(results_button)
        layout.addLayout(results_layout)
        
        # Probe file selection
        probe_layout = QHBoxLayout()
        probe_label = QLabel("Probe file:")
        probe_label.setFont(bold_font)
        self.probe_edit = QLineEdit()
        self.probe_edit.setReadOnly(True)
        if DEBUG_MODE:
            self.probe_edit.setText(self.probe_file)
        probe_button = QPushButton("Select")
        probe_button.setFixedWidth(70)
        probe_button.clicked.connect(self.select_probe_file)
        probe_layout.addWidget(probe_label)
        probe_layout.addWidget(self.probe_edit)
        probe_layout.addWidget(probe_button)
        layout.addLayout(probe_layout)
        
        # DateTime selection
        datetime_layout = QHBoxLayout()
        datetime_label = QLabel("Schedule for:")
        datetime_label.setFont(bold_font)
        self.datetime_edit = QDateTimeEdit()
        if DEBUG_MODE:
            debug_time = DEBUG_SCHEDULE_TIME
            self.datetime_edit.setDateTime(debug_time)
        else:
            current_time = QDateTime.currentDateTime()
            self.datetime_edit.setDateTime(current_time)
        # Set the display format to ISO standard format
        self.datetime_edit.setDisplayFormat("yyyy-MM-dd h:mm AP")
        self.datetime_edit.setCalendarPopup(True)
        datetime_layout.addWidget(datetime_label)
        datetime_layout.addWidget(self.datetime_edit)

        # Time preset buttons
        preset_layout = QHBoxLayout()
        
        # Add a horizontal spacer before preset buttons
        datetime_layout.addSpacing(50)  # Add a small spacer
        
        # 5 seconds from now button
        five_sec_button = QPushButton("5s")
        five_sec_button.setToolTip("Set time to 5 seconds from now")
        five_sec_button.clicked.connect(lambda: self.set_scheduled_time(value=5))
        preset_layout.addWidget(five_sec_button)
        
        # 10 PM today button
        ten_pm_button = QPushButton("10 PM")
        ten_pm_button.setToolTip("Set time to 10 PM today")
        ten_pm_button.clicked.connect(lambda: self.set_scheduled_time(time_type='absolute', value=22))
        preset_layout.addWidget(ten_pm_button)
        
        # 2 AM tomorrow button
        two_am_button = QPushButton("2 AM")
        two_am_button.setToolTip("Set time to 2 AM tomorrow")
        two_am_button.clicked.connect(lambda: self.set_scheduled_time(time_type='absolute', value=2))
        preset_layout.addWidget(two_am_button)
        
        datetime_layout.addLayout(preset_layout)

        # Add a spacer to push everything to the left
        spacer = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        datetime_layout.addItem(spacer) 
        layout.addLayout(datetime_layout)
        # Countdown label with spacing
        self.countdown_label = QLabel("Not scheduled")
        self.countdown_label.setAlignment(Qt.AlignCenter)
        self.countdown_label.setStyleSheet("font-size: 20px;")  # Make the label bigger
        layout.addSpacing(20)  # Add spacing above the countdown label
        layout.addWidget(self.countdown_label)
        layout.addSpacing(20)  # Add spacing below the countdown label
        # Control buttons
        button_layout = QHBoxLayout()
        self.schedule_button = QPushButton("Schedule")
        self.schedule_button.setFixedHeight(50)  # Make the button taller
        self.schedule_button.clicked.connect(self.schedule_command)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFixedHeight(50)  # Make the button taller
        self.cancel_button.clicked.connect(self.cancel_schedule)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.schedule_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        # Setup timer for countdown
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_countdown)
        self.timer.start(1000)  # Update every second
        
        self.setMinimumSize(600, 200)
        
        # Create worker signals
        self.worker_signals = WorkerSignals()
        self.worker_signals.output.connect(self.append_output)
        self.worker_signals.finished.connect(self.on_execution_finished)
    def select_data_file(self):
        # Use the directory from the default data file if it exists
        default_dir = os.path.dirname(config.DEFAULT_DATA_FILE) if config.DEFAULT_DATA_FILE else ''
        
        file_name, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Data File", 
            directory=default_dir,  # Set the default directory
            filter="Data Files (*.dat *.bin);;All Files (*)"
        )
        if file_name:
            self.data_file = file_name
            self.data_edit.setText(file_name)
    
    def select_results_dir(self):
        # Use the default results directory if it exists
        default_dir = config.DEFAULT_RESULTS_DIR if config.DEFAULT_RESULTS_DIR else ''
        
        folder_name = QFileDialog.getExistingDirectory(
            self, 
            "Select Results Folder",
            directory=default_dir  # Set the default directory
        )
        if folder_name:
            self.results_dir = folder_name
            self.results_edit.setText(folder_name)
    
    def select_probe_file(self):
        # Use the directory from the default probe file if it exists
        default_dir = os.path.dirname(config.DEFAULT_PROBE_FILE) if config.DEFAULT_PROBE_FILE else ''
        
        file_name, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Probe File", 
            directory=default_dir,  # Set the default directory
            filter="Probe Files (*.json);;All Files (*)"
        )
        if file_name:
            self.probe_file = file_name
            self.probe_edit.setText(file_name)
    
    def schedule_command(self):
        if not all([self.data_file, self.results_dir, self.probe_file]):
            return
        
        self.scheduled_time = self.datetime_edit.dateTime().toPyDateTime()
        if self.scheduled_time <= datetime.now():
            self.countdown_label.setText("Scheduled time has passed")
            self.schedule_button.setStyleSheet("")  # Reset button style
            return
        
        # Create and start the scheduler thread
        self.scheduler_thread = SchedulerThread(
            self.scheduled_time,
            self.data_file, 
            self.probe_file, 
            self.results_dir
        )
        self.scheduler_thread.signals.finished.connect(self.on_execution_finished)
        self.scheduler_thread.start()
        
        self.schedule_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.schedule_button.setStyleSheet("background-color: red; color: black;")
        self.schedule_button.setText("Scheduled")

    def cancel_schedule(self):
        if hasattr(self, 'scheduler_thread'):
            self.scheduler_thread.stop()
            self.scheduler_thread.wait()  # Wait for the thread to finish
        self.countdown_label.setText("Not scheduled")
        self.schedule_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.schedule_button.setStyleSheet("")
        self.schedule_button.setText("Schedule")
        print("Scheduled task cancelled")

    def update_countdown(self):
        if not hasattr(self, 'scheduler_thread') or not self.scheduler_thread.isRunning():
            return
        
        scheduled_time = self.datetime_edit.dateTime().toPyDateTime()
        now = datetime.now()
        
        if scheduled_time > now:
            time_diff = scheduled_time - now
            hours, remainder = divmod(time_diff.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.countdown_label.setText(
                f"Time until execution: {time_diff.days}d {hours}h {minutes}m {seconds}s"
            )
        else:
            self.countdown_label.setText("Action has been triggered")

    def append_output(self, text):
        # This method is no longer needed since we are printing directly to stdout
        pass

    def on_execution_finished(self):
        self.running = False
        self.schedule_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.schedule_button.setStyleSheet("")  # Reset button style when finished
        self.schedule_button.setText("Schedule")
        self.countdown_label.setText("Action finished")

    def set_scheduled_time(self, time_type='relative', value=5, unit='seconds'):
        """
        Flexible method to set scheduled time
        
        Args:
            time_type (str): 'relative' or 'absolute'
            value (int): Number of seconds/hours to add, or specific hour (24h format) for absolute time
            unit (str): 'seconds' or 'hours'
        """
        current_time = QDateTime.currentDateTime()
        if time_type == 'relative':
            if unit == 'seconds':
                scheduled_time = current_time.addSecs(value)
            elif unit == 'hours':
                scheduled_time = current_time.addSecs(value * 3600)
            else:
                raise ValueError(f"Unsupported unit: {unit}")
        elif time_type == 'absolute':
            current_date = datetime.now().date()
            if value < 0 or value > 23:
                raise ValueError("Hour must be between 0 and 23")
            # If time is earlier than current time, set to next day
            absolute_time = datetime.combine(current_date, datetime.min.time().replace(hour=value))
            if absolute_time <= datetime.now():
                absolute_time += timedelta(days=1)
            scheduled_time = QDateTime(absolute_time)
        else:
            raise ValueError(f"Unsupported time type: {time_type}")
        self.datetime_edit.setDateTime(scheduled_time)


def main():
    app = QApplication(sys.argv)
    window = SchedulerApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
