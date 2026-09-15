from __future__ import annotations

from enum import StrEnum


class ProviderType(StrEnum):
    REALTIME = "realtime"
    HISTORICAL = "historical"
    REFERENCE = "reference"
    NEWS = "news"
    MACRO = "macro"
    MANUAL = "manual"
    BROKER = "broker"


class ProviderName(StrEnum):
    TSETMC = "tsetmc"
    TSE = "tse"
    CODAL = "codal"
    MARKETWATCH = "marketwatch"
    AGAH = "agah"
    FARDANAMA = "fardanama"
    MOFID = "mofid"
    RSS = "rss"
    MANUAL = "manual"
    SQL_DATABASE = "sql_database"
    FILE_ARCHIVE = "file_archive"


PROVIDER_PRIORITIES: dict[ProviderName, int] = {
    ProviderName.TSETMC: 10,
    ProviderName.TSE: 20,
    ProviderName.MARKETWATCH: 30,
    ProviderName.CODAL: 10,
    ProviderName.AGAH: 20,
    ProviderName.FARDANAMA: 20,
    ProviderName.MOFID: 20,
    ProviderName.RSS: 30,
    ProviderName.MANUAL: 40,
    ProviderName.SQL_DATABASE: 50,
    ProviderName.FILE_ARCHIVE: 60,
}
