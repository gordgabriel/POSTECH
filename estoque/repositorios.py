from oficina.estoque.dominio.peca import Peca
from oficina.estoque.portas.repositorios import PecaRepositorio
from estoque.models import Peca as PecaModel


class PecaRepositorioDjango(PecaRepositorio):
    def __init__(self):
        self._travadas = {}

    @staticmethod
    def para_entidade(modelo):
        return Peca(
            id=modelo.pk,
            nome=modelo.nome,
            quantidade=modelo.quantidade,
            quantidade_reservada=modelo.quantidade_reservada,
            estoque_minimo=modelo.estoque_minimo,
        )

    def travar(self, peca_id):
        # select_for_update evita duas reservas da mesma unidade ao mesmo tempo.
        modelo = PecaModel.objects.select_for_update().get(pk=peca_id)
        self._travadas[modelo.pk] = modelo
        return self.para_entidade(modelo)

    def travar_varias(self, pecas_ids):
        return [
            self.para_entidade(modelo)
            for modelo in PecaModel.objects.select_for_update().filter(pk__in=pecas_ids)
        ]

    def obter_varias(self, pecas_ids):
        return [
            self.para_entidade(modelo)
            for modelo in PecaModel.objects.filter(pk__in=pecas_ids)
        ]

    def salvar(self, peca, campos):
        modelo = self._travadas[peca.id]
        for campo in campos:
            setattr(modelo, campo, getattr(peca, campo))
        modelo.save(update_fields=[*campos, 'updated_at'])
