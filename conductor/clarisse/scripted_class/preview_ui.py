"""Provide a window in which to display a preview submission.

This is required because Clarisse's attribute editor doesn't allow
custom UI to be embedded.
"""

import json

import ix
 
C_LEFT = ix.api.GuiWidget.CONSTRAINT_LEFT
C_TOP = ix.api.GuiWidget.CONSTRAINT_TOP
C_RIGHT = ix.api.GuiWidget.CONSTRAINT_RIGHT
C_BOTTOM = ix.api.GuiWidget.CONSTRAINT_BOTTOM

BTN_HEIGHT = 22
BTN_WIDTH = 100
WINDOW_LEFT = 600
WINDOW_TOP = 200
HEIGHT = 500
WIDTH = 800
PADDING = 5

SYMBOL_BUT_WIDTH = 30
CHECKBOX_WIDTH = 50

BOTTOM_BUT_WIDTH = WIDTH / 3


class PreviewWindow(ix.api.GuiWindow):
    """The entire window.

    Holds the panel plus buttons to Submit or Cancel and so on.
    """

    def __init__(self, submission):
        window_height = HEIGHT + BTN_HEIGHT

        super(PreviewWindow, self).__init__(ix.application.get_event_window(),
                                            WINDOW_LEFT,
                                            WINDOW_TOP,
                                            WIDTH,
                                            window_height,
                                            "Submission Preview")

        self.submission = submission
        self.text_widget = ix.api.GuiTextEdit(self, 0, 0, WIDTH, HEIGHT)
        self.text_widget.set_constraints(C_LEFT, C_TOP, C_RIGHT, C_BOTTOM)
        self.close_but = ix.api.GuiPushButton(
            self, 0, HEIGHT, BOTTOM_BUT_WIDTH, BTN_HEIGHT, "Close")
        self.close_but.set_constraints(C_LEFT, C_BOTTOM, C_LEFT, C_BOTTOM)
        self.connect(
            self.close_but,
            'EVT_ID_PUSH_BUTTON_CLICK',
            self.on_close_but)

        self.apply_but = ix.api.GuiPushButton(
            self,
            BOTTOM_BUT_WIDTH,
            HEIGHT,
            BOTTOM_BUT_WIDTH,
            BTN_HEIGHT,
            "Submit")
        self.apply_but.set_constraints(C_LEFT, C_BOTTOM, C_RIGHT, C_BOTTOM)
        self.connect(
            self.apply_but,
            'EVT_ID_PUSH_BUTTON_CLICK',
            self.on_apply_but)

        self.go_but = ix.api.GuiPushButton(
            self,
            (WIDTH - BOTTOM_BUT_WIDTH),
            HEIGHT,
            BOTTOM_BUT_WIDTH,
            BTN_HEIGHT,
            "Submit and close")
        self.go_but.set_constraints(C_RIGHT, C_BOTTOM, C_RIGHT, C_BOTTOM)
        self.connect(self.go_but, 'EVT_ID_PUSH_BUTTON_CLICK', self.on_go_but)

        self._populate()

    def _populate(self):
        """Put the submission args in the window."""
        submission_args = self.submission.get_args()
        json_jobs = json.dumps(submission_args, indent=3, sort_keys=True)
        self.text_widget.set_text(json_jobs)

    def on_add_but(self, sender, eventid):
        self.panel.add_entries({})

    def on_close_but(self, sender, eventid):
        """Hide only.

        Don't destroy because hide will cause the event loop to end and
        destroy will kick in afterwards.
        """
        self.hide()

    def on_apply_but(self, sender, eventid):
        """Submit and keep the window visible."""
        self.submission.submit()

    def on_go_but(self, sender, eventid):
        """Submit and hide(destroy) the window."""
        self.submission.submit()
        self.hide()


def build(submission):
    """Show the window.

    Populate it with submission args for each job. Listen for events
    until the window is hidden.
    """
    win = PreviewWindow(submission)

    win.show_modal()
    while win.is_shown():
        ix.application.check_for_events()

    # win.destroy is recommended but makes Clarisse crash
    # when saving the scene
    # win.destroy()
