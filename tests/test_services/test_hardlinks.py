"""Tests for hardlink analysis."""

from __future__ import annotations

from pathlib import Path

from plexbud.models import FileLocation
from plexbud.services.hardlinks import calculate_deletion_impact, scan_file_locations


class TestScanFileLocations:
    def test_nonexistent_path(self) -> None:
        loc = scan_file_locations("/nonexistent/path")
        assert loc.media_paths == []
        assert loc.summary == "Unknown"

    def test_real_directory(self, tmp_path: Path) -> None:
        media = tmp_path / "media" / "show"
        media.mkdir(parents=True)
        (media / "ep01.mkv").write_bytes(b"x" * 100)

        loc = scan_file_locations(str(media))
        assert len(loc.media_paths) == 1
        assert loc.summary == "Plex"


class TestCalculateDeletionImpact:
    def test_nonexistent_path(self) -> None:
        impact = calculate_deletion_impact("/nonexistent", FileLocation())
        assert impact.total_bytes == 0
        assert impact.freeable_bytes == 0

    def test_simple_files(self, tmp_path: Path) -> None:
        media = tmp_path / "media"
        media.mkdir()
        f = media / "file.mkv"
        f.write_bytes(b"x" * 1000)

        loc = FileLocation(media_paths=[str(f)])
        impact = calculate_deletion_impact(str(media), loc)
        assert impact.total_bytes == 1000
        assert impact.freeable_bytes == 1000
        assert not impact.has_shared_links

    def test_hardlinked_files_both_in_deletion_set(self, tmp_path: Path) -> None:
        media = tmp_path / "media"
        torrents = tmp_path / "torrents"
        media.mkdir()
        torrents.mkdir()

        src = torrents / "file.mkv"
        src.write_bytes(b"x" * 1000)
        dst = media / "file.mkv"
        dst.hardlink_to(src)

        loc = FileLocation(
            media_paths=[str(dst)],
            torrent_paths=[str(src)],
        )
        impact = calculate_deletion_impact(str(media), loc)
        assert impact.total_bytes == 1000
        assert impact.freeable_bytes == 1000
        assert not impact.has_shared_links
