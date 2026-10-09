from enum import Enum


class Enumeracao(str, Enum):
    """Enum com valor e rótulo que se comporta como string."""

    def __new__(cls, valor, rotulo):
        membro = str.__new__(cls, valor)
        membro._value_ = valor
        membro.label = rotulo
        return membro

    def __str__(self):
        return self.value

    def __repr__(self):
        return f'{type(self).__name__}.{self.name}'

    __format__ = str.__format__

    @classmethod
    def rotulo_de(cls, valor):
        try:
            return cls(valor).label
        except ValueError:
            return valor
