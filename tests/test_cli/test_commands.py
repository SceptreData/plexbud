"""Tests for CLI commands."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from plexbud.main import app

runner = CliRunner()


class TestCLI:
    def test_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "plexbud" in result.output.lower() or "stats" in result.output.lower()

    def test_stats_help(self) -> None:
        result = runner.invoke(app, ["stats", "--help"])
        assert result.exit_code == 0
        assert "tv" in result.output.lower()
        assert "movies" in result.output.lower()

    def test_delete_help(self) -> None:
        result = runner.invoke(app, ["delete", "--help"])
        assert result.exit_code == 0
        assert "tv" in result.output.lower()
        assert "movie" in result.output.lower()

    def test_stats_tv_mock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PLEXBUD_MOCK", "1")
        result = runner.invoke(app, ["stats", "tv", "--plain"])
        assert result.exit_code == 0
        assert "Breaking Bad" in result.output

    def test_stats_movies_mock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PLEXBUD_MOCK", "1")
        result = runner.invoke(app, ["stats", "movies", "--plain"])
        assert result.exit_code == 0
        assert "Interstellar" in result.output

    def test_no_args_shows_both(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PLEXBUD_MOCK", "1")
        result = runner.invoke(app, ["--plain"])
        assert result.exit_code == 0
        assert "Breaking Bad" in result.output
        assert "Interstellar" in result.output

    def test_delete_bare_prompts_and_launches_tui(self) -> None:
        """'plexbud delete' (no subcommand) prompts for tv/movies, then launches TUI."""
        with patch("plexbud.commands.delete._launch_tui") as mock_tui:
            result = runner.invoke(app, ["delete"], input="tv\n")
            assert result.exit_code == 0
            mock_tui.assert_called_once_with(media_filter="tv")

    def test_delete_tv_no_name_launches_tui(self) -> None:
        """'plexbud delete tv' (no name arg) launches interactive TUI."""
        with patch("plexbud.commands.delete._launch_tui") as mock_tui:
            result = runner.invoke(app, ["delete", "tv"])
            assert result.exit_code == 0
            mock_tui.assert_called_once_with(media_filter="tv")

    def test_delete_movie_no_name_launches_tui(self) -> None:
        """'plexbud delete movie' (no name arg) launches interactive TUI."""
        with patch("plexbud.commands.delete._launch_tui") as mock_tui:
            result = runner.invoke(app, ["delete", "movie"])
            assert result.exit_code == 0
            mock_tui.assert_called_once_with(media_filter="movie")

    def test_delete_tv_with_name_still_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """'plexbud delete tv "Breaking Bad"' uses existing non-interactive path."""
        monkeypatch.setenv("PLEXBUD_MOCK", "1")
        result = runner.invoke(app, ["delete", "tv", "Breaking Bad"])
        assert result.exit_code == 0
        assert "Breaking Bad" in result.output
