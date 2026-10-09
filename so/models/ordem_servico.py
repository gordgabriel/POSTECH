import uuid

from django.db import models
from django.utils import timezone

from cadastros.models import Cliente, Veiculo
from oficina.atendimento.dominio import ordem_servico as dominio
from So_PosTech.exceptions import traduzir_erros_de_dominio

# Gerado a partir do enum do núcleo: mesmos valores e rótulos.
StatusOS = models.TextChoices(
    'StatusOS',
    [(status.name, (status.value, status.label)) for status in dominio.StatusOS],
    module=__name__,
)
TRANSICOES_VALIDAS = dominio.TRANSICOES_VALIDAS
DATA_POR_STATUS = dominio.DATA_POR_STATUS


class OrdemServico(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    descricao = models.TextField()
    diagnostico = models.TextField(null=True, blank=True)
    observacoes = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=30,
        choices=StatusOS.choices,
        default=StatusOS.RECEBIDA,
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='ordens_servico',
    )
    veiculo = models.ForeignKey(
        Veiculo,
        on_delete=models.PROTECT,
        related_name='ordens_servico',
    )
    data_abertura = models.DateTimeField(auto_now_add=True)
    data_diagnostico = models.DateTimeField(null=True, blank=True)
    data_inicio_execucao = models.DateTimeField(null=True, blank=True)
    data_finalizacao = models.DateTimeField(null=True, blank=True)
    data_entrega = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'ordem de serviço'
        verbose_name_plural = 'ordens de serviço'

    @staticmethod
    def validar_transicao(status_atual, novo_status):
        with traduzir_erros_de_dominio():
            dominio.OrdemServico.validar_transicao(status_atual, novo_status)

    def transitar_para(self, novo_status):
        """Transição validada com registro de datas e efeitos de estoque e notificação."""
        from So_PosTech.container import atendimento

        with traduzir_erros_de_dominio():
            atendimento(self).transitar_os.executar(self.pk, novo_status)

    def encerrar(self):
        from So_PosTech.container import atendimento

        with traduzir_erros_de_dominio():
            atendimento(self).encerrar_os.executar(self.pk)
        return self

    def save(self, *args, **kwargs):
        # Toda gravação passa aqui (comando, admin ou seed): mudança de status
        # é conferida pelo domínio e dispara e-mail e baixa de estoque.
        from So_PosTech.container import atendimento
        from so.repositorios import OrdemServicoRepositorioDjango as Repositorio

        status_gravado = None
        if self.pk:
            status_gravado = (
                OrdemServico.objects.only('status').get(pk=self.pk).status
            )

        entidade = Repositorio.para_entidade(self)
        with traduzir_erros_de_dominio():
            mudou = entidade.confirmar_mudanca_de_status(status_gravado, timezone.now())
        Repositorio.aplicar(entidade, self)

        super().save(*args, **kwargs)

        if mudou:
            atendimento(self).efeitos_da_transicao.executar(
                self.pk, self.status, status_gravado,
            )

    def __str__(self):
        return f'OS {self.uuid} - {self.get_status_display()}'
