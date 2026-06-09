"""Data source connectors.

Each connector knows how to pull a user's real data out of a given source type
(REST API, Google Sheets, CSV, SQL database) and make it queryable by the rest
of the pipeline. Non-SQL sources are *materialized* into a temporary SQLite
database so the uniform SQL pipeline (query writer -> executor -> analyst) runs
against the user's actual data instead of a bundled sample.
"""

from .base import MaterializedSource, materialize_source, SourceLoadError

__all__ = ["MaterializedSource", "materialize_source", "SourceLoadError"]
