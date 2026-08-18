from enum import StrEnum
from uuid import UUID

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


class Papel(StrEnum):
    CORRETOR = "corretor"
    ADMIN = "admin"
