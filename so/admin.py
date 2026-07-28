from django.contrib import admin

from so.models import ItemPecaOS, ItemServicoOS, Orcamento, OrdemServico


class ItemServicoOSInline(admin.TabularInline):
    model = ItemServicoOS
    extra = 0
    readonly_fields = ['uuid', 'created_at']


class ItemPecaOSInline(admin.TabularInline):
    model = ItemPecaOS
    extra = 0
    readonly_fields = ['uuid', 'created_at']


@admin.register(OrdemServico)
class OrdemServicoAdmin(admin.ModelAdmin):
    list_display = [
        'uuid',
        'status',
        'cliente',
        'veiculo',
        'responsavel',
        'data_abertura',
    ]
    list_filter = ['status', 'is_active']
    search_fields = ['uuid', 'cliente__nome', 'veiculo__placa']
    readonly_fields = [
        'uuid',
        'data_abertura',
        'data_diagnostico',
        'data_inicio_execucao',
        'data_finalizacao',
        'data_entrega',
        'updated_at',
    ]
    inlines = [ItemServicoOSInline, ItemPecaOSInline]


@admin.register(Orcamento)
class OrcamentoAdmin(admin.ModelAdmin):
    list_display = [
        'uuid',
        'ordem_servico',
        'sequencia',
        'valor_total',
        'status',
        'data_geracao',
    ]
    list_filter = ['status']
    search_fields = ['uuid', 'ordem_servico__uuid']
    readonly_fields = ['uuid', 'valor_total', 'data_geracao']
