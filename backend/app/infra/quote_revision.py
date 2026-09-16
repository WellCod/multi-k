"""Impressão da oferta armazenada; não é credencial nem substitui autorização."""

import hashlib
import json

from app.infra.models import CotacaoJob


def quote_revision(job: CotacaoJob) -> str:
    return hashlib.sha256(
        json.dumps(
            [
                str(job.id),
                job.cia,
                job.status,
                job.status_resultado,
                job.cotacao_id_cia,
                str(job.premio_total),
                job.payload_resposta,
            ],
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()
