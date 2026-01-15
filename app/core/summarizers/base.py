from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.models import OpportunityNotes, TranscriptInput


class Summarizer(ABC):
    @abstractmethod
    def summarize(self, transcript: TranscriptInput) -> OpportunityNotes:  # pragma: no cover
        raise NotImplementedError

    @property
    def name(self) -> str:  # pragma: no cover
        return self.__class__.__name__

