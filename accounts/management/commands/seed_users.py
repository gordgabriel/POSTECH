from django.core.management.base import BaseCommand

from accounts.models import UserModel

SENHA_PADRAO = 'oficina123'

USUARIOS = [
    {
        'username': 'atendente',
        'name': 'Ana Atendente',
        'email': 'atendente@oficina.com',
        'type': UserModel.Tipo.ATENDENTE,
    },
    {
        'username': 'mecanico',
        'name': 'Marcos Mecânico',
        'email': 'mecanico@oficina.com',
        'type': UserModel.Tipo.MECANICO,
    },
    {
        'username': 'estoquista',
        'name': 'Estela Estoquista',
        'email': 'estoquista@oficina.com',
        'type': UserModel.Tipo.ESTOQUISTA,
    },
    {
        'username': 'admin',
        'name': 'Alice Admin',
        'email': 'admin@oficina.com',
        'type': UserModel.Tipo.ADMIN,
        'is_staff': True,
    },
    # Sem type: é o login de cliente, que enxerga apenas as próprias OS.
    {
        'username': 'cliente',
        'name': 'Carlos Cliente',
        'email': 'cliente@email.com',
        'type': None,
    },
]


class Command(BaseCommand):
    help = 'Cria os usuários dos cinco papéis para uso local e demonstração.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--senha',
            default=SENHA_PADRAO,
            help=f'Senha aplicada a todos os usuários (padrão: {SENHA_PADRAO}).',
        )

    def handle(self, *args, **options):
        senha = options['senha']

        for dados in USUARIOS:
            username = dados['username']
            usuario, criado = UserModel.objects.update_or_create(
                username=username,
                defaults={k: v for k, v in dados.items() if k != 'username'},
            )
            usuario.set_password(senha)
            usuario.save(update_fields=['password'])

            acao = 'Criado' if criado else 'Atualizado'
            papel = usuario.get_type_display() if usuario.type else 'Cliente'
            self.stdout.write(f'{acao} usuário: {username} ({papel})')

        self.stdout.write(self.style.SUCCESS(
            f'\nSeed de usuários concluído: {len(USUARIOS)} papéis, senha "{senha}".',
        ))
