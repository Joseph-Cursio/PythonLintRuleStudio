import unittest
import customtkinter as ctk
from unittest.mock import MagicMock
from ruff_studio.ui.tooltip import Tooltip


class TestTooltip(unittest.TestCase):
    def setUp(self):
        self.root = ctk.CTk()
        self.button = ctk.CTkButton(self.root, text="Test")
        self.tooltip_text = "Helpful info"
        self.tooltip = Tooltip(self.button, self.tooltip_text)

    def tearDown(self):
        self.root.destroy()

    def test_init(self):
        self.assertEqual(self.tooltip.text, self.tooltip_text)
        self.assertIsNone(self.tooltip.tooltip_window)

    def test_show_hide_tooltip(self):
        # Mock winfo methods to avoid Tcl errors in some environments
        self.button.winfo_rootx = MagicMock(return_value=100)
        self.button.winfo_rooty = MagicMock(return_value=100)
        self.button.bbox = MagicMock(return_value=(0, 0, 10, 10))

        # Simulate <Enter> event
        event = MagicMock()
        self.tooltip.show_tooltip(event)

        self.assertIsNotNone(self.tooltip.tooltip_window)
        # Check if it's a CTkToplevel
        self.assertIsInstance(self.tooltip.tooltip_window, ctk.CTkToplevel)

        # Simulate <Leave> event
        self.tooltip.hide_tooltip(event)
        self.assertIsNone(self.tooltip.tooltip_window)

    def test_hide_tooltip_no_window(self):
        # Should not raise error if tooltip_window is None
        self.tooltip.tooltip_window = None
        self.tooltip.hide_tooltip(None)
        self.assertIsNone(self.tooltip.tooltip_window)


if __name__ == "__main__":
    unittest.main()
