"""Firestore Client - Imperative Shell.

This module handles persistence of alerted earthquake IDs to prevent
duplicate notifications. Uses Google Cloud Firestore.

All I/O is contained here; deduplication logic is in the core module.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from google.cloud import firestore


logger = logging.getLogger(__name__)


# Default collection name for storing alerted earthquake IDs
DEFAULT_COLLECTION = "earthquake_alerts"

# Default document for storing the set of alerted IDs
DEFAULT_DOCUMENT = "alerted_ids"


@dataclass
class FirestoreConfig:
    """Configuration for Firestore client.

    Attributes:
        project_id: GCP project ID (None for default)
        database: Firestore database name (None for default database)
        collection: Firestore collection name
        document: Document ID for storing alerted IDs
    """
    project_id: str | None = None
    database: str | None = None
    collection: str = DEFAULT_COLLECTION
    document: str = DEFAULT_DOCUMENT


class FirestoreClient:
    """Client for persisting alerted earthquake IDs to Firestore.

    This is part of the imperative shell - it handles database I/O.

    Document structure:
    {
        "ids": ["earthquake_id_1", "earthquake_id_2", ...],
        "updated_at": <timestamp>
    }
    """

    def __init__(self, config: FirestoreConfig | None = None) -> None:
        """Initialize Firestore client.

        Args:
            config: Firestore configuration
        """
        self.config = config or FirestoreConfig()
        self._client: firestore.Client | None = None

    @property
    def client(self) -> firestore.Client:
        """Lazy initialization of Firestore client."""
        if self._client is None:
            kwargs = {}
            if self.config.project_id:
                kwargs['project'] = self.config.project_id
            if self.config.database:
                kwargs['database'] = self.config.database
            self._client = firestore.Client(**kwargs)
        return self._client

    def _get_doc_ref(self) -> Any:
        """Get reference to the alerted IDs document."""
        return (
            self.client
            .collection(self.config.collection)
            .document(self.config.document)
        )

    def get_alerted_ids(self) -> set[str]:
        """Fetch the set of already-alerted earthquake IDs.

        This method performs database I/O.

        Returns:
            Set of earthquake IDs that have been alerted
        """
        logger.info("Fetching alerted IDs from Firestore")

        try:
            doc = self._get_doc_ref().get()

            if not doc.exists:
                logger.info("No existing alerted IDs document found")
                return set()

            data = doc.to_dict()
            ids = set(data.get("ids", []))

            logger.info("Fetched %d alerted IDs from Firestore", len(ids))
            return ids

        except Exception as e:
            logger.error("Failed to fetch alerted IDs: %s", str(e))
            # Return empty set on error - will re-alert but won't crash
            return set()

    def save_alerted_ids(self, ids: set[str]) -> bool:
        """Save the set of alerted earthquake IDs.

        This method performs database I/O.

        Args:
            ids: Set of earthquake IDs to save

        Returns:
            True if save was successful
        """
        logger.info("Saving %d alerted IDs to Firestore", len(ids))

        try:
            self._get_doc_ref().set({
                "ids": list(ids),
                "updated_at": datetime.now(timezone.utc),
            })

            logger.info("Successfully saved alerted IDs")
            return True

        except Exception as e:
            logger.error("Failed to save alerted IDs: %s", str(e))
            return False

    def add_alerted_ids(self, new_ids: set[str]) -> bool:
        """Add new IDs to the set of alerted earthquake IDs.

        This is an atomic update operation.

        Args:
            new_ids: New earthquake IDs to add

        Returns:
            True if update was successful
        """
        if not new_ids:
            return True

        logger.info("Adding %d new alerted IDs to Firestore", len(new_ids))

        try:
            # Use array union for atomic update
            self._get_doc_ref().set(
                {
                    "ids": firestore.ArrayUnion(list(new_ids)),
                    "updated_at": datetime.now(timezone.utc),
                },
                merge=True,
            )

            logger.info("Successfully added new alerted IDs")
            return True

        except Exception as e:
            logger.error("Failed to add alerted IDs: %s", str(e))
            return False

    def remove_alerted_ids(self, ids_to_remove: set[str]) -> bool:
        """Remove IDs from the set of alerted earthquake IDs.

        Used for expiring old IDs to keep storage bounded.

        Args:
            ids_to_remove: Earthquake IDs to remove

        Returns:
            True if update was successful
        """
        if not ids_to_remove:
            return True

        logger.info("Removing %d expired IDs from Firestore", len(ids_to_remove))

        try:
            self._get_doc_ref().set(
                {
                    "ids": firestore.ArrayRemove(list(ids_to_remove)),
                    "updated_at": datetime.now(timezone.utc),
                },
                merge=True,
            )

            logger.info("Successfully removed expired IDs")
            return True

        except Exception as e:
            logger.error("Failed to remove expired IDs: %s", str(e))
            return False
