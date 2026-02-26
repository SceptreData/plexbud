"""Tests for deletion planning and execution service."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from plexbud.models import DeletionPlan, FileLocation, MediaItem, TorrentInfo
from plexbud.services.deletion import build_deletion_plan, execute_deletion_plan


def _make_item(media_type: str = "tv") -> MediaItem:
    return MediaItem(
        title="Breaking Bad",
        arr_id=1,
        external_id=81189,
        path="/media/tv/Breaking Bad",
        size_bytes=45_000_000_000,
        added=datetime(2024, 1, 1, tzinfo=UTC),
        media_type=media_type,
    )


def _mock_config() -> MagicMock:
    config = MagicMock()
    config.paths.torrents_root = "/downloads/torrents"
    config.paths.usenet_complete = "/downloads/usenet"
    config.tautulli.tv_section_id = 1
    config.tautulli.movie_section_id = 2
    return config


class TestBuildDeletionPlan:
    @patch("plexbud.services.deletion.collect_inodes", return_value=set())
    @patch("plexbud.services.deletion.scan_file_locations")
    def test_plan_for_nonexistent_path(
        self,
        mock_scan: MagicMock,
        mock_inodes: MagicMock,
    ) -> None:
        mock_scan.return_value = FileLocation()
        qbt = MagicMock()
        qbt.get_torrents.return_value = []
        tautulli = MagicMock()
        tautulli.get_activity.return_value = []

        item = _make_item()
        item.path = "/nonexistent/path"

        plan = build_deletion_plan(item, qbt=qbt, tautulli=tautulli, config=_mock_config())

        assert plan.title == "Breaking Bad"
        assert plan.media_type == "tv"
        assert plan.arr_id == 1
        assert plan.media_file_count == 0
        assert plan.torrent_count == 0

    @patch("plexbud.services.deletion._safe_size", return_value=1_000_000)
    @patch("plexbud.services.deletion.collect_inodes", return_value={(1, 12345)})
    @patch("plexbud.services.deletion.scan_file_locations")
    def test_plan_with_media_files(
        self,
        mock_scan: MagicMock,
        mock_inodes: MagicMock,
        mock_safe_size: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_scan.return_value = FileLocation()
        qbt = MagicMock()
        qbt.get_torrents.return_value = []
        tautulli = MagicMock()
        tautulli.get_activity.return_value = []

        # Create real files on disk
        media_dir = tmp_path / "Breaking Bad"
        media_dir.mkdir()
        (media_dir / "episode.mkv").write_bytes(b"x" * 100)

        item = _make_item()
        item.path = str(media_dir)

        plan = build_deletion_plan(item, qbt=qbt, tautulli=tautulli, config=_mock_config())

        assert plan.media_file_count == 1
        assert plan.media_dir == str(media_dir)

    @patch("plexbud.services.deletion.collect_inodes", return_value={(1, 99999)})
    @patch("plexbud.services.deletion.scan_file_locations")
    def test_plan_finds_matching_torrents(
        self,
        mock_scan: MagicMock,
        mock_inodes: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_scan.return_value = FileLocation()
        tautulli = MagicMock()
        tautulli.get_activity.return_value = []

        # Create a real torrent file that shares an inode
        torrent_dir = tmp_path / "torrents"
        torrent_dir.mkdir()
        torrent_file = torrent_dir / "episode.mkv"
        torrent_file.write_bytes(b"x" * 100)
        # Patch stat to return matching (device, inode) pair
        fake_stat = MagicMock()
        fake_stat.st_dev = 1
        fake_stat.st_ino = 99999

        qbt = MagicMock()
        qbt.get_torrents.return_value = [
            TorrentInfo(hash="abc123", name="Breaking Bad", save_path=str(torrent_dir), size=100),
        ]
        qbt.get_torrent_files.return_value = ["episode.mkv"]

        media_dir = tmp_path / "media"
        media_dir.mkdir()
        item = _make_item()
        item.path = str(media_dir)

        with patch.object(Path, "stat", return_value=fake_stat):
            plan = build_deletion_plan(item, qbt=qbt, tautulli=tautulli, config=_mock_config())

        assert plan.torrent_count == 1
        assert "abc123" in plan.torrent_hashes

    @patch("plexbud.services.deletion.collect_inodes", return_value=set())
    @patch("plexbud.services.deletion.scan_file_locations")
    def test_plan_warns_on_tautulli_unreachable(
        self,
        mock_scan: MagicMock,
        mock_inodes: MagicMock,
    ) -> None:
        mock_scan.return_value = FileLocation()
        qbt = MagicMock()
        qbt.get_torrents.return_value = []
        tautulli = MagicMock()
        tautulli.get_activity.side_effect = Exception("Connection refused")

        item = _make_item()
        item.path = "/nonexistent"

        plan = build_deletion_plan(item, qbt=qbt, tautulli=tautulli, config=_mock_config())

        assert any("Tautulli unreachable" in w for w in plan.warnings)

    @patch("plexbud.services.deletion.collect_inodes", return_value=set())
    @patch("plexbud.services.deletion.scan_file_locations")
    def test_plan_warns_on_active_stream(
        self,
        mock_scan: MagicMock,
        mock_inodes: MagicMock,
    ) -> None:
        mock_scan.return_value = FileLocation()
        qbt = MagicMock()
        qbt.get_torrents.return_value = []
        tautulli = MagicMock()
        tautulli.get_activity.return_value = [
            {"grandparent_title": "Breaking Bad", "title": "Pilot", "friendly_name": "alice"},
        ]

        item = _make_item()
        item.path = "/nonexistent"

        plan = build_deletion_plan(item, qbt=qbt, tautulli=tautulli, config=_mock_config())

        assert any("alice" in w for w in plan.warnings)


class TestExecuteDeletionPlan:
    def test_execute_removes_torrents(self) -> None:
        qbt = MagicMock()
        plan = DeletionPlan(title="Test", media_type="tv", arr_id=1)
        plan.torrent_hashes = ["abc123", "def456"]
        plan.torrent_count = 2

        log = execute_deletion_plan(plan, qbt=qbt)

        qbt.delete_torrents.assert_called_once_with(["abc123", "def456"], delete_files=True)
        assert any("2 torrent" in entry for entry in log)

    def test_execute_deletes_from_sonarr(self) -> None:
        qbt = MagicMock()
        sonarr = MagicMock()
        plan = DeletionPlan(title="Test", media_type="tv", arr_id=42)

        log = execute_deletion_plan(plan, qbt=qbt, sonarr=sonarr)

        sonarr.delete_series.assert_called_once_with(42)
        assert any("Sonarr" in entry for entry in log)

    def test_execute_deletes_from_radarr(self) -> None:
        qbt = MagicMock()
        radarr = MagicMock()
        plan = DeletionPlan(title="Test", media_type="movie", arr_id=7)

        log = execute_deletion_plan(plan, qbt=qbt, radarr=radarr)

        radarr.delete_movie.assert_called_once_with(7)
        assert any("Radarr" in entry for entry in log)

    def test_execute_removes_usenet_files(self, tmp_path: Path) -> None:
        qbt = MagicMock()

        usenet_file = tmp_path / "show.nzb"
        usenet_file.write_text("nzb content")

        plan = DeletionPlan(title="Test", media_type="tv", arr_id=1)
        plan.usenet_paths = [str(usenet_file)]

        log = execute_deletion_plan(plan, qbt=qbt)

        assert not usenet_file.exists()
        assert any("usenet" in entry.lower() for entry in log)

    def test_execute_handles_missing_usenet_gracefully(self) -> None:
        qbt = MagicMock()
        plan = DeletionPlan(title="Test", media_type="tv", arr_id=1)
        plan.usenet_paths = ["/nonexistent/file.nzb"]

        log = execute_deletion_plan(plan, qbt=qbt)

        # No crash, no usenet deletion logged (file didn't exist)
        assert not any("Deleted usenet" in entry for entry in log)

    def test_execute_empty_plan(self) -> None:
        qbt = MagicMock()
        plan = DeletionPlan(title="Test", media_type="tv", arr_id=1)

        execute_deletion_plan(plan, qbt=qbt)

        qbt.delete_torrents.assert_not_called()

    def test_execute_continues_after_qbt_failure(self) -> None:
        qbt = MagicMock()
        qbt.delete_torrents.side_effect = Exception("qBt down")
        sonarr = MagicMock()

        plan = DeletionPlan(title="Test", media_type="tv", arr_id=42)
        plan.torrent_hashes = ["abc123"]
        plan.torrent_count = 1

        log = execute_deletion_plan(plan, qbt=qbt, sonarr=sonarr)

        assert any("Failed" in entry and "qBt down" in entry for entry in log)
        sonarr.delete_series.assert_called_once_with(42)

    def test_execute_continues_after_arr_failure(self) -> None:
        qbt = MagicMock()
        sonarr = MagicMock()
        sonarr.delete_series.side_effect = Exception("Sonarr down")

        plan = DeletionPlan(title="Test", media_type="tv", arr_id=42)
        plan.torrent_hashes = ["abc123"]
        plan.torrent_count = 1

        log = execute_deletion_plan(plan, qbt=qbt, sonarr=sonarr)

        assert any("Removed 1 torrent" in entry for entry in log)
        assert any("Failed" in entry and "Sonarr down" in entry for entry in log)

    def test_execute_rejects_paths_outside_allowed_roots(self, tmp_path: Path) -> None:
        qbt = MagicMock()
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        outside_file = tmp_path / "outside" / "file.nzb"
        outside_file.parent.mkdir()
        outside_file.write_text("content")

        plan = DeletionPlan(title="Test", media_type="tv", arr_id=1)
        plan.usenet_paths = [str(outside_file)]

        log = execute_deletion_plan(plan, qbt=qbt, allowed_roots=[str(allowed)])

        assert outside_file.exists()
        assert any("outside allowed roots" in entry for entry in log)
