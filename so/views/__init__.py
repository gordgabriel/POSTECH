from .item_peca_views import ItemPecaOSViewSet
from .item_servico_views import ItemServicoOSViewSet
from .orcamento_views import OrcamentoViewSet
from .ordem_servico_views import OrdemServicoViewSet
from .relatorio_views import TempoMedioExecucaoView

__all__ = [
    'ItemPecaOSViewSet',
    'ItemServicoOSViewSet',
    'OrcamentoViewSet',
    'OrdemServicoViewSet',
    'TempoMedioExecucaoView',
]
