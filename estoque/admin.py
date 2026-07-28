from django.contrib import admin

from estoque.models import Peca


@admin.register(Peca)
class PecaAdmin(admin.ModelAdmin):
    list_display = [
        'nome',
        'preco',
        'quantidade',
        'quantidade_reservada',
        'estoque_minimo',
        'abaixo_do_minimo',
    ]
    search_fields = ['nome']
    readonly_fields = ['uuid', 'created_at', 'updated_at']

    @admin.display(boolean=True, description='Abaixo do mínimo')
    def abaixo_do_minimo(self, obj):
        return obj.abaixo_do_minimo
