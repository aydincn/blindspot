from blindspot.collector.bots import is_bot_author
from blindspot.collector.filters import FileFilter, canonical_email
from blindspot.collector.git import GitCollector
from blindspot.collector.mailmap import MailMap
from blindspot.collector.models import Commit, FileChange

__all__ = [
    "Commit",
    "FileChange",
    "FileFilter",
    "GitCollector",
    "MailMap",
    "canonical_email",
    "is_bot_author",
]
