import datetime
import hashlib
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import backend_modal as backend
from pymongo.errors import DuplicateKeyError


class PollingTests(unittest.TestCase):
    def setUp(self):
        self.feed_url = "https://example.com/feed"
        self.entry = {
            "id": "episode-1", "title": "Episode 1", "published": "Tue, 10 Nov 2026 12:00:00 GMT",
            "enclosures": [{"href": "https://example.com/audio.mp3"}],
        }
        self.feed = SimpleNamespace(entries=[self.entry])
        self.db = MagicMock()
        self.db.episodes.find_one.return_value = None
        self.patchers = [
            patch.object(backend, "get_mongo_client"),
            patch.object(backend.requests, "get"),
            patch.object(backend.feedparser, "parse", return_value=self.feed),
            patch.object(backend.process_podcast, "remote", return_value="Transcript"),
            patch.object(backend.generate_summary, "remote", return_value=("TLDR", "Summary")),
            patch.object(backend.store_episode_data, "remote"),
        ]
        self.mongo, self.http, _, self.transcribe, self.summarize, self.store = [
            patcher.start() for patcher in self.patchers
        ]
        for patcher in self.patchers:
            self.addCleanup(patcher.stop)
        self.mongo.return_value.__enter__.return_value.podcast_summarizer = self.db

    def test_existing_episode_skips_transcription(self):
        # Arrange
        self.db.episodes.find_one.return_value = {"summary": "Already saved"}

        # Act
        backend.main.local(self.feed_url)

        # Assert
        self.transcribe.assert_not_called()
        self.db.episode_jobs.find_one_and_update.assert_not_called()
        query = self.db.episodes.find_one.call_args.args[0]
        self.assertIn({"title": self.entry["title"], "publish_date": self.entry["published"],
                       "feed_url": {"$exists": False}}, query["$or"])

    def test_new_episode_is_claimed_before_transcribing_and_completed_after_storage(self):
        # Arrange
        events = []
        self.db.episode_jobs.find_one_and_update.side_effect = lambda *a, **kw: events.append("claim")
        self.transcribe.side_effect = lambda *a: events.append("transcribe") or "Transcript"
        self.store.side_effect = lambda *a: events.append("store")
        self.db.episode_jobs.update_one.side_effect = lambda *a: events.append("complete")

        # Act
        backend.main.local(self.feed_url)

        # Assert
        episode_id = hashlib.sha256(f"{self.feed_url}\nepisode-1".encode()).hexdigest()
        self.assertEqual(events, ["claim", "transcribe", "store", "complete"])
        self.transcribe.assert_called_once_with("https://example.com/audio.mp3")
        self.store.assert_called_once_with(episode_id, self.feed_url, "Episode 1", "TLDR", "Summary",
                                           self.entry["published"])
        claim = self.db.episode_jobs.update_one.call_args.args
        self.assertEqual((claim[0]["_id"], claim[1]), (episode_id, {"$set": {"status": "completed"}}))

    def test_overlapping_claim_skips_expensive_work(self):
        # Arrange
        self.db.episode_jobs.find_one_and_update.side_effect = DuplicateKeyError("Already claimed")

        # Act
        backend.main.local(self.feed_url)

        # Assert
        self.transcribe.assert_not_called()
        self.store.assert_not_called()

    def test_failures_release_claim_without_marking_completed(self):
        for stage in (self.transcribe, self.summarize, self.store):
            with self.subTest(stage=stage):
                # Arrange
                self.db.episode_jobs.update_one.reset_mock()
                stage.side_effect = RuntimeError("Service unavailable")

                # Act / Assert
                with self.assertRaisesRegex(RuntimeError, "Service unavailable"):
                    backend.main.local(self.feed_url)
                self.assertEqual(self.db.episode_jobs.update_one.call_args.args[1],
                                 {"$set": {"status": "failed"}})
                stage.side_effect = None

    def test_failed_and_expired_jobs_can_be_reclaimed(self):
        # Act
        backend.main.local(self.feed_url)

        # Assert
        query, update = self.db.episode_jobs.find_one_and_update.call_args.args
        expiry = query["$or"][1]["lease_until"]["$lte"]
        self.assertEqual((query["$or"][0], query["$or"][1]["status"],
                          update["$set"]["lease_until"] - expiry),
                         ({"status": "failed"}, "processing", datetime.timedelta(hours=1)))
        self.assertEqual(self.db.episode_jobs.update_one.call_args.args[0]["token"],
                         update["$set"]["token"])

    def test_guid_keeps_identity_stable_when_title_or_audio_changes(self):
        # Arrange / Act
        backend.main.local(self.feed_url)
        first_id = self.store.call_args.args[0]
        self.entry.update(title="Updated title", enclosures=[{"href": "https://example.com/new.mp3"}])
        backend.main.local(self.feed_url)

        # Assert
        self.assertEqual(self.store.call_args.args[0], first_id)

    def test_missing_guid_falls_back_to_audio_url_and_identity_includes_feed(self):
        # Arrange
        del self.entry["id"]

        # Act
        backend.main.local(self.feed_url)
        first_id = self.store.call_args.args[0]
        backend.main.local("https://example.com/another-feed")

        # Assert
        expected_id = hashlib.sha256(f"{self.feed_url}\nhttps://example.com/audio.mp3".encode()).hexdigest()
        self.assertEqual(first_id, expected_id)
        self.assertNotEqual(self.store.call_args.args[0], first_id)

    def test_empty_feed_avoids_database_and_transcription(self):
        # Arrange
        self.feed.entries = []

        # Act
        backend.main.local(self.feed_url)

        # Assert
        self.mongo.assert_not_called()
        self.transcribe.assert_not_called()

    def test_missing_audio_is_rejected_before_claiming(self):
        # Arrange
        self.entry["enclosures"] = []

        # Act / Assert
        with self.assertRaisesRegex(ValueError, "missing audio"):
            backend.main.local(self.feed_url)
        self.mongo.assert_not_called()
        self.transcribe.assert_not_called()

    def test_failed_feed_request_does_not_claim_or_transcribe(self):
        # Arrange
        self.http.return_value.raise_for_status.side_effect = backend.requests.HTTPError("Unavailable")

        # Act / Assert
        with self.assertRaises(backend.requests.HTTPError):
            backend.main.local(self.feed_url)
        self.mongo.assert_not_called()
        self.transcribe.assert_not_called()

    def test_storage_is_insert_only_upsert_using_episode_identity(self):
        # Act
        backend.store_episode_data.local("episode-id", self.feed_url, "Title", "TLDR", "Summary", "Date")

        # Assert
        args, kwargs = self.db.episodes.update_one.call_args
        document = args[1]["$setOnInsert"]
        self.assertEqual((args[0], kwargs, document["feed_url"], document["summary"]),
                         ({"_id": "episode-id"}, {"upsert": True}, self.feed_url, "Summary"))
        self.db.episodes.insert_one.assert_not_called()


class SummaryTests(unittest.TestCase):
    def test_empty_transcript_does_not_call_groq(self):
        # Arrange
        with patch.object(backend, "Groq") as groq:
            # Act / Assert
            with self.assertRaisesRegex(ValueError, "No transcript"):
                backend.generate_summary.local("")
            groq.assert_not_called()

    def test_groq_failure_is_raised_instead_of_saved_as_summary(self):
        # Arrange
        with patch.dict(os.environ, {"GROQ_API_KEY": "test"}), patch.object(backend, "Groq") as groq:
            groq.return_value.chat.completions.create.side_effect = RuntimeError("Rate limited")

            # Act / Assert
            with self.assertRaisesRegex(RuntimeError, "Rate limited"):
                backend.generate_summary.local("Transcript")

    def test_empty_summary_response_is_rejected(self):
        # Arrange
        with patch.dict(os.environ, {"GROQ_API_KEY": "test"}), patch.object(backend, "Groq") as groq:
            response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=" "))])
            groq.return_value.chat.completions.create.return_value = response

            # Act / Assert
            with self.assertRaisesRegex(ValueError, "Empty summary"):
                backend.generate_summary.local("Transcript")


if __name__ == "__main__":
    unittest.main()
