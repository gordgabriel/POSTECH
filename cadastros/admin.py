from django.contrib import admin

from cadastros.models import Cliente, Servico, Veiculo


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ['nome', 'cpf_cnpj', 'email', 'telefone', 'usuario']
    search_fields = ['nome', 'cpf_cnpj', 'email']
    readonly_fields = ['uuid', 'created_at', 'updated_at']


@admin.register(Veiculo)
class VeiculoAdmin(admin.ModelAdmin):
    list_display = ['placa', 'marca', 'modelo', 'ano', 'cliente']
    search_fields = ['placa', 'marca', 'modelo', 'cliente__nome']
    readonly_fields = ['uuid', 'created_at', 'updated_at']


@admin.register(Servico)
class ServicoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'preco', 'tempo_execucao', 'ativo']
    list_filter = ['ativo']
    search_fields = ['nome']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
