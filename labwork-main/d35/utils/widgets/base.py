from PyQt5 import QtCore, QtGui, QtWidgets


class QLedLabel(QtWidgets.QLabel):
    SIZE = 20;
    green = "color: white;border-radius: %d ;background-color: qlineargradient(spread:pad, x1:0.145, y1:0.16, x2:1, y2:1, stop:0 rgba(20, 252, 7, 255), stop:1 rgba(25, 134, 5, 255));" % (SIZE/2)
    red = "color: white;border-radius: %d ;background-color: qlineargradient(spread:pad, x1:0.145, y1:0.16, x2:0.92, y2:0.988636, stop:0 rgba(255, 12, 12, 255), stop:0.869347 rgba(103, 0, 0, 255));" % (SIZE/2)
    orange = "color: white;border-radius: %d ;background-color: qlineargradient(spread:pad, x1:0.232, y1:0.272, x2:0.98, y2:0.959773, stop:0 rgba(255, 113, 4, 255), stop:1 rgba(91, 41, 7, 255))" % (SIZE/2)
    blue = "color: white;border-radius: %d ;background-color: qlineargradient(spread:pad, x1:0.04, y1:0.0565909, x2:0.799, y2:0.795, stop:0 rgba(203, 220, 255, 255), stop:0.41206 rgba(0, 115, 255, 255), stop:1 rgba(0, 49, 109, 255));" % (SIZE/2)

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)

        self.setState(0)
        self.setFixedSize(QLedLabel.SIZE,QLedLabel.SIZE)

    def setState(self, state):
        if state == 0: # Green
            self.setStyleSheet(QLedLabel.green)
            return
        if state == 1: # Orange
            self.setStyleSheet(QLedLabel.orange)
            return
        if state == 2: # Blue
            self.setStyleSheet(QLedLabel.blue)
            return
        self.setStyleSheet(QLedLabel.red)




class LabviewQDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    def textFromValue(self, value):
        # show + sign for positive values
        text = super().textFromValue(value)
        if value >= 0:
            text = "+" + text
        return text

    def stepBy(self, steps):
        cursor_position = self.lineEdit().cursorPosition()
        # number of characters before the decimal separator including +/- sign
        n_chars_before_sep = len(str(abs(int(self.value())))) + 1
        if cursor_position == 0:
            # set the cursor right of the +/- sign
            self.lineEdit().setCursorPosition(1)
            cursor_position = self.lineEdit().cursorPosition()
        single_step = 10 ** (n_chars_before_sep - cursor_position)
        # Handle decimal separator. Step should be 0.1 if cursor is at `1.|23` or
        # `1.2|3`.
        if cursor_position >= n_chars_before_sep + 2:
            single_step = 10 * single_step
        # Change single step and perform the step
        self.setSingleStep(single_step)
        super().stepBy(steps)
        # Undo selection of the whole text.
        self.lineEdit().deselect()
        # Handle cases where the number of characters before the decimal separator
        # changes. Step size should remain the same.
        new_n_chars_before_sep = len(str(abs(int(self.value())))) + 1
        if new_n_chars_before_sep < n_chars_before_sep:
            cursor_position -= 1
        elif new_n_chars_before_sep > n_chars_before_sep:
            cursor_position += 1
        self.lineEdit().setCursorPosition(cursor_position)