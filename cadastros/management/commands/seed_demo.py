from decimal import Decimal

from django.core.management.base import BaseCommand

from cadastros.models import Cliente, Servico, Veiculo
from estoque.models import Peca


class Command(BaseCommand):
    help = 'Popula o banco com clientes, veículos, serviços e peças de demonstração.'

    def handle(self, *args, **options):
        clientes_data = [
            {
                'cpf_cnpj': '529.982.247-25',
                'nome': 'João da Silva',
                'email': 'joao.silva@email.com',
                'telefone': '11987654321',
                'endereco': 'Rua das Flores, 100 - São Paulo/SP',
                'veiculos': [
                    {'placa': 'ABC1D23', 'marca': 'Fiat', 'modelo': 'Uno', 'ano': 2018},
                ],
            },
            {
                'cpf_cnpj': '390.533.447-05',
                'nome': 'Maria Santos',
                'email': 'maria.santos@email.com',
                'telefone': '11976543210',
                'endereco': 'Av. Paulista, 500 - São Paulo/SP',
                'veiculos': [
                    {'placa': 'DEF2E45', 'marca': 'Volkswagen', 'modelo': 'Gol', 'ano': 2020},
                ],
            },
            {
                'cpf_cnpj': '11.444.777/0001-61',
                'nome': 'Transportes Rápido LTDA',
                'email': 'contato@transportesrapido.com',
                'telefone': '1133334444',
                'endereco': 'Rua Industrial, 200 - Guarulhos/SP',
                'veiculos': [
                    {'placa': 'GHI3F67', 'marca': 'Ford', 'modelo': 'Ranger', 'ano': 2022},
                    {'placa': 'JKL4G89', 'marca': 'Mercedes-Benz', 'modelo': 'Sprinter', 'ano': 2021},
                ],
            },
            {
                'cpf_cnpj': '863.735.940-09',
                'nome': 'Ana Costa',
                'email': 'ana.costa@email.com',
                'telefone': '21998765432',
                'endereco': 'Rua do Catete, 45 - Rio de Janeiro/RJ',
                'veiculos': [
                    {'placa': 'MNO5H12', 'marca': 'Hyundai', 'modelo': 'HB20', 'ano': 2019},
                ],
            },
            {
                'cpf_cnpj': '714.287.938-60',
                'nome': 'Pedro Oliveira',
                'email': 'pedro.oliveira@email.com',
                'telefone': '31987651234',
                'endereco': 'Av. Afonso Pena, 1200 - Belo Horizonte/MG',
                'veiculos': [
                    {'placa': 'PQR6J34', 'marca': 'Chevrolet', 'modelo': 'Onix', 'ano': 2023},
                ],
            },
        ]

        servicos_data = [
            {'nome': 'Troca de óleo', 'descricao': 'Troca de óleo mineral ou sintético + filtro', 'preco': '180.00', 'tempo_execucao': 45},
            {'nome': 'Alinhamento e balanceamento', 'descricao': 'Alinhamento computadorizado 4 rodas', 'preco': '120.00', 'tempo_execucao': 60},
            {'nome': 'Revisão dos freios', 'descricao': 'Inspeção pastilhas, discos e fluido', 'preco': '250.00', 'tempo_execucao': 90},
            {'nome': 'Troca de correia dentada', 'descricao': 'Kit correia dentada com tensor', 'preco': '650.00', 'tempo_execucao': 240},
            {'nome': 'Diagnóstico eletrônico', 'descricao': 'Leitura de OBD e relatório de falhas', 'preco': '150.00', 'tempo_execucao': 30},
            {'nome': 'Recarga de ar condicionado', 'descricao': 'Recarga gás R134a + teste de vazamento', 'preco': '220.00', 'tempo_execucao': 75},
            {'nome': 'Troca de velas', 'descricao': 'Substituição jogo de velas de ignição', 'preco': '95.00', 'tempo_execucao': 40},
            {'nome': 'Limpeza de bicos injetores', 'descricao': 'Ultrassom + teste de vazão', 'preco': '320.00', 'tempo_execucao': 120},
        ]

        pecas_data = [
            {'nome': 'Filtro de óleo', 'descricao': 'Filtro universal 1.0 a 1.6', 'preco': '35.00', 'quantidade': 25, 'estoque_minimo': 5},
            {'nome': 'Filtro de ar', 'descricao': 'Elemento filtrante de ar motor', 'preco': '42.00', 'quantidade': 18, 'estoque_minimo': 4},
            {'nome': 'Pastilha de freio dianteira', 'descricao': 'Jogo pastilhas cerâmicas', 'preco': '89.90', 'quantidade': 12, 'estoque_minimo': 3},
            {'nome': 'Disco de freio', 'descricao': 'Disco ventilado 256mm', 'preco': '145.00', 'quantidade': 8, 'estoque_minimo': 2},
            {'nome': 'Correia dentada', 'descricao': 'Correia 120 dentes reforçada', 'preco': '78.50', 'quantidade': 6, 'estoque_minimo': 2},
            {'nome': 'Vela de ignição', 'descricao': 'Vela iridium longa duração', 'preco': '28.00', 'quantidade': 40, 'estoque_minimo': 8},
            {'nome': 'Fluido de freio DOT4', 'descricao': '500ml fluido sintético', 'preco': '22.00', 'quantidade': 30, 'estoque_minimo': 6},
            {'nome': 'Óleo motor 5W30 sintético', 'descricao': '1 litro óleo sintético', 'preco': '55.00', 'quantidade': 50, 'estoque_minimo': 10},
            {'nome': 'Amortecedor dianteiro', 'descricao': 'Amortecedor pressurizado par', 'preco': '380.00', 'quantidade': 4, 'estoque_minimo': 1},
            {'nome': 'Bateria 60Ah', 'descricao': 'Bateria selada 60Ah 540A', 'preco': '520.00', 'quantidade': 5, 'estoque_minimo': 2},
        ]

        for dados in clientes_data:
            veiculos = dados.pop('veiculos')
            cliente, created = Cliente.objects.update_or_create(
                cpf_cnpj=dados['cpf_cnpj'],
                defaults=dados,
            )
            acao = 'Criado' if created else 'Atualizado'
            self.stdout.write(f'{acao} cliente: {cliente.nome}')
            for v in veiculos:
                veiculo, v_created = Veiculo.objects.update_or_create(
                    placa=v['placa'],
                    defaults={**v, 'cliente': cliente},
                )
                v_acao = 'criado' if v_created else 'atualizado'
                self.stdout.write(f'  Veículo {v_acao}: {veiculo.placa} ({veiculo.marca} {veiculo.modelo})')

        for s in servicos_data:
            servico, created = Servico.objects.update_or_create(
                nome=s['nome'],
                defaults={
                    'descricao': s['descricao'],
                    'preco': Decimal(s['preco']),
                    'tempo_execucao': s['tempo_execucao'],
                    'ativo': True,
                },
            )
            acao = 'Criado' if created else 'Atualizado'
            self.stdout.write(f'{acao} serviço: {servico.nome} - R$ {servico.preco}')

        for p in pecas_data:
            peca, created = Peca.objects.update_or_create(
                nome=p['nome'],
                defaults={
                    'descricao': p['descricao'],
                    'preco': Decimal(p['preco']),
                    'quantidade': p['quantidade'],
                    'quantidade_reservada': 0,
                    'estoque_minimo': p['estoque_minimo'],
                },
            )
            acao = 'Criado' if created else 'Atualizado'
            self.stdout.write(
                f'{acao} peça: {peca.nome} - R$ {peca.preco} '
                f'(estoque: {peca.quantidade}, mín: {peca.estoque_minimo})',
            )

        self.stdout.write(self.style.SUCCESS(
            f'\nSeed concluído: {Cliente.objects.count()} clientes, '
            f'{Veiculo.objects.count()} veículos, '
            f'{Servico.objects.count()} serviços, '
            f'{Peca.objects.count()} peças.',
        ))
