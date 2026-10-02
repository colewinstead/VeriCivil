import unittest
import subprocess
import tempfile
from pathlib import Path

from scripts.classify_release_changes import changed_paths, requires_release
from scripts.validate_release_version import parse_version, release_tags


class ReleaseVersionTests(unittest.TestCase):
    def test_parse_version_accepts_numeric_semver(self):
        self.assertEqual(parse_version("1.2.3"), (1, 2, 3))

    def test_parse_version_rejects_non_release_labels(self):
        with self.assertRaises(ValueError):
            parse_version("1.2")
        with self.assertRaises(ValueError):
            parse_version("1.2.3-beta")

    def test_release_tags_accept_existing_tag_case(self):
        self.assertEqual(
            release_tags(["v1.0.0", "V1.1.0", "other"]),
            {"v1.0.0": (1, 0, 0), "V1.1.0": (1, 1, 0)},
        )

    def test_documentation_changes_do_not_require_release(self):
        self.assertFalse(requires_release(["README.md", "AGENTS.md", "docs/guide.rst", "LICENSE"]))

    def test_application_and_unknown_files_require_release(self):
        for path in ["Super.py", "web/app/page.tsx", "web/package-lock.json", "docs/criteria.json",
                     ".github/workflows/release.yml", "test_release_version.py", "unknown.txt"]:
            with self.subTest(path=path):
                self.assertTrue(requires_release(["README.md", path]))

    def test_git_diff_includes_original_path_when_code_is_renamed_to_documentation(self):
        with tempfile.TemporaryDirectory() as directory:
            def git(*args):
                return subprocess.check_output(
                    ["git", "-C", directory, "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
                    text=True, stderr=subprocess.STDOUT,
                ).strip()

            git("init")
            source = Path(directory) / "app.py"
            source.write_text("example\n", encoding="utf-8")
            git("add", ".")
            git("commit", "-m", "Baseline")
            base = git("rev-parse", "HEAD")
            readme = Path(directory) / "README.md"
            readme.write_text("Documentation\n", encoding="utf-8")
            git("add", ".")
            git("commit", "-m", "Docs")
            docs = git("rev-parse", "HEAD")
            self.assertFalse(requires_release(changed_paths(base, docs, merge_base=True, cwd=directory)))
            source.rename(Path(directory) / "app.md")
            git("add", "-A")
            git("commit", "-m", "Rename code")
            paths = changed_paths(base, "HEAD", cwd=directory)
            self.assertIn("app.py", paths)
            self.assertIn("app.md", paths)
            self.assertTrue(requires_release(paths))
            self.assertTrue(requires_release(changed_paths("0" * 40, base, cwd=directory)))


if __name__ == "__main__":
    unittest.main()
