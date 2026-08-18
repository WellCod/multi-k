"""
Abstração de acesso a segredos.

Trocar EnvSecretProvider por SecretManagerProvider (GCP) é uma classe nova —
zero mudança no restante do código.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class SecretProvider(ABC):
    """Interface para leitura de segredos. Nunca use os.environ diretamente."""

    @abstractmethod
    def get(self, key: str) -> str:
        """Retorna o valor do segredo. Lança KeyError se não encontrado."""
        ...

    def get_optional(self, key: str, default: str = "") -> str:
        try:
            return self.get(key)
        except KeyError:
            return default


class EnvSecretProvider(SecretProvider):
    """
    Lê segredos de variáveis de ambiente.

    Válido apenas em desenvolvimento com dados mock.
    Quando a credencial real da Yelum chegar, substitua por SecretManagerProvider.
    """

    def get(self, key: str) -> str:
        value = os.environ.get(key)
        if value is None:
            raise KeyError(
                f"Secret '{key}' não encontrado. "
                "Verifique seu arquivo .env (use .env.example como base)."
            )
        return value


# Instância padrão usada pela aplicação.
# Substituída via injeção de dependência nos testes e na migração para GCP.
_provider: SecretProvider = EnvSecretProvider()


def get_secret(key: str) -> str:
    return _provider.get(key)


def get_optional_secret(key: str, default: str = "") -> str:
    return _provider.get_optional(key, default)


def set_provider(provider: SecretProvider) -> None:
    """Troca o provider global — use apenas em testes e na inicialização."""
    global _provider
    _provider = provider
