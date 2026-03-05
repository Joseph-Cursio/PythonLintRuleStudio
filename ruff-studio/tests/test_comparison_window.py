import unittest
import customtkinter as ctk
from unittest.mock import patch
from ruff_studio.ui.comparison_window import ProfileComparisonWindow


class TestComparisonWindow(unittest.TestCase):
    def setUp(self):
        self.root = ctk.CTk()
        # Mock profile_manager to avoid loading real files
        self.profiles = ["p1", "p2", "p3"]
        self.p1_data = {
            "profile": {"rules": {"ruff": {"select": ["E"], "ignore": ["F"]}}}
        }
        self.p2_data = {
            "profile": {"rules": {"ruff": {"select": ["F"], "ignore": ["E"]}}}
        }

        self.get_profiles_patch = patch(
            "ruff_studio.profile_manager.get_built_in_profiles",
            return_value=self.profiles,
        )
        self.load_profile_patch = patch(
            "ruff_studio.profile_manager.load_profile",
            side_effect=[self.p1_data, self.p2_data, self.p1_data],
        )

        self.get_profiles_patch.start()
        self.load_profile_patch.start()

        self.win = ProfileComparisonWindow(self.root)

    def tearDown(self):
        self.get_profiles_patch.stop()
        self.load_profile_patch.stop()
        self.win.destroy()
        self.root.destroy()

    def test_init(self):
        self.assertEqual(self.win.profile1_var.get(), "p1")
        self.assertEqual(self.win.profile2_var.get(), "p2")

    def test_compare_same_profile(self):
        self.win.profile1_var.set("p1")
        self.win.profile2_var.set("p1")
        self.win.do_comparison()

        report = self.win.results_textbox.get("1.0", "end")
        self.assertIn("Please select two different profiles", report)

    def test_compare_different_profiles(self):
        self.win.profile1_var.set("p1")
        self.win.profile2_var.set("p2")

        diff = {
            "select_only_in_1": ["E101"],
            "select_only_in_2": ["F401"],
            "ignore_only_in_1": ["W001"],
            "ignore_only_in_2": ["C001"],
            "common_select": ["E501"],
            "common_ignore": ["F841"],
        }

        with patch("ruff_studio.profile_manager.compare_profiles", return_value=diff):
            self.win.do_comparison()
            report = self.win.results_textbox.get("1.0", "end")
            self.assertIn("Comparing 'p1' vs 'p2':", report)
            self.assertIn("Only in 'p1':\n  - E101", report)
            self.assertIn("Only in 'p2':\n  - F401", report)
            self.assertIn("Commonly Selected:\n  - E501", report)

    def test_empty_diff_sections(self):
        """Tests that sections are omitted if there are no differences."""
        self.win.profile1_var.set("p1")
        self.win.profile2_var.set("p2")

        diff = {
            "select_only_in_1": [],
            "select_only_in_2": [],
            "ignore_only_in_1": [],
            "ignore_only_in_2": [],
            "common_select": ["E501"],
            "common_ignore": [],
        }

        with patch("ruff_studio.profile_manager.compare_profiles", return_value=diff):
            self.win.do_comparison()
            report = self.win.results_textbox.get("1.0", "end")
            self.assertIn("Commonly Selected:\n  - E501", report)
            # Ensure "Only in 'p1'" is not there if empty
            self.assertNotIn("Only in 'p1':", report)


if __name__ == "__main__":
    unittest.main()
